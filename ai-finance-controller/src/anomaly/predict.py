"""Inference helpers for the persisted Phase 3 anomaly pipeline."""

from pathlib import Path
from typing import Any, Dict

import joblib
import pandas as pd


def predict_anomaly(transaction: Dict[str, Any], model_path: str | Path = "models/anomaly_detector_pipeline.joblib") -> Dict[str, Any]:
    """Score one transaction dictionary with the persisted anomaly pipeline."""
    pipeline = joblib.load(model_path)
    frame = pd.DataFrame([transaction])
    is_anomaly = bool(pipeline.predict(frame)[0] == -1)
    score = float(-pipeline.score_samples(frame)[0])
    return {"is_anomaly": is_anomaly, "anomaly_score": score}
