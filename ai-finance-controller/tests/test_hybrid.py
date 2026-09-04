"""Mocked tests for Gemini validation and confidence-gated hybrid routing."""

import json

import numpy as np
import pandas as pd

from src.categorization.hybrid import HybridTransactionClassifier
from src.llm.gemini_fallback import classify_with_gemini, validate_gemini_response
from src.llm.gemini_smoke_test import run_gemini_smoke_test
import src.categorization.phase2_evaluate as phase2_evaluate


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, response=None, exception=None):
        self.response = response
        self.exception = exception
        self.calls = 0

    def generate_content(self, **_kwargs):
        self.calls += 1
        if self.exception:
            raise self.exception
        return self.response


class FakeClient:
    def __init__(self, response=None, exception=None):
        self.models = FakeModels(response, exception)


class FakePipeline:
    classes_ = ["Food", "Transport"]

    def predict_proba(self, descriptions):
        return [[0.95, 0.05] if "high" in text else [0.45, 0.55] for text in descriptions]


def test_missing_gemini_api_key_is_safe(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = classify_with_gemini("UPI PAYMENT 829173", ["Food"])
    assert result["ok"] is False
    assert result["error_code"] == "missing_api_key"


def test_valid_gemini_structured_response():
    client = FakeClient(FakeResponse(json.dumps({"category": "Food", "confidence": 0.94, "reason": "merchant cue"})))
    result = classify_with_gemini("SWIGGY", ["Food", "Transport"], client=client)
    assert result == {"ok": True, "category": "Food", "confidence": 0.94, "reason": "merchant cue"}
    assert client.models.calls == 1


def test_malformed_gemini_response_is_safe():
    client = FakeClient(FakeResponse("not json"))
    assert classify_with_gemini("SWIGGY", ["Food"], client=client)["error_code"] == "malformed_response"


def test_invalid_category_and_confidence_are_rejected():
    assert validate_gemini_response({"category": "Other", "confidence": 0.9, "reason": "x"}, ["Food"])["error_code"] == "invalid_category"
    assert validate_gemini_response({"category": "Food", "confidence": 1.2, "reason": "x"}, ["Food"])["error_code"] == "invalid_confidence"


def test_high_confidence_prediction_does_not_call_gemini():
    calls = []

    def fallback(*_args):
        calls.append(True)
        return {"ok": True, "category": "Transport", "confidence": 0.9, "reason": "unused"}

    result = HybridTransactionClassifier(pipeline=FakePipeline(), gemini_classifier=fallback).predict("high confidence", 0.70)
    assert result["source"] == "ml"
    assert result["fallback_used"] is False
    assert calls == []


def test_low_confidence_prediction_uses_gemini_and_preserves_ml_confidence():
    fallback = lambda *_args: {"ok": True, "category": "Food", "confidence": 0.91, "reason": "context"}
    result = HybridTransactionClassifier(pipeline=FakePipeline(), gemini_classifier=fallback).predict("low confidence", 0.70)
    assert result["source"] == "gemini"
    assert result["fallback_used"] is True
    assert result["ml_confidence"] == 0.55
    assert result["gemini_confidence"] == 0.91
    assert result["gemini_attempted"] is True


def test_gemini_api_failure_falls_back_to_ml_output():
    failing = lambda *_args: {"ok": False, "error_code": "gemini_api_error"}
    result = HybridTransactionClassifier(pipeline=FakePipeline(), gemini_classifier=failing).predict("low confidence", 0.70)
    assert result["source"] == "ml"
    assert result["fallback_used"] is True
    assert result["fallback_error"] == "gemini_api_error"
    assert result["fallback_status"] == "gemini_unavailable"
    assert result["category"] == "Transport"


def test_hybrid_output_format():
    result = HybridTransactionClassifier(pipeline=FakePipeline()).predict("high confidence", 0.70)
    assert set(result) == {
        "transaction_description", "category", "confidence", "source", "fallback_used", "fallback_status",
        "ml_category", "ml_confidence", "gemini_category", "gemini_confidence",
        "gemini_reason", "gemini_attempted", "gemini_exception_type",
        "gemini_http_status_code", "gemini_provider_message", "gemini_request_attempts", "fallback_error",
    }


def test_smoke_test_uses_only_the_controlled_examples():
    client = FakeClient(FakeResponse(json.dumps({"category": "Food", "confidence": 0.8, "reason": "mock"})))
    outcome = run_gemini_smoke_test(["Food", "Transport"], client=client)
    assert outcome["requests_attempted"] == 4
    assert outcome["successful_responses"] == 4
    assert client.models.calls == 4


def test_hybrid_evaluation_keeps_true_and_final_categories_separate(monkeypatch, tmp_path):
    """Regression test for duplicate `category` columns becoming two predictions."""
    challenge = pd.DataFrame(
        {
            "challenge_group": ["known_merchant_noisy_description", "unseen_merchant", "ambiguous_description"],
            "transaction_description": ["high one", "low two", "low three"],
            "category": ["Food", "Transport", "Food"],
        }
    )
    challenge_path = tmp_path / "challenge.csv"
    challenge.to_csv(challenge_path, index=False)

    class EvaluationPipeline(FakePipeline):
        def predict_proba(self, descriptions):
            return np.array([[0.95, 0.05] if "high" in text else [0.20, 0.80] for text in descriptions])

    class EvaluationClassifier(HybridTransactionClassifier):
        def __init__(self, **_kwargs):
            super().__init__(pipeline=EvaluationPipeline(), gemini_classifier=lambda *_args: {"ok": True, "category": "Food", "confidence": 0.9, "reason": "mock"})

    monkeypatch.setattr(phase2_evaluate, "HybridTransactionClassifier", EvaluationClassifier)
    output = phase2_evaluate.run_hybrid_evaluation(
        challenge_path=challenge_path,
        metrics_output_path=tmp_path / "metrics.json",
        predictions_output_path=tmp_path / "predictions.csv",
    )
    predictions = pd.read_csv(tmp_path / "predictions.csv")
    assert len(predictions) == len(challenge)
    assert "category" in predictions.columns
    assert "final_prediction" in predictions.columns
    assert predictions.columns.tolist().count("category") == 1
    assert output["hybrid_metrics"]["total_test_samples"] == len(challenge)


def test_retries_transient_429_then_returns_valid_response():
    class TransientError(Exception):
        status_code = 429

    class RetryModels:
        def __init__(self):
            self.calls = 0

        def generate_content(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise TransientError("rate limited")
            return FakeResponse(json.dumps({"category": "Food", "confidence": 0.8, "reason": "mock"}))

    client = type("RetryClient", (), {"models": RetryModels()})()
    sleeps = []
    result = classify_with_gemini(
        "SWIGGY", ["Food"], client=client, sleep_fn=sleeps.append, monotonic_fn=lambda: 10.0
    )
    assert result["ok"] is True
    assert client.models.calls == 2
    assert 1.0 in sleeps


def test_does_not_retry_non_transient_provider_error():
    class BadRequestError(Exception):
        status_code = 400

    client = FakeClient(exception=BadRequestError("bad request"))
    result = classify_with_gemini("SWIGGY", ["Food"], client=client, sleep_fn=lambda _delay: None)
    assert result["ok"] is False
    assert result["gemini_request_attempts"] == 1
    assert result["gemini_http_status_code"] == 400
    assert client.models.calls == 1


def test_exhausted_429_retries_preserve_ml_result_and_mark_rate_limited():
    class RateLimitError(Exception):
        status_code = 429

    fallback = lambda *_args: {
        "ok": False,
        "error_code": "gemini_rate_limited",
        "gemini_request_attempts": 3,
        "gemini_exception_type": "ClientError",
        "gemini_http_status_code": 429,
        "gemini_provider_message": "quota exceeded",
    }
    result = HybridTransactionClassifier(pipeline=FakePipeline(), gemini_classifier=fallback).predict("low confidence", 0.70)
    assert result["source"] == "ml"
    assert result["category"] == "Transport"
    assert result["fallback_used"] is True
    assert result["fallback_status"] == "rate_limited"
    assert result["fallback_error"] == "gemini_rate_limited"
    assert result["gemini_http_status_code"] == 429
