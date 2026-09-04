"""Unit tests for the Core Reconciliation Engine (Phase 2.5).

Tests use isolated, controlled synthetic fixtures without depending on ground-truth files.
Covers original 14 test cases plus targeted regression tests for Phase 2.5 failure modes.
"""

from datetime import datetime, timedelta
import pytest

from src.reconciliation.engine import ReconciliationEngine
from src.reconciliation.normalize import (
    compute_amount_similarity,
    compute_merchant_similarity,
    compute_reference_similarity,
    compute_timestamp_proximity,
    normalize_merchant,
    normalize_reference,
)
from src.reconciliation.schemas import (
    BankRecord,
    LedgerRecord,
    MatchMethod,
    ReconciliationConfig,
    ReconciliationStatus,
)


# ==============================================================================
# TEST FIXTURES
# ==============================================================================

def make_bank_record(
    txn_id: str = "BANK-001",
    dt: datetime = datetime(2026, 6, 1, 12, 0, 0),
    amount: float = 1000.0,
    direction: str = "CREDIT",
    merchant: str = "SWIGGY*BLR",
    ref: str = "UPI-123456",
    payment_method: str = "UPI",
) -> BankRecord:
    return BankRecord(
        bank_txn_id=txn_id,
        timestamp=dt,
        amount=amount,
        direction=direction,
        merchant=merchant,
        reference=ref,
        payment_method=payment_method,
        norm_merchant=normalize_merchant(merchant),
        norm_reference=normalize_reference(ref),
    )


def make_ledger_record(
    ledger_id: str = "LEDGER-001",
    dt: datetime = datetime(2026, 6, 1, 12, 5, 0),
    amount: float = 1000.0,
    direction: str = "CREDIT",
    merchant: str = "SWIGGY",
    ref: str = "UPI123456",
    invoice_id: str = "INV-001",
) -> LedgerRecord:
    return LedgerRecord(
        ledger_id=ledger_id,
        timestamp=dt,
        amount=amount,
        direction=direction,
        merchant=merchant,
        reference=ref,
        invoice_id=invoice_id,
        norm_merchant=normalize_merchant(merchant),
        norm_reference=normalize_reference(ref),
    )


# ==============================================================================
# CORE TEST SUITE (14 ORIGINAL TESTS)
# ==============================================================================

def test_merchant_normalization():
    """1. Test merchant normalization rules (casing, trimming, punctuation, aliases)."""
    assert normalize_merchant(" swiggy*blr ") == "SWIGGY"
    assert normalize_merchant("BMS") == "BOOKMYSHOW"
    assert normalize_merchant("BookMyShow.com") == "BOOKMYSHOW"
    assert normalize_merchant("UrbanClap") == "URBAN COMPANY"
    assert normalize_merchant("Urban Company India") == "URBAN COMPANY"
    assert normalize_merchant("Domino's Pizza") == "DOMINOS"
    assert normalize_merchant("Reliance Retail Ltd") == "RELIANCE"
    assert normalize_merchant("Croma Electronics") == "CROMA"
    assert normalize_merchant("Big Basket") == "BIGBASKET"
    assert normalize_merchant("Decathlon Sports") == "DECATHLON"
    assert normalize_merchant("Apollo Pharmacy Ltd") == "APOLLO"
    assert normalize_merchant("") == ""
    assert normalize_merchant(None) == ""


def test_reference_normalization():
    """2. Test reference normalization (hyphen/space removal, uppercase, alphanumeric preservation)."""
    assert normalize_reference("UPI-156805") == "UPI156805"
    assert normalize_reference(" UPI 449836 ") == "UPI449836"
    assert normalize_reference("SYNTH-INV-000001") == "SYNTHINV000001"
    assert normalize_reference("upi-abc-123") == "UPIABC123"
    assert normalize_reference("UPI123456") != normalize_reference("UPI123457")
    assert normalize_reference("") == ""
    assert normalize_reference(None) == ""


