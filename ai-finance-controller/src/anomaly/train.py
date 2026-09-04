"""Train and evaluate the reproducible Phase 3 Isolation Forest detector."""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.anomaly.evaluate import evaluate_anomalies
from src.anomaly.preprocess import AnomalyFeatureBuilder, REQUIRED_COLUMNS


def build_anomaly_pipeline(
    categorization_model_path: str | Path = "models/categorization_pipeline.joblib",
    contamination: float = 0.10,
    random_state: int = 42,
) -> Pipeline:
    """Build the persisted feature/scaling/Isolation Forest pipeline."""
    if not 0.0 < contamination < 0.5:
        raise ValueError("contamination must be between 0 and 0.5")
    return Pipeline(
        [
            ("features", AnomalyFeatureBuilder(categorization_model_path=categorization_model_path)),
            ("scaler", StandardScaler()),
            ("isolation_forest", IsolationForest(contamination=contamination, random_state=random_state, n_estimators=200)),
        ]
    )


def _flags_from_pipeline(pipeline: Pipeline, data: pd.DataFrame) -> np.ndarray:
    """Translate sklearn's -1 / 1 convention into 1 anomaly / 0 normal."""
    return (pipeline.predict(data) == -1).astype(int)


def train_and_evaluate_anomaly_detector(
    data_path: str | Path = "data/raw/transactions_v2.csv",
    categorization_model_path: str | Path = "models/categorization_pipeline.joblib",
    model_path: str | Path = "models/anomaly_detector_pipeline.joblib",
    metrics_path: str | Path = "evaluation/phase3_anomaly_metrics.json",
    test_size: float = 0.25,
    contamination: float = 0.10,
    random_state: int = 42,
) -> Tuple[Pipeline, Dict[str, Any]]:
    """Fit only on train rows, then benchmark against requires_review when available."""
    raw = pd.read_csv(data_path)
    missing = REQUIRED_COLUMNS - set(raw.columns)
    if missing:
        raise ValueError(f"Dataset is missing required anomaly columns: {sorted(missing)}")
    X = raw.copy()
    label_available = "requires_review" in raw.columns
    split_labels = raw["requires_review"] if label_available and raw["requires_review"].value_counts().min() >= 2 else None
    train_data, test_data = train_test_split(X, test_size=test_size, random_state=random_state, stratify=split_labels)
    pipeline = build_anomaly_pipeline(categorization_model_path, contamination, random_state)
    pipeline.fit(train_data)
    flags = _flags_from_pipeline(pipeline, test_data)

    # Transparent baseline: a global raw-amount percentile fitted on train data.
    baseline_cutoff = float(train_data["amount"].quantile(1.0 - contamination))
    baseline_flags = (test_data["amount"] >= baseline_cutoff).astype(int).to_numpy()
    metrics: Dict[str, Any] = {
        "configuration": {
            "random_state": random_state, "test_size": test_size, "contamination": contamination,
            "label": "requires_review" if label_available else None,
            "feature_names": pipeline.named_steps["features"].feature_names_out_,
            "category_feature_source": "Phase 1 predicted category; raw ground-truth category is excluded",
        },
        "split": {"train_rows": int(len(train_data)), "test_rows": int(len(test_data))},
        "isolation_forest": {"anomalies_detected": int(flags.sum())},
        "global_amount_baseline": {"threshold": baseline_cutoff, "anomalies_detected": int(baseline_flags.sum())},
    }
    if label_available:
        y_test = test_data["requires_review"].to_numpy()
        metrics["isolation_forest"]["evaluation"] = evaluate_anomalies(y_test, flags)
        metrics["global_amount_baseline"]["evaluation"] = evaluate_anomalies(y_test, baseline_flags)
        salary_normal = test_data["category"].eq("Salary") & test_data["requires_review"].eq(0)
        metrics["salary_legitimate_high_value_false_positive_rate"] = {
            "eligible_rows": int(salary_normal.sum()),
            "isolation_forest": float(flags[salary_normal.to_numpy()].mean()) if salary_normal.any() else None,
            "global_amount_baseline": float(baseline_flags[salary_normal.to_numpy()].mean()) if salary_normal.any() else None,
        }
    else:
        metrics["evaluation_note"] = "No legitimate anomaly label is available; precision, recall, and F1 are not claimed."

    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_path)
    Path(metrics_path).parent.mkdir(parents=True, exist_ok=True)
    Path(metrics_path).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return pipeline, metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Phase 3 Isolation Forest anomaly detector")
    parser.add_argument("--data", default="data/raw/transactions_v2.csv")
    parser.add_argument("--categorization-model", default="models/categorization_pipeline.joblib")
    parser.add_argument("--model", default="models/anomaly_detector_pipeline.joblib")
    parser.add_argument("--metrics-output", default="evaluation/phase3_anomaly_metrics.json")
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--contamination", type=float, default=0.10)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    _, metrics = train_and_evaluate_anomaly_detector(
        args.data, args.categorization_model, args.model, args.metrics_output,
        args.test_size, args.contamination, args.random_state,
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
