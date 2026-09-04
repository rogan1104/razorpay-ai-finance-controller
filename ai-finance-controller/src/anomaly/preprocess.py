"""Feature engineering for the Isolation Forest anomaly detector."""

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin


REQUIRED_COLUMNS = {
    "transaction_description", "amount", "hour", "is_new_merchant_for_customer",
    "customer_txn_count_so_far", "days_since_last_transaction",
}


class AnomalyFeatureBuilder(BaseEstimator, TransformerMixin):
    """Build numeric, category-relative features using predicted—not true—category."""

    def __init__(
        self,
        categorization_model_path: str | Path = "models/categorization_pipeline.joblib",
        recognition_threshold: float = 0.70,
        minimum_category_std: float = 1e-6,
    ) -> None:
        self.categorization_model_path = str(categorization_model_path)
        self.recognition_threshold = recognition_threshold
        self.minimum_category_std = minimum_category_std

    def _validate(self, data: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Anomaly features require a pandas DataFrame.")
        missing = REQUIRED_COLUMNS - set(data.columns)
        if missing:
            raise ValueError(f"Missing anomaly feature columns: {sorted(missing)}")
        return data.copy()

    def _categorize(self, data: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        probabilities = self.categorizer_.predict_proba(data["transaction_description"].fillna("").astype(str))
        best_indices = probabilities.argmax(axis=1)
        categories = np.asarray(self.categorizer_.classes_)[best_indices]
        confidences = probabilities.max(axis=1)
        return categories, confidences

    def fit(self, X: pd.DataFrame, y: Any = None) -> "AnomalyFeatureBuilder":
        data = self._validate(X)
        self.categorizer_ = joblib.load(self.categorization_model_path)
        categories, _ = self._categorize(data)
        amounts = pd.to_numeric(data["amount"], errors="coerce").fillna(0.0)
        grouped = pd.DataFrame({"predicted_category": categories, "amount": amounts}).groupby("predicted_category")["amount"]
        self.category_amount_mean_ = grouped.mean().to_dict()
        std = grouped.std(ddof=0).fillna(0.0)
        self.category_amount_std_ = std.where(std.abs() >= self.minimum_category_std, 1.0).to_dict()
        self.feature_names_in_ = np.array(sorted(REQUIRED_COLUMNS))
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        if not hasattr(self, "categorizer_"):
            raise RuntimeError("AnomalyFeatureBuilder must be fitted before transform.")
        data = self._validate(X)
        categories, recognition_confidence = self._categorize(data)
        amounts = pd.to_numeric(data["amount"], errors="coerce").fillna(0.0).clip(lower=0.0)
        means = pd.Series(categories, index=data.index).map(self.category_amount_mean_).fillna(float(amounts.mean()))
        stds = pd.Series(categories, index=data.index).map(self.category_amount_std_).fillna(1.0).clip(lower=self.minimum_category_std)
        category_zscore = (amounts - means) / stds
        hours = pd.to_numeric(data["hour"], errors="coerce").fillna(0.0).mod(24.0)
        radians = 2.0 * np.pi * hours / 24.0
        new_merchant = data["is_new_merchant_for_customer"].astype(float)
        customer_count = pd.to_numeric(data["customer_txn_count_so_far"], errors="coerce").fillna(0.0).clip(lower=0.0)
        days_since_last = pd.to_numeric(data["days_since_last_transaction"], errors="coerce").fillna(0.0).clip(lower=0.0)
        return np.column_stack(
            [
                np.log1p(amounts),
                category_zscore,
                np.sin(radians),
                np.cos(radians),
                recognition_confidence,
                (recognition_confidence >= self.recognition_threshold).astype(float),
                new_merchant,
                np.log1p(customer_count),
                np.log1p(days_since_last),
            ]
        )

    @property
    def feature_names_out_(self) -> list[str]:
        return [
            "log_amount", "predicted_category_amount_zscore", "hour_sin", "hour_cos",
            "recognition_confidence", "confidently_recognized", "is_new_merchant_for_customer",
            "log_customer_txn_count", "log_days_since_last_transaction",
        ]