def test_exact_match():
    """3. Test high-confidence exact match (reference, amount, direction, time)."""
    engine = ReconciliationEngine()
    bank = [make_bank_record(txn_id="B1", amount=1500.0, ref="UPI-999001", direction="CREDIT")]
    ledger = [make_ledger_record(ledger_id="L1", amount=1500.0, ref="UPI999001", direction="CREDIT")]

    results = engine.reconcile(bank, ledger)
    assert len(results) == 1
    res = results[0]
    assert res.predicted_status == ReconciliationStatus.MATCH
    assert res.bank_txn_id == "B1"
    assert res.ledger_id == "L1"
    assert res.match_confidence == 1.0
    assert res.match_method == MatchMethod.EXACT_REFERENCE_AMOUNT.value
    assert res.amount_difference == 0.0
    assert "matched exactly after normalization" in res.reason


def test_amount_mismatch():
    """4. Test unique reference match with amount difference (AMOUNT_MISMATCH)."""
    engine = ReconciliationEngine()
    bank = [make_bank_record(txn_id="B1", amount=1200.0, ref="UPI-888001", direction="DEBIT")]
    ledger = [make_ledger_record(ledger_id="L1", amount=1000.0, ref="UPI888001", direction="DEBIT")]

    results = engine.reconcile(bank, ledger)
    assert len(results) == 1
    res = results[0]
    assert res.predicted_status == ReconciliationStatus.AMOUNT_MISMATCH
    assert res.bank_txn_id == "B1"
    assert res.ledger_id == "L1"
    assert res.amount_difference == 200.0
    assert res.match_method == MatchMethod.REFERENCE_AMOUNT_MISMATCH.value
    assert "differs from ledger amount" in res.reason


def test_direction_mismatch():
    """5. Test direction mismatch prevents matching across opposite directions."""
    engine = ReconciliationEngine()
    bank = [make_bank_record(txn_id="B1", amount=500.0, ref="UPI-777001", direction="CREDIT")]
    ledger = [make_ledger_record(ledger_id="L1", amount=500.0, ref="UPI-777001", direction="DEBIT")]

    results = engine.reconcile(bank, ledger)
    assert len(results) == 2
    statuses = {r.predicted_status for r in results}
    assert ReconciliationStatus.UNMATCHED_BANK in statuses
    assert ReconciliationStatus.UNMATCHED_LEDGER in statuses


def test_timestamp_tolerance():
    """6. Test timestamp tolerance window (within window matches, outside window fails exact match)."""
    config = ReconciliationConfig(timestamp_window_days=7.0)
    engine = ReconciliationEngine(config=config)

    base_time = datetime(2026, 6, 1, 10, 0, 0)
    # Case A: Within tolerance (2 days)
    bank_a = [make_bank_record(txn_id="B_A", dt=base_time, ref="UPI-T1", amount=500.0)]
    ledger_a = [make_ledger_record(ledger_id="L_A", dt=base_time + timedelta(days=2), ref="UPIT1", amount=500.0)]
    res_a = engine.reconcile(bank_a, ledger_a)
    assert res_a[0].predicted_status == ReconciliationStatus.MATCH

    # Case B: Outside tolerance (15 days)
    bank_b = [make_bank_record(txn_id="B_B", dt=base_time, ref="UPI-T2", amount=500.0)]
    ledger_b = [make_ledger_record(ledger_id="L_B", dt=base_time + timedelta(days=15), ref="UPIT2", amount=500.0)]
    res_b = engine.reconcile(bank_b, ledger_b)
    statuses_b = {r.predicted_status for r in res_b}
    assert ReconciliationStatus.MATCH not in statuses_b


