"""Evaluation helpers for Phase 3 anomaly detection."""

from typing import Any, Dict

import numpy as np
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score


def evaluate_anomalies(y_true: np.ndarray, anomaly_flags: np.ndarray) -> Dict[str, Any]:
    """Evaluate flags against the synthetic requires_review benchmark label."""
    y_true = np.asarray(y_true, dtype=int)
    flags = np.asarray(anomaly_flags, dtype=int)
    matrix = confusion_matrix(y_true, flags, labels=[0, 1])
    return {
        "precision": float(precision_score(y_true, flags, zero_division=0)),
        "recall": float(recall_score(y_true, flags, zero_division=0)),
        "f1": float(f1_score(y_true, flags, zero_division=0)),
        "confusion_matrix": matrix.tolist(),
        "labels": ["normal", "requires_review"],
        "anomalies_detected": int(flags.sum()),
        "total_rows": int(len(flags)),
    }
