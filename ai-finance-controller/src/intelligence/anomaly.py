"""Isolation Forest risk/anomaly enrichment using the persisted Phase 3 ML pipeline contract."""

from pathlib import Path
from typing import Dict, Any, Optional
import joblib
import pandas as pd


REQUIRED_ANOMALY_COLUMNS = {
    "transaction_description",
    "amount",
    "hour",
    "is_new_merchant_for_customer",
    "customer_txn_count_so_far",
    "days_since_last_transaction",
}


class AnomalyEnricher:
    """Evaluates transaction risk using the persisted Isolation Forest anomaly detection model.

    Adheres strictly to the schema contract. If required customer history features are absent,
    gracefully marks anomaly status as 'unavailable' without fabricating fake inputs.
    """

    def __init__(self, model_path: str | Path = "models/anomaly_detector_pipeline.joblib"):
        self.model_path = Path(model_path)
        self.pipeline = None
        self.is_loaded = False
        self._try_load_model()

    def _try_load_model(self) -> None:
        """Attempt to load the persisted anomaly detection pipeline."""
        if self.model_path.exists():
            try:
                self.pipeline = joblib.load(self.model_path)
                self.is_loaded = True
            except Exception as e:
                self.is_loaded = False
                self.load_error = str(e)
        else:
            self.is_loaded = False
            self.load_error = f"Model file not found at {self.model_path}"

    def score_transaction(
        self,
        transaction_data: Dict[str, Any],
        is_exception: bool = True,
    ) -> Dict[str, Any]:
        """Evaluate secondary anomaly signal for a transaction record.

        Args:
            transaction_data: Dictionary containing available transaction features.
            is_exception: Whether this record is an exception (AMOUNT_MISMATCH, AMBIGUOUS, DUPLICATE, UNMATCHED).

        Returns:
            Dict containing:
                - anomaly_flag: bool (True if anomalous, False otherwise)
                - anomaly_score: Optional[float] (higher = more anomalous)
                - anomaly_status: 'available' | 'unavailable' | 'skipped_match'
                - anomaly_reason: explainable reason for signal status
        """
        # Check feature availability
        available_cols = set(transaction_data.keys())
        missing_cols = REQUIRED_ANOMALY_COLUMNS - available_cols

        if missing_cols:
            return {
                "anomaly_flag": False,
                "anomaly_score": None,
                "anomaly_status": "unavailable",
                "anomaly_reason": (
                    f"Required historical feature(s) {sorted(list(missing_cols))} "
                    "are unavailable in the reconciliation dataset schema."
                ),
            }

        # If model is not loaded
        if not self.is_loaded or self.pipeline is None:
            return {
                "anomaly_flag": False,
                "anomaly_score": None,
                "anomaly_status": "unavailable",
                "anomaly_reason": f"Anomaly detection model unavailable ({getattr(self, 'load_error', 'Not loaded')}).",
            }

        # If feature contract is fully satisfied, perform inference
        try:
            frame = pd.DataFrame([transaction_data])
            prediction = self.pipeline.predict(frame)[0]
            is_anomaly = bool(prediction == -1)
            raw_score = float(-self.pipeline.score_samples(frame)[0])

            return {
                "anomaly_flag": is_anomaly,
                "anomaly_score": round(raw_score, 4),
                "anomaly_status": "available",
                "anomaly_reason": (
                    "Elevated risk signal detected by Isolation Forest model."
                    if is_anomaly
                    else "Normal transaction risk pattern within expected envelope."
                ),
            }
        except Exception as e:
            return {
                "anomaly_flag": False,
                "anomaly_score": None,
                "anomaly_status": "error",
                "anomaly_reason": f"Anomaly inference failed: {str(e)}",
            }