def test_fuzzy_candidate_scoring():
    """7. Test fuzzy candidate scoring formula and component calculation."""
    ref_sim = compute_reference_similarity("UPI123456", "UPI123450")
    assert 0.8 < ref_sim < 1.0

    amt_sim = compute_amount_similarity(1000.0, 950.0)
    assert amt_sim == pytest.approx(0.95, rel=1e-2)

    merch_sim = compute_merchant_similarity("SWIGGY*BLR", "SWIGGY")
    assert merch_sim == 1.0

    time_prox = compute_timestamp_proximity(
        datetime(2026, 6, 1, 10, 0),
        datetime(2026, 6, 1, 10, 30),
        max_window_seconds=86400.0,
    )
    assert time_prox > 0.95


def test_ambiguous_candidates():
    """8. Test ambiguous candidates resolution when multiple ledger records score similarly."""
    config = ReconciliationConfig(
        high_confidence_threshold=0.85,
        ambiguity_threshold=0.70,
        ambiguity_margin=0.05,
    )
    engine = ReconciliationEngine(config=config)

    base_time = datetime(2026, 6, 1, 12, 0)
    bank = [make_bank_record(txn_id="B1", dt=base_time, amount=1000.0, ref="UPI999000", merchant="AMAZON")]
    ledger = [
        make_ledger_record(ledger_id="L1", dt=base_time, amount=1000.0, ref="UPI999001", merchant="AMAZON"),
        make_ledger_record(ledger_id="L2", dt=base_time, amount=1000.0, ref="UPI999002", merchant="AMAZON"),
    ]

    results = engine.reconcile(bank, ledger)
    bank_results = [r for r in results if r.bank_txn_id == "B1"]
    assert len(bank_results) == 1
    assert bank_results[0].predicted_status == ReconciliationStatus.AMBIGUOUS
    assert "Ambiguous" in bank_results[0].reason


def test_duplicate_candidates():
    """9. Test duplicate bank transactions detection for single ledger entry."""
    engine = ReconciliationEngine()
    base_time = datetime(2026, 6, 1, 10, 0)
    b1 = make_bank_record(txn_id="SYNTH-BANK-001", dt=base_time, amount=500.0, ref="UPI-DUP1")
    b2 = make_bank_record(txn_id="SYNTH-BANK-DUP-001", dt=base_time, amount=500.0, ref="UPI-DUP1")
    l1 = make_ledger_record(ledger_id="SYNTH-LEDGER-001", dt=base_time, amount=500.0, ref="UPIDUP1")

    results = engine.reconcile([b1, b2], [l1])
    b1_res = next(r for r in results if r.bank_txn_id == "SYNTH-BANK-001")
    b2_res = next(r for r in results if r.bank_txn_id == "SYNTH-BANK-DUP-001")

    assert b1_res.predicted_status == ReconciliationStatus.MATCH
    assert b1_res.has_duplicate_submission is True
    assert b2_res.predicted_status == ReconciliationStatus.DUPLICATE
    assert b2_res.duplicate_of_bank_txn_id == "SYNTH-BANK-001"


def test_unmatched_bank_transaction():
    """10. Test unmatched bank transaction with no counterpart."""
    engine = ReconciliationEngine()
    bank = [make_bank_record(txn_id="B_ORPHAN", amount=9999.0, ref="UPI-ORPHAN-BANK")]
    ledger = [make_ledger_record(ledger_id="L_OTHER", amount=100.0, ref="UPI-OTHER")]

    results = engine.reconcile(bank, ledger)
    bank_orphan = next(r for r in results if r.bank_txn_id == "B_ORPHAN")
    assert bank_orphan.predicted_status == ReconciliationStatus.UNMATCHED_BANK
    assert bank_orphan.ledger_id is None
    assert bank_orphan.match_confidence == 0.0


