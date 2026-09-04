"""Unit tests for Day 3 Supporting Intelligence & ML Enrichment.

Tests all 12 required intelligence and enrichment test specifications using controlled fixtures.
"""

from pathlib import Path
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from src.intelligence.categorizer import CategorizationEnricher
from src.intelligence.anomaly import AnomalyEnricher
from src.intelligence.priority import ExceptionPriorityEngine
from src.intelligence.enricher import IntelligencePipeline


# ==============================================================================
# TEST FIXTURES
# ==============================================================================

@pytest.fixture
def categorizer():
    return CategorizationEnricher("models/categorization_pipeline.joblib")


@pytest.fixture
def anomaly_enricher():
    return AnomalyEnricher("models/anomaly_detector_pipeline.joblib")


@pytest.fixture
def priority_engine():
    return ExceptionPriorityEngine()


@pytest.fixture
def sample_predictions_df():
    return pd.DataFrame([
        {
            "bank_txn_id": "BANK-001",
            "ledger_id": "LEDGER-001",
            "predicted_status": "MATCH",
            "match_confidence": 1.0,
            "match_method": "EXACT_REFERENCE_AMOUNT",
            "reason": "Exact match on reference, amount, and direction.",
            "amount_difference": 0.0,
            "timestamp_difference": 5.0,
            "merchant_similarity": 1.0,
            "reference_similarity": 1.0,
        },
        {
            "bank_txn_id": "BANK-002",
            "ledger_id": "LEDGER-002",
            "predicted_status": "AMOUNT_MISMATCH",
            "match_confidence": 0.95,
            "match_method": "REFERENCE_AMOUNT_MISMATCH",
            "reason": "Amount discrepancy of ₹1200.00.",
            "amount_difference": 1200.0,
            "timestamp_difference": 10.0,
            "merchant_similarity": 1.0,
            "reference_similarity": 1.0,
        },
        {
            "bank_txn_id": "BANK-003",
            "ledger_id": "LEDGER-003",
            "predicted_status": "DUPLICATE",
            "match_confidence": 1.0,
            "match_method": "DUPLICATE_MULTIPLE_BANK",
            "reason": "Duplicate bank transaction detected.",
            "amount_difference": 0.0,
            "timestamp_difference": 0.0,
            "merchant_similarity": 1.0,
            "reference_similarity": 1.0,
        },
        {
            "bank_txn_id": "BANK-004",
            "ledger_id": "LEDGER-004",
            "predicted_status": "AMBIGUOUS",
            "match_confidence": 0.75,
            "match_method": "AMBIGUOUS_MULTI_CANDIDATE",
            "reason": "Ambiguous candidate match.",
            "amount_difference": 50.0,
            "timestamp_difference": 30.0,
            "merchant_similarity": 1.0,
            "reference_similarity": 0.89,
        },
        {
            "bank_txn_id": "BANK-005",
            "ledger_id": None,
            "predicted_status": "UNMATCHED_BANK",
            "match_confidence": 0.0,
            "match_method": "UNMATCHED_NO_CANDIDATE",
            "reason": "No compatible candidate found.",
            "amount_difference": None,
            "timestamp_difference": None,
            "merchant_similarity": None,
            "reference_similarity": None,
        },
    ])


@pytest.fixture
def sample_bank_df():
    return pd.DataFrame([
        {"bank_txn_id": "BANK-001", "merchant": "SWIGGY*BLR", "amount": 500.0},
        {"bank_txn_id": "BANK-002", "merchant": "FLIPKART", "amount": 2500.0},
        {"bank_txn_id": "BANK-003", "merchant": "UBER", "amount": 300.0},
        {"bank_txn_id": "BANK-004", "merchant": "BOOKMYSHOW", "amount": 400.0},
        {"bank_txn_id": "BANK-005", "merchant": "RELIANCE DIGITAL", "amount": 8000.0},
    ])


# ==============================================================================
# TEST SUITE
# ==============================================================================

def test_categorization_enrichment(categorizer):
    """1. Test categorization enrichment predicts expected category."""
    res = categorizer.predict("SWIGGY*BLR0091 BANGALORE")
    assert res["category"] == "Food"
    assert res["categorization_confidence"] > 0.90
    assert res["categorization_source"] == "local_ml"


def test_missing_description_handling(categorizer):
    """2. Test missing/empty description gracefully returns Unknown with 0 confidence."""
    res1 = categorizer.predict("")
    assert res1["category"] == "Unknown"
    assert res1["categorization_confidence"] == 0.0
    assert "No usable transaction description" in res1["categorization_reason"]

    res2 = categorizer.predict(None)
    assert res2["category"] == "Unknown"
    assert res2["categorization_confidence"] == 0.0


def test_categorization_confidence_propagation(categorizer):
    """3. Test categorization confidence is propagated as a float between 0 and 1."""
    res = categorizer.predict("ZOMATO")
    assert isinstance(res["categorization_confidence"], float)
    assert 0.0 <= res["categorization_confidence"] <= 1.0


