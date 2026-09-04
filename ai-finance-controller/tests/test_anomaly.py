"""Unit tests for Phase 3 category-relative Isolation Forest features."""

import joblib
import numpy as np
import pandas as pd

from src.anomaly.preprocess import AnomalyFeatureBuilder
from src.anomaly.train import build_anomaly_pipeline


class DummyCategorizer:
    classes_ = np.array(["Food", "Salary"])

    def predict_proba(self, descriptions):
        return np.array([[0.95, 0.05] if "food" in text.lower() else [0.10, 0.90] for text in descriptions])


def anomaly_frame():
    return pd.DataFrame(
        {
            "transaction_description": ["food one", "food two", "salary one", "salary two", "food three", "salary three"],
            "amount": [10.0, 10.0, 1000.0, 1000.0, 30.0, 2000.0],
            "hour": [23, 0, 12, 13, 1, 11],
            "is_new_merchant_for_customer": [False, True, False, False, True, False],
            "customer_txn_count_so_far": [1, 2, 3, 4, 5, 6],
            "days_since_last_transaction": [1, 2, 3, 4, 5, 6],
        }
    )


def feature_builder(tmp_path):
    model_path = tmp_path / "categorizer.joblib"
    joblib.dump(DummyCategorizer(), model_path)
    return AnomalyFeatureBuilder(model_path)


def test_category_relative_zscore_handles_zero_variance(tmp_path):
    builder = feature_builder(tmp_path).fit(anomaly_frame().iloc[:4])
    features = builder.transform(anomaly_frame().iloc[:4])
    assert np.isfinite(features).all()
    assert np.allclose(features[:, 1], 0.0)


def test_category_relative_amount_uses_predicted_category(tmp_path):
    builder = feature_builder(tmp_path).fit(anomaly_frame())
    features = builder.transform(anomaly_frame())
    # Salary 1,000 is typical for Salary while it would be globally extreme.
    assert abs(features[2, 1]) < abs((1000.0 - anomaly_frame()["amount"].mean()) / anomaly_frame()["amount"].std())


def test_midnight_is_cyclic_not_distant_from_23(tmp_path):
    builder = feature_builder(tmp_path).fit(anomaly_frame())
    features = builder.transform(anomaly_frame())
    hour_23, hour_0, hour_12 = features[0, 2:4], features[1, 2:4], features[2, 2:4]
    assert np.linalg.norm(hour_23 - hour_0) < np.linalg.norm(hour_23 - hour_12)


def test_pipeline_training_and_predictions_are_deterministic(tmp_path):
    builder = feature_builder(tmp_path)
    model_path = tmp_path / "categorizer.joblib"
    first = build_anomaly_pipeline(model_path, contamination=0.2, random_state=42).fit(anomaly_frame())
    second = build_anomaly_pipeline(model_path, contamination=0.2, random_state=42).fit(anomaly_frame())
    assert np.array_equal(first.predict(anomaly_frame()), second.predict(anomaly_frame()))
    assert set(first.predict(anomaly_frame())) <= {-1, 1}


def test_categories_with_one_transaction_are_safe(tmp_path):
    frame = anomaly_frame().iloc[:2].copy()
    frame.loc[1, "transaction_description"] = "salary only"
    builder = feature_builder(tmp_path).fit(frame)
    assert np.isfinite(builder.transform(frame)).all()