def test_unmatched_ledger_transaction():
    """11. Test unmatched ledger transaction with no counterpart."""
    engine = ReconciliationEngine()
    bank = [make_bank_record(txn_id="B_OTHER", amount=100.0, ref="UPI-OTHER")]
    ledger = [make_ledger_record(ledger_id="L_ORPHAN", amount=9999.0, ref="UPI-ORPHAN-LEDGER")]

    results = engine.reconcile(bank, ledger)
    ledger_orphan = next(r for r in results if r.ledger_id == "L_ORPHAN" and r.bank_txn_id is None)
    assert ledger_orphan.predicted_status == ReconciliationStatus.UNMATCHED_LEDGER
    assert ledger_orphan.bank_txn_id is None
    assert ledger_orphan.match_confidence == 0.0


def test_one_to_one_consumption():
    """12. Test one-to-one consumption prevents double-counting."""
    engine = ReconciliationEngine()
    b1 = make_bank_record(txn_id="B1", amount=500.0, ref="UPI-MATCH-1")
    b2 = make_bank_record(txn_id="B2", amount=500.0, ref="UPI-MATCH-2")
    l1 = make_ledger_record(ledger_id="L1", amount=500.0, ref="UPIMATCH1")

    results = engine.reconcile([b1, b2], [l1])
    b1_res = next(r for r in results if r.bank_txn_id == "B1")
    b2_res = next(r for r in results if r.bank_txn_id == "B2")

    assert b1_res.predicted_status == ReconciliationStatus.MATCH
    assert b1_res.ledger_id == "L1"
    assert b2_res.predicted_status == ReconciliationStatus.UNMATCHED_BANK


def test_explainable_reason_generation():
    """13. Test explainable human-readable reason generation for all outcomes."""
    engine = ReconciliationEngine()
    b1 = make_bank_record(txn_id="B1", amount=1000.0, ref="UPI100", direction="CREDIT")
    l1 = make_ledger_record(ledger_id="L1", amount=1000.0, ref="UPI100", direction="CREDIT")

    results = engine.reconcile([b1], [l1])
    reason = results[0].reason
    assert len(reason) > 20
    assert "AI predicted this" not in reason
    assert "matched exactly" in reason


def test_deterministic_results():
    """14. Test deterministic execution produces bit-identical results across multiple runs."""
    config = ReconciliationConfig()
    engine1 = ReconciliationEngine(config=config)
    engine2 = ReconciliationEngine(config=config)

    bank = [
        make_bank_record(txn_id="B1", amount=100.0, ref="UPI1"),
        make_bank_record(txn_id="B2", amount=200.0, ref="UPI2"),
    ]
    ledger = [
        make_ledger_record(ledger_id="L1", amount=100.0, ref="UPI1"),
        make_ledger_record(ledger_id="L2", amount=250.0, ref="UPI2"),
    ]

    res1 = [r.to_dict() for r in engine1.reconcile(bank, ledger)]
    res2 = [r.to_dict() for r in engine2.reconcile(bank, ledger)]
    assert res1 == res2


# ==============================================================================
# PHASE 2.5 TARGETED REGRESSION TESTS
# ==============================================================================

def test_phase25_fuzzy_discrepancy_is_ambiguous():
    """15. Phase 2.5: Fuzzy candidate with both ref typo and differing amount is AMBIGUOUS."""
    engine = ReconciliationEngine()
    base_time = datetime(2026, 6, 1, 10, 0)
    # Reference differs by 1 digit and amount differs by 2%
    bank = [make_bank_record(txn_id="B1", dt=base_time, amount=669.73, ref="UPI724185", merchant="IRCTC")]
    ledger = [make_ledger_record(ledger_id="L1", dt=base_time, amount=656.34, ref="UPI724186", merchant="IRCTC")]

    results = engine.reconcile(bank, ledger)
    b1_res = next(r for r in results if r.bank_txn_id == "B1")
    assert b1_res.predicted_status == ReconciliationStatus.AMBIGUOUS
    assert b1_res.match_method == MatchMethod.AMBIGUOUS_FUZZY_DISCREPANCY.value


