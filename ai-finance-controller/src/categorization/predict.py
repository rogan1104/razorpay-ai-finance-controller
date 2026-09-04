"""Inference and prediction module for transaction categorization."""

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import joblib
import numpy as np

from src.categorization.preprocess import clean_text


class TransactionClassifier:
    """Inference wrapper for trained transaction categorization pipeline."""

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = "models/categorization_pipeline.joblib",
        pipeline: Optional[Any] = None,
    ) -> None:
        """Initialize classifier with a serialized model file or an existing pipeline.

        Args:
            model_path: Path to serialized joblib model file.
            pipeline: Pre-loaded scikit-learn pipeline instance (optional).
        """
        if pipeline is not None:
            self.pipeline = pipeline
        elif model_path is not None:
            self.pipeline = self.load_model(model_path)
        else:
            raise ValueError("Either model_path or pipeline must be provided.")

    @staticmethod
    def load_model(model_path: Union[str, Path]) -> Any:
        """Load serialized pipeline from disk.

        Args:
            model_path: Path to joblib file.

        Returns:
            Loaded pipeline.

        Raises:
            FileNotFoundError: If model file does not exist.
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Model file not found at: {path.resolve()}. "
                "Please train the model first using 'python -m src.categorization.train'."
            )
        return joblib.load(path)

    def predict(self, description: Optional[str]) -> Dict[str, Any]:
        """Predict category and confidence score for a single transaction description.

        Args:
            description: Raw transaction text (e.g. 'SWIGGY*BLR0091 BANGALORE').

        Returns:
            Dictionary containing:
            - 'transaction': original input description
            - 'predicted_category': predicted category label
            - 'confidence': float score between 0.0 and 1.0 (from predict_proba)
        """
        raw_text = "" if description is None else str(description)
        cleaned = clean_text(raw_text)

        # Handle empty/missing descriptions gracefully
        if not cleaned:
            return {
                "transaction": raw_text,
                "predicted_category": "Unknown",
                "confidence": 0.0,
            }

        # Obtain class probabilities
        # The serialized pipeline owns text normalization, so independently
        # loaded models receive the same preprocessing as training data.
        probabilities = self.pipeline.predict_proba([raw_text])[0]
        max_idx = int(np.argmax(probabilities))
        predicted_category = str(self.pipeline.classes_[max_idx])
        confidence = float(probabilities[max_idx])

        return {
            "transaction": raw_text,
            "predicted_category": predicted_category,
            "confidence": round(confidence, 4),
        }

    def predict_batch(self, descriptions: List[Optional[str]]) -> List[Dict[str, Any]]:
        """Predict categories and confidence scores for a list of transaction descriptions.

        Args:
            descriptions: List of transaction strings.

        Returns:
            List of prediction dictionaries.
        """
        return [self.predict(desc) for desc in descriptions]


def predict_transaction(
    description: Optional[str],
    model_path: Union[str, Path] = "models/categorization_pipeline.joblib",
) -> Dict[str, Any]:
    """Standalone convenience function to predict a single transaction.

    Args:
        description: Raw transaction text.
        model_path: Path to saved model file.

    Returns:
        Prediction dictionary.
    """
    classifier = TransactionClassifier(model_path=model_path)
    return classifier.predict(description)


def main() -> None:
    """CLI entrypoint for inference."""
    parser = argparse.ArgumentParser(description="Predict category for a transaction description")
    parser.add_argument(
        "description",
        type=str,
        nargs="?",
        default="SWIGGY*BLR0091 BANGALORE",
        help="Transaction description string to classify",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="models/categorization_pipeline.joblib",
        help="Path to saved model artifact (default: models/categorization_pipeline.joblib)",
    )
    args = parser.parse_args()

    result = predict_transaction(args.description, model_path=args.model)
    print("\n--- Prediction Result ---")
    print(f"Transaction:        {result['transaction']}")
    print(f"Predicted category: {result['predicted_category']}")
    print(f"Confidence:         {result['confidence']:.4f}\n")


if __name__ == "__main__":
    main()