def test_anomaly_model_loading(anomaly_enricher):
    """4. Test anomaly enricher handles model availability gracefully."""
    assert isinstance(anomaly_enricher, AnomalyEnricher)


def test_anomaly_unavailable_handling(anomaly_enricher):
    """5. Test anomaly scoring marks status as unavailable when required features are missing."""
    partial_payload = {"transaction_description": "SWIGGY", "amount": 500.0}
    res = anomaly_enricher.score_transaction(partial_payload)

    assert res["anomaly_status"] == "unavailable"
    assert res["anomaly_flag"] is False
    assert res["anomaly_score"] is None
    assert "Required historical feature(s)" in res["anomaly_reason"]


def test_anomaly_flag_propagation(anomaly_enricher):
    """6. Test anomaly flag structure and boolean type."""
    res = anomaly_enricher.score_transaction({"description": "Test"})
    assert isinstance(res["anomaly_flag"], bool)


def test_exception_only_anomaly_scoring(priority_engine):
    """7. Test exception priority rules for anomaly-flagged transactions."""
    priority, reasons = priority_engine.evaluate_priority(
        predicted_status="MATCH",
        anomaly_flag=True,
        bank_amount=500.0,
    )
    assert priority == "HIGH"
    assert "anomaly_flag=True" in reasons


def test_priority_calculation(priority_engine):
    """8. Test transparent priority calculation for different exception types."""
    # Large AMOUNT_MISMATCH (>= 1000 INR) -> HIGH
    p1, _ = priority_engine.evaluate_priority("AMOUNT_MISMATCH", amount_difference=1500.0)
    assert p1 == "HIGH"

    # Small AMOUNT_MISMATCH (< 1000 INR) -> MEDIUM
    p2, _ = priority_engine.evaluate_priority("AMOUNT_MISMATCH", amount_difference=250.0)
    assert p2 == "MEDIUM"

    # DUPLICATE -> HIGH
    p3, _ = priority_engine.evaluate_priority("DUPLICATE", bank_amount=1000.0)
    assert p3 == "HIGH"

    # AMBIGUOUS -> MEDIUM
    p4, _ = priority_engine.evaluate_priority("AMBIGUOUS", bank_amount=1000.0)
    assert p4 == "MEDIUM"

    # UNMATCHED_BANK large (>= 5000) -> HIGH
    p5, _ = priority_engine.evaluate_priority("UNMATCHED_BANK", bank_amount=6000.0)
    assert p5 == "HIGH"

    # UNMATCHED_BANK small (< 1000) -> LOW
    p6, _ = priority_engine.evaluate_priority("UNMATCHED_BANK", bank_amount=500.0)
    assert p6 == "LOW"

    # Normal MATCH -> LOW
    p7, _ = priority_engine.evaluate_priority("MATCH", bank_amount=500.0)
    assert p7 == "LOW"


def test_priority_reason_generation(priority_engine):
    """9. Test priority reason is human-readable and explains the assigned level."""
    _, reasons = priority_engine.evaluate_priority(
        predicted_status="AMOUNT_MISMATCH",
        amount_difference=1250.0,
        bank_amount=2000.0,
    )
    assert "AMOUNT_MISMATCH" in reasons
    assert "₹1250.00" in reasons
    assert "₹1,000 threshold" in reasons


def test_reconciliation_status_cannot_be_overridden_by_ml(sample_predictions_df, sample_bank_df):
    """10. Test that ML intelligence enrichment NEVER overrides reconciliation status."""
    pipeline = IntelligencePipeline()
    original_statuses = sample_predictions_df["predicted_status"].tolist()

    df_enriched = pipeline.enrich_predictions(sample_predictions_df, df_bank=sample_bank_df)
    enriched_statuses = df_enriched["predicted_status"].tolist()

    assert enriched_statuses == original_statuses
    for i, row in df_enriched.iterrows():
        assert row["predicted_status"] == original_statuses[i]


def test_ground_truth_is_not_required_for_inference(sample_predictions_df, sample_bank_df):
    """11. Test that intelligence enrichment works with zero dependency on ground truth."""
    pipeline = IntelligencePipeline()
    df_enriched = pipeline.enrich_predictions(sample_predictions_df, df_bank=sample_bank_df)
    assert "category" in df_enriched.columns
    assert "priority" in df_enriched.columns
    assert "anomaly_status" in df_enriched.columns
    assert len(df_enriched) == len(sample_predictions_df)


def test_deterministic_enrichment_behavior(sample_predictions_df, sample_bank_df):
    """12. Test that intelligence enrichment is 100% deterministic across repeated runs."""
    pipeline = IntelligencePipeline()
    run1 = pipeline.enrich_predictions(sample_predictions_df, df_bank=sample_bank_df)
    run2 = pipeline.enrich_predictions(sample_predictions_df, df_bank=sample_bank_df)
    assert_frame_equal(run1, run2)
