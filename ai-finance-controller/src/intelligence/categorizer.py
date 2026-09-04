"""Transaction Categorization enrichment using the persisted Phase 1 ML pipeline."""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import joblib
import pandas as pd


class CategorizationEnricher:
    """Enriches transactions with category and confidence from the persisted ML model."""

    def __init__(self, model_path: str | Path = "models/categorization_pipeline.joblib"):
        self.model_path = Path(model_path)
        self.pipeline = None
        self.classes = None
        self._load_model()

    def _load_model(self) -> None:
        """Safely load the persisted categorization pipeline."""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Categorization model not found at: {self.model_path}")
        self.pipeline = joblib.load(self.model_path)
        if hasattr(self.pipeline, "classes_"):
            self.classes = list(self.pipeline.classes_)

    def predict(self, description: Optional[str]) -> Dict[str, Any]:
        """Categorize a transaction description without modifying any reconciliation fields.

        Returns:
            Dict containing:
                - category: predicted category name (or 'Unknown')
                - categorization_confidence: float probability (0.0 to 1.0)
                - categorization_source: 'local_ml' (or 'fallback_unknown')
                - categorization_reason: explanation of inference result
        """
        if (
            not description
            or not isinstance(description, str)
            or not description.strip()
            or description.strip().lower() in {"nan", "none", "null", "unknown"}
        ):
            return {
                "category": "Unknown",
                "categorization_confidence": 0.0,
                "categorization_source": "fallback_unknown",
                "categorization_reason": "No usable transaction description provided for categorization.",
            }

        text = description.strip()
        try:
            probs = self.pipeline.predict_proba([text])[0]
            best_idx = probs.argmax()
            best_category = self.classes[best_idx] if self.classes else str(self.pipeline.predict([text])[0])
            confidence = float(probs[best_idx])

            return {
                "category": best_category,
                "categorization_confidence": round(confidence, 4),
                "categorization_source": "local_ml",
                "categorization_reason": f"Classified by local TF-IDF + Logistic Regression model ({confidence * 100:.1f}% confidence).",
            }
        except Exception as e:
            return {
                "category": "Unknown",
                "categorization_confidence": 0.0,
                "categorization_source": "error_fallback",
                "categorization_reason": f"Model inference error on description '{text}': {str(e)}",
            }
