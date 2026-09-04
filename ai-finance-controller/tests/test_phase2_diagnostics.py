"""Tests for post-evaluation accounting of failed Gemini fallback rows."""

import json

import pandas as pd

from src.categorization.phase2_post_evaluation_diagnostics import analyze_phase2_results


def test_diagnostics_exclude_failed_fallbacks_from_valid_model_metrics(tmp_path):
    predictions = pd.DataFrame(
        {
            "challenge_group": ["known_merchant_noisy_description"] * 3,
            "category": ["Food", "Food", "Transport"],
            "final_prediction": ["Food", "Transport", "Transport"],
            "source": ["gemini", "ml", "gemini"],
            "fallback_used": [True, True, True],
            "gemini_attempted": [True, True, True],
            "gemini_category": ["Food", None, "Transport"],
            "fallback_error": [None, "gemini_rate_limited", None],
            "gemini_exception_type": [None, "ClientError", None],
            "gemini_http_status_code": [None, 429, None],
            "gemini_provider_message": [None, "quota exceeded", None],
        }
    )
    prediction_path = tmp_path / "predictions.csv"
    metrics_path = tmp_path / "metrics.json"
    output_path = tmp_path / "diagnostics.json"
    predictions.to_csv(prediction_path, index=False)
    metrics_path.write_text(json.dumps({"selected_threshold": 0.7, "ml_only_metrics": {"classes": ["Food", "Transport"]}}))

    report = analyze_phase2_results(prediction_path, metrics_path, output_path)

    assert report["gemini_fallback_calls"] == 3
    assert report["gemini_successful_responses"] == 2
    assert report["gemini_failed_responses"] == 1
    assert report["gemini_metrics_on_successful_responses_only"]["accuracy"] == 1.0
    assert report["hybrid_metrics_excluding_gemini_failed_rows"]["accuracy"] == 1.0
    assert report["hybrid_accuracy_failure_inclusive"]["accuracy"] == 2 / 3
    assert output_path.exists()
