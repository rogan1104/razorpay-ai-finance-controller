"""Confidence-gated local ML plus Gemini fallback categorization."""

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

import joblib
import numpy as np

from src.categorization.preprocess import clean_text
from src.llm.gemini_fallback import classify_with_gemini


class HybridTransactionClassifier:
    """Route only low-confidence local predictions to an injected LLM fallback."""

    def __init__(
        self,
        model_path: str | Path = "models/categorization_pipeline.joblib",
        pipeline: Optional[Any] = None,
        gemini_classifier: Callable[[str, Iterable[str]], Dict[str, Any]] = classify_with_gemini,
    ) -> None:
        self.pipeline = pipeline if pipeline is not None else joblib.load(model_path)
        self.allowed_categories = [str(category) for category in self.pipeline.classes_]
        self.gemini_classifier = gemini_classifier

    def predict(self, transaction_description: Optional[str], threshold: float) -> Dict[str, Any]:
        """Return local output, or a validated Gemini result below the threshold."""
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        description = "" if transaction_description is None else str(transaction_description)
        if not clean_text(description):
            return {
                "transaction_description": description,
                "category": "Unknown",
                "confidence": 0.0,
                "source": "ml",
                "fallback_used": False,
                "fallback_status": "not_used",
                "ml_category": "Unknown",
                "ml_confidence": 0.0,
                "gemini_category": None,
                "gemini_confidence": None,
                "gemini_reason": None,
                "gemini_attempted": False,
                "gemini_exception_type": None,
                "gemini_http_status_code": None,
                "gemini_provider_message": None,
                "gemini_request_attempts": 0,
                "fallback_error": None,
            }

        probabilities = self.pipeline.predict_proba([description])[0]
        index = int(np.argmax(probabilities))
        ml_category = str(self.pipeline.classes_[index])
        ml_confidence = float(probabilities[index])
        result = {
            "transaction_description": description,
            "category": ml_category,
            "confidence": ml_confidence,
            "source": "ml",
            "fallback_used": False,
            "fallback_status": "not_used",
            "ml_category": ml_category,
            "ml_confidence": ml_confidence,
            "gemini_category": None,
            "gemini_confidence": None,
            "gemini_reason": None,
            "gemini_attempted": False,
            "gemini_exception_type": None,
            "gemini_http_status_code": None,
            "gemini_provider_message": None,
            "gemini_request_attempts": 0,
            "fallback_error": None,
        }
        if ml_confidence >= threshold:
            return result

        result["fallback_used"] = True
        result["gemini_attempted"] = True
        gemini = self.gemini_classifier(description, self.allowed_categories)
        result["gemini_request_attempts"] = int(gemini.get("gemini_request_attempts", 1))
        if not gemini.get("ok"):
            result["fallback_error"] = str(gemini.get("error_code", "gemini_api_error"))
            result["fallback_status"] = (
                "rate_limited" if result["fallback_error"] == "gemini_rate_limited" else "gemini_unavailable"
            )
            result["gemini_exception_type"] = gemini.get("gemini_exception_type")
            result["gemini_http_status_code"] = gemini.get("gemini_http_status_code")
            result["gemini_provider_message"] = gemini.get("gemini_provider_message")
            return result
        result.update(
            {
                "category": gemini["category"],
                "confidence": float(gemini["confidence"]),
                "source": "gemini",
                "fallback_status": "gemini",
                "gemini_category": gemini["category"],
                "gemini_confidence": float(gemini["confidence"]),
                "gemini_reason": gemini["reason"],
            }
        )
        return result