def test_phase25_weak_fuzzy_candidate_remains_unmatched():
    """16. Phase 2.5: Weak candidate (low ref sim and differing amount) becomes UNMATCHED_BANK."""
    engine = ReconciliationEngine()
    base_time = datetime(2026, 6, 1, 10, 0)
    # Low ref similarity (0.55) and differing amount should not trigger false AMBIGUOUS
    bank = [make_bank_record(txn_id="B1", dt=base_time, amount=854.06, ref="UPI528519", merchant="Big Basket")]
    ledger = [make_ledger_record(ledger_id="L1", dt=base_time, amount=1213.98, ref="UPI619004", merchant="BIGBASKET")]

    results = engine.reconcile(bank, ledger)
    b1_res = next(r for r in results if r.bank_txn_id == "B1")
    assert b1_res.predicted_status == ReconciliationStatus.UNMATCHED_BANK
    assert b1_res.match_method == MatchMethod.UNMATCHED_NO_CANDIDATE.value


def test_phase25_distinct_transactions_with_same_ref_months_apart_not_duplicate():
    """17. Phase 2.5: Transactions 1.5 months apart with different amounts are distinct, not duplicates."""
    engine = ReconciliationEngine()
    # Same merchant & ref token, but 1.5 months apart with completely different amounts
    b1 = make_bank_record(txn_id="B1", dt=datetime(2026, 5, 12, 10, 29), amount=1666.23, ref="UPI918816", merchant="SWIGGY*BLR")
    b2 = make_bank_record(txn_id="B2", dt=datetime(2026, 6, 28, 22, 3), amount=733.48, ref="UPI918816", merchant="SWIGGY")
    l1 = make_ledger_record(ledger_id="L1", dt=datetime(2026, 5, 12, 10, 39), amount=1666.23, ref="UPI918816", merchant="Swiggy India")
    l2 = make_ledger_record(ledger_id="L2", dt=datetime(2026, 6, 28, 22, 3), amount=733.48, ref="UPI918816", merchant="SWIGGY*BLR")

    results = engine.reconcile([b1, b2], [l1, l2])
    b1_res = next(r for r in results if r.bank_txn_id == "B1")
    b2_res = next(r for r in results if r.bank_txn_id == "B2")

    assert b1_res.predicted_status == ReconciliationStatus.MATCH
    assert b1_res.ledger_id == "L1"
    assert b2_res.predicted_status == ReconciliationStatus.MATCH
    assert b2_res.ledger_id == "L2"
    assert b2_res.predicted_status != ReconciliationStatus.DUPLICATE


def test_phase25_primary_plus_duplicate_representation():
    """18. Phase 2.5: Primary transaction is MATCH and companion is DUPLICATE with linkage."""
    engine = ReconciliationEngine()
    base_time = datetime(2026, 5, 20, 18, 33)
    b_primary = make_bank_record(txn_id="SYNTH-BANK-000009", dt=base_time, amount=3009.72, ref="UPI974622", merchant="MYNTRA")
    b_dup = make_bank_record(txn_id="SYNTH-BANK-DUP-000009", dt=base_time, amount=3009.72, ref="UPI974622", merchant="MYNTRA")
    l1 = make_ledger_record(ledger_id="SYNTH-LEDGER-000009", dt=base_time, amount=3009.72, ref="UPI974622", merchant="Myntra Designs")

    results = engine.reconcile([b_primary, b_dup], [l1])
    r_primary = next(r for r in results if r.bank_txn_id == "SYNTH-BANK-000009")
    r_dup = next(r for r in results if r.bank_txn_id == "SYNTH-BANK-DUP-000009")

    assert r_primary.predicted_status == ReconciliationStatus.MATCH
    assert r_primary.has_duplicate_submission is True
    assert r_dup.predicted_status == ReconciliationStatus.DUPLICATE
    assert r_dup.duplicate_of_bank_txn_id == "SYNTH-BANK-000009"
