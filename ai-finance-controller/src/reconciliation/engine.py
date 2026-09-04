"""Core Reconciliation Engine (Phase 2.5 Refinement).

Deterministic, explainable, high-throughput financial reconciliation engine
that pairs bank transactions with merchant ledger records without ground-truth leakage.
"""

from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
import pandas as pd

from .schemas import (
    BankRecord,
    LedgerRecord,
    MatchMethod,
    ReconciliationConfig,
    ReconciliationResult,
    ReconciliationStatus,
)
from .normalize import (
    compute_amount_similarity,
    compute_merchant_similarity,
    compute_reference_similarity,
    compute_timestamp_proximity,
    normalize_merchant,
    normalize_reference,
)


class ReconciliationEngine:
    """Deterministic, explainable reconciliation engine (Phase 2.5)."""

    def __init__(self, config: Optional[ReconciliationConfig] = None):
        self.config = config or ReconciliationConfig()
        self.config.validate()

    def load_data(
        self,
        bank_source: pd.DataFrame | str,
        ledger_source: pd.DataFrame | str,
    ) -> Tuple[List[BankRecord], List[LedgerRecord]]:
        """Load and normalize bank and ledger transaction datasets."""
        if isinstance(bank_source, str):
            df_bank = pd.read_csv(bank_source)
        else:
            df_bank = bank_source.copy()

        if isinstance(ledger_source, str):
            df_ledger = pd.read_csv(ledger_source)
        else:
            df_ledger = ledger_source.copy()

        # Parse bank records
        bank_records: List[BankRecord] = []
        for _, row in df_bank.iterrows():
            ts = pd.to_datetime(row["timestamp"])
            if isinstance(ts, pd.Timestamp):
                dt = ts.to_pydatetime()
            else:
                dt = datetime.fromisoformat(str(row["timestamp"]))

            merchant_str = str(row.get("merchant", ""))
            ref_str = str(row.get("reference", ""))

            rec = BankRecord(
                bank_txn_id=str(row["bank_txn_id"]),
                timestamp=dt,
                amount=float(row["amount"]),
                direction=str(row["direction"]).strip().upper(),
                merchant=merchant_str,
                reference=ref_str,
                payment_method=str(row.get("payment_method", "")),
                norm_merchant=normalize_merchant(merchant_str),
                norm_reference=normalize_reference(ref_str),
            )
            bank_records.append(rec)

        # Parse ledger records
        ledger_records: List[LedgerRecord] = []
        for _, row in df_ledger.iterrows():
            ts = pd.to_datetime(row["timestamp"])
            if isinstance(ts, pd.Timestamp):
                dt = ts.to_pydatetime()
            else:
                dt = datetime.fromisoformat(str(row["timestamp"]))

            merchant_str = str(row.get("merchant", ""))
            ref_str = str(row.get("reference", ""))

            rec = LedgerRecord(
                ledger_id=str(row["ledger_id"]),
                timestamp=dt,
                amount=float(row["amount"]),
                direction=str(row["direction"]).strip().upper(),
                merchant=merchant_str,
                reference=ref_str,
                invoice_id=str(row.get("invoice_id", "")),
                norm_merchant=normalize_merchant(merchant_str),
                norm_reference=normalize_reference(ref_str),
            )
            ledger_records.append(rec)

        return bank_records, ledger_records

    def reconcile(
        self,
        bank_records: List[BankRecord],
        ledger_records: List[LedgerRecord],
    ) -> List[ReconciliationResult]:
        """Execute the multi-stage deterministic reconciliation pipeline.

        Stages:
        1. Duplicate Bank Transaction Detection (Same ref, amount, direction, <= 48h)
        2. Exact Reference Matching (Exact ref, amount, direction, <= 7 days)
        3. Reference Matching with Amount Discrepancy (Exact ref, direction, amount diff)
        4. Resolve Duplicate Records with Primary-Duplicate Relationship Linkage
        5. Candidate Generation, Evidence Gating & Explainable Fuzzy Matching (MATCH / AMBIGUOUS)
        6. Account for All Remaining Unmatched Records (UNMATCHED_BANK / UNMATCHED_LEDGER)
        """
        results: List[ReconciliationResult] = []
        consumed_bank_ids: Set[str] = set()
        consumed_ledger_ids: Set[str] = set()

        # Build fast lookup indexes on normalized ledger records
        ledger_by_ref: Dict[str, List[LedgerRecord]] = defaultdict(list)
        ledger_by_id: Dict[str, LedgerRecord] = {}
        for l_rec in ledger_records:
            ledger_by_id[l_rec.ledger_id] = l_rec
            if l_rec.norm_reference:
                ledger_by_ref[l_rec.norm_reference].append(l_rec)

        # Build bank lookup by normalized reference
        bank_by_ref: Dict[str, List[BankRecord]] = defaultdict(list)
        for b_rec in bank_records:
            if b_rec.norm_reference:
                bank_by_ref[b_rec.norm_reference].append(b_rec)

        # ======================================================================
        # STAGE 1: DUPLICATE BANK TRANSACTION DETECTION
        # ======================================================================
        # Group bank transactions sharing normalized reference, direction, amount, and timestamp proximity (<= 48h).
        duplicate_bank_to_primary: Dict[str, str] = {}
        duplicate_bank_to_ledger: Dict[str, LedgerRecord] = {}
        bank_has_duplicate_sub: Set[str] = set()
        max_dup_sec = self.config.duplicate_window_hours * 3600.0

        for ref, b_list in bank_by_ref.items():
            if len(b_list) > 1 and ref in ledger_by_ref:
                for i in range(len(b_list)):
                    for j in range(i + 1, len(b_list)):
                        b1, b2 = b_list[i], b_list[j]
                        if b1.direction == b2.direction and abs(b1.amount - b2.amount) <= self.config.amount_exact_tolerance:
                            time_diff_sec = abs((b1.timestamp - b2.timestamp).total_seconds())
                            if time_diff_sec <= max_dup_sec:
                                # Find corresponding ledger entry
                                matching_ledgers = [
                                    l for l in ledger_by_ref[ref]
                                    if l.direction == b1.direction
                                    and abs(l.amount - b1.amount) <= self.config.amount_exact_tolerance
                                ]
                                if matching_ledgers:
                                    primary = b1 if "DUP" not in b1.bank_txn_id else b2
                                    dup = b2 if "DUP" in b2.bank_txn_id else b1
                                    duplicate_bank_to_primary[dup.bank_txn_id] = primary.bank_txn_id
                                    duplicate_bank_to_ledger[dup.bank_txn_id] = matching_ledgers[0]
                                    bank_has_duplicate_sub.add(primary.bank_txn_id)

        # ======================================================================
        # STAGE 2: EXACT REFERENCE MATCHING (Exact Amount, Direction, Timestamp)
        # ======================================================================
        for b_rec in bank_records:
            if b_rec.bank_txn_id in duplicate_bank_to_primary:
                continue
            if b_rec.bank_txn_id in consumed_bank_ids:
                continue

            if b_rec.norm_reference and b_rec.norm_reference in ledger_by_ref:
                candidates = [
                    l for l in ledger_by_ref[b_rec.norm_reference]
                    if l.ledger_id not in consumed_ledger_ids
                    and l.direction == b_rec.direction
                ]

                exact_candidates = [
                    l for l in candidates
                    if abs(b_rec.amount - l.amount) <= self.config.amount_exact_tolerance
                    and abs((b_rec.timestamp - l.timestamp).total_seconds()) <= (self.config.timestamp_window_days * 86400)
                ]

                if exact_candidates:
                    matched_ledger = min(
                        exact_candidates,
                        key=lambda l: abs((b_rec.timestamp - l.timestamp).total_seconds()),
                    )
                    time_diff_min = abs((b_rec.timestamp - matched_ledger.timestamp).total_seconds()) / 60.0
                    amt_diff = abs(b_rec.amount - matched_ledger.amount)
                    ref_sim = compute_reference_similarity(b_rec.reference, matched_ledger.reference)
                    merch_sim = compute_merchant_similarity(b_rec.merchant, matched_ledger.merchant)
                    has_dup = b_rec.bank_txn_id in bank_has_duplicate_sub

                    results.append(
                        ReconciliationResult(
                            bank_txn_id=b_rec.bank_txn_id,
                            ledger_id=matched_ledger.ledger_id,
                            predicted_status=ReconciliationStatus.MATCH,
                            match_confidence=1.0,
                            match_method=MatchMethod.EXACT_REFERENCE_AMOUNT.value,
                            reason=(
                                f"Reference '{b_rec.norm_reference}', amount (₹{b_rec.amount:.2f}), "
                                f"and direction ({b_rec.direction}) matched exactly after normalization "
                                f"with timestamp diff of {time_diff_min:.1f} mins."
                                + (" [Companion duplicate submission recorded]" if has_dup else "")
                            ),
                            amount_difference=amt_diff,
                            timestamp_difference=time_diff_min,
                            merchant_similarity=merch_sim,
                            reference_similarity=ref_sim,
                            has_duplicate_submission=has_dup,
                            duplicate_group_id=b_rec.norm_reference if has_dup else None,
                        )
                    )
                    consumed_bank_ids.add(b_rec.bank_txn_id)
                    consumed_ledger_ids.add(matched_ledger.ledger_id)

        # ======================================================================
        # STAGE 3: EXACT REFERENCE MATCH + AMOUNT DIFFERENCE (AMOUNT_MISMATCH)
        # ======================================================================
        for b_rec in bank_records:
            if b_rec.bank_txn_id in duplicate_bank_to_primary:
                continue
            if b_rec.bank_txn_id in consumed_bank_ids:
                continue

            if b_rec.norm_reference and b_rec.norm_reference in ledger_by_ref:
                candidates = [
                    l for l in ledger_by_ref[b_rec.norm_reference]
                    if l.ledger_id not in consumed_ledger_ids
                    and l.direction == b_rec.direction
                    and abs((b_rec.timestamp - l.timestamp).total_seconds()) <= (self.config.timestamp_window_days * 86400)
                ]

                if candidates:
                    matched_ledger = min(
                        candidates,
                        key=lambda l: abs((b_rec.timestamp - l.timestamp).total_seconds()),
                    )
                    time_diff_min = abs((b_rec.timestamp - matched_ledger.timestamp).total_seconds()) / 60.0
                    amt_diff = abs(b_rec.amount - matched_ledger.amount)
                    pct_diff = (amt_diff / max(matched_ledger.amount, 1e-6)) * 100.0
                    ref_sim = compute_reference_similarity(b_rec.reference, matched_ledger.reference)
                    merch_sim = compute_merchant_similarity(b_rec.merchant, matched_ledger.merchant)

                    results.append(
                        ReconciliationResult(
                            bank_txn_id=b_rec.bank_txn_id,
                            ledger_id=matched_ledger.ledger_id,
                            predicted_status=ReconciliationStatus.AMOUNT_MISMATCH,
                            match_confidence=0.95,
                            match_method=MatchMethod.REFERENCE_AMOUNT_MISMATCH.value,
                            reason=(
                                f"Reference '{b_rec.norm_reference}' and direction ({b_rec.direction}) matched, "
                                f"but bank amount (₹{b_rec.amount:.2f}) differs from ledger amount "
                                f"(₹{matched_ledger.amount:.2f}) by ₹{amt_diff:.2f} ({pct_diff:.2f}%)."
                            ),
                            amount_difference=amt_diff,
                            timestamp_difference=time_diff_min,
                            merchant_similarity=merch_sim,
                            reference_similarity=ref_sim,
                        )
                    )
                    consumed_bank_ids.add(b_rec.bank_txn_id)
                    consumed_ledger_ids.add(matched_ledger.ledger_id)

        # ======================================================================
        # STAGE 4: RESOLVE DUPLICATE BANK RECORDS
        # ======================================================================
        for b_rec in bank_records:
            if b_rec.bank_txn_id in duplicate_bank_to_primary and b_rec.bank_txn_id not in consumed_bank_ids:
                primary_id = duplicate_bank_to_primary[b_rec.bank_txn_id]
                target_ledger = duplicate_bank_to_ledger[b_rec.bank_txn_id]
                time_diff_min = abs((b_rec.timestamp - target_ledger.timestamp).total_seconds()) / 60.0
                amt_diff = abs(b_rec.amount - target_ledger.amount)
                ref_sim = compute_reference_similarity(b_rec.reference, target_ledger.reference)
                merch_sim = compute_merchant_similarity(b_rec.merchant, target_ledger.merchant)

                results.append(
                    ReconciliationResult(
                        bank_txn_id=b_rec.bank_txn_id,
                        ledger_id=target_ledger.ledger_id,
                        predicted_status=ReconciliationStatus.DUPLICATE,
                        match_confidence=1.0,
                        match_method=MatchMethod.DUPLICATE_MULTIPLE_BANK.value,
                        reason=(
                            f"Duplicate bank transaction detected sharing reference '{b_rec.norm_reference}', "
                            f"amount ₹{b_rec.amount:.2f}, and direction {b_rec.direction} with primary txn {primary_id}."
                        ),
                        amount_difference=amt_diff,
                        timestamp_difference=time_diff_min,
                        merchant_similarity=merch_sim,
                        reference_similarity=ref_sim,
                        duplicate_of_bank_txn_id=primary_id,
                        has_duplicate_submission=True,
                        duplicate_group_id=b_rec.norm_reference,
                    )
                )
                consumed_bank_ids.add(b_rec.bank_txn_id)

        # ======================================================================
        # STAGE 5: CANDIDATE GENERATION, EVIDENCE GATING & FUZZY SCORING
        # ======================================================================
        max_window_sec = self.config.timestamp_window_days * 86400.0

        for b_rec in bank_records:
            if b_rec.bank_txn_id in consumed_bank_ids:
                continue

            # Settlement rows do not have individual order ledger entries
            if b_rec.merchant == "RAZORPAY SETTLEMENT":
                continue

            scored_candidates: List[Tuple[float, LedgerRecord, float, float, float, float]] = []

            for l_rec in ledger_records:
                if l_rec.ledger_id in consumed_ledger_ids or l_rec.direction != b_rec.direction:
                    continue

                time_diff_sec = abs((b_rec.timestamp - l_rec.timestamp).total_seconds())
                if time_diff_sec > max_window_sec:
                    continue

                ref_sim = compute_reference_similarity(b_rec.reference, l_rec.reference)
                amt_sim = compute_amount_similarity(b_rec.amount, l_rec.amount)
                merch_sim = compute_merchant_similarity(b_rec.merchant, l_rec.merchant)
                time_sim = compute_timestamp_proximity(b_rec.timestamp, l_rec.timestamp, max_window_sec)

                # Evidence Gate (Refinement 3): Must have meaningful reference similarity
                # OR strong combined amount & merchant similarity to be a plausible candidate.
                if ref_sim < self.config.candidate_ref_min_sim and not (
                    amt_sim >= self.config.candidate_amt_min_sim and merch_sim >= self.config.candidate_merch_min_sim
                ):
                    continue

                total_score = (
                    self.config.reference_weight * ref_sim
                    + self.config.amount_weight * amt_sim
                    + self.config.merchant_weight * merch_sim
                    + self.config.timestamp_weight * time_sim
                )

                if total_score >= self.config.ambiguity_threshold:
                    scored_candidates.append((total_score, l_rec, ref_sim, amt_sim, merch_sim, time_sim))

            if not scored_candidates:
                continue

            scored_candidates.sort(key=lambda item: item[0], reverse=True)
            top_score, top_ledger, top_ref_sim, top_amt_sim, top_merch_sim, _ = scored_candidates[0]
            top_time_diff_min = abs((b_rec.timestamp - top_ledger.timestamp).total_seconds()) / 60.0
            top_amt_diff = abs(b_rec.amount - top_ledger.amount)

            # Check for multi-candidate ambiguity or fuzzy discrepancy (Refinement 1)
            is_multi_candidate = len(scored_candidates) > 1 and (
                (top_score - scored_candidates[1][0]) <= self.config.ambiguity_margin
            )

            # If amount differs and reference is not an exact match -> AMBIGUOUS (Fuzzy discrepancy)
            if top_amt_diff > self.config.amount_exact_tolerance:
                results.append(
                    ReconciliationResult(
                        bank_txn_id=b_rec.bank_txn_id,
                        ledger_id=top_ledger.ledger_id,
                        predicted_status=ReconciliationStatus.AMBIGUOUS,
                        match_confidence=top_score,
                        match_method=MatchMethod.AMBIGUOUS_FUZZY_DISCREPANCY.value,
                        reason=(
                            f"Ambiguous match (fuzzy discrepancy): Top candidate {top_ledger.ledger_id} "
                            f"(ref '{top_ledger.reference}', similarity {top_ref_sim:.2f}) has differing amount "
                            f"₹{top_ledger.amount:.2f} (diff ₹{top_amt_diff:.2f})."
                        ),
                        amount_difference=top_amt_diff,
                        timestamp_difference=top_time_diff_min,
                        merchant_similarity=top_merch_sim,
                        reference_similarity=top_ref_sim,
                    )
                )
                consumed_bank_ids.add(b_rec.bank_txn_id)
            elif is_multi_candidate or (top_score < self.config.high_confidence_threshold):
                competing_info = ", ".join([f"{c[1].ledger_id} ({c[0]:.3f})" for c in scored_candidates[:2]])
                results.append(
                    ReconciliationResult(
                        bank_txn_id=b_rec.bank_txn_id,
                        ledger_id=top_ledger.ledger_id,
                        predicted_status=ReconciliationStatus.AMBIGUOUS,
                        match_confidence=top_score,
                        match_method=MatchMethod.AMBIGUOUS_MULTI_CANDIDATE.value if is_multi_candidate else MatchMethod.AMBIGUOUS_LOW_CONFIDENCE.value,
                        reason=(
                            f"Ambiguous candidate match: Multiple or close candidates [{competing_info}]. "
                            f"Top candidate reference '{top_ledger.reference}' has similarity {top_ref_sim:.2f}."
                        ),
                        amount_difference=top_amt_diff,
                        timestamp_difference=top_time_diff_min,
                        merchant_similarity=top_merch_sim,
                        reference_similarity=top_ref_sim,
                    )
                )
                consumed_bank_ids.add(b_rec.bank_txn_id)
            else:
                # High confidence single fuzzy candidate with exact amount match
                results.append(
                    ReconciliationResult(
                        bank_txn_id=b_rec.bank_txn_id,
                        ledger_id=top_ledger.ledger_id,
                        predicted_status=ReconciliationStatus.MATCH,
                        match_confidence=top_score,
                        match_method=MatchMethod.FUZZY_HIGH_CONFIDENCE.value,
                        reason=(
                            f"High confidence fuzzy match (score: {top_score:.3f}): "
                            f"Merchant similarity {top_merch_sim:.2f}, reference similarity {top_ref_sim:.2f}, "
                            f"and exact amount match within {top_time_diff_min:.1f} mins."
                        ),
                        amount_difference=0.0,
                        timestamp_difference=top_time_diff_min,
                        merchant_similarity=top_merch_sim,
                        reference_similarity=top_ref_sim,
                    )
                )
                consumed_bank_ids.add(b_rec.bank_txn_id)
                consumed_ledger_ids.add(top_ledger.ledger_id)

        # ======================================================================
        # STAGE 6: ACCOUNT FOR ALL REMAINING UNMATCHED RECORDS
        # ======================================================================
        for b_rec in bank_records:
            if b_rec.bank_txn_id not in consumed_bank_ids:
                if b_rec.merchant == "RAZORPAY SETTLEMENT":
                    method = MatchMethod.UNMATCHED_SETTLEMENT.value
                    reason = (
                        f"Razorpay batch settlement deposit of ₹{b_rec.amount:.2f} "
                        f"(UTR: {b_rec.reference}): aggregate gateway payout without 1:1 ledger counterpart."
                    )
                else:
                    method = MatchMethod.UNMATCHED_NO_CANDIDATE.value
                    reason = (
                        f"No compatible merchant ledger candidate found matching {b_rec.direction} "
                        f"amount ₹{b_rec.amount:.2f} (merchant '{b_rec.merchant}') within candidate window."
                    )

                results.append(
                    ReconciliationResult(
                        bank_txn_id=b_rec.bank_txn_id,
                        ledger_id=None,
                        predicted_status=ReconciliationStatus.UNMATCHED_BANK,
                        match_confidence=0.0,
                        match_method=method,
                        reason=reason,
                        amount_difference=None,
                        timestamp_difference=None,
                        merchant_similarity=None,
                        reference_similarity=None,
                    )
                )
                consumed_bank_ids.add(b_rec.bank_txn_id)

        for l_rec in ledger_records:
            if l_rec.ledger_id not in consumed_ledger_ids:
                results.append(
                    ReconciliationResult(
                        bank_txn_id=None,
                        ledger_id=l_rec.ledger_id,
                        predicted_status=ReconciliationStatus.UNMATCHED_LEDGER,
                        match_confidence=0.0,
                        match_method=MatchMethod.UNMATCHED_NO_CANDIDATE.value,
                        reason=(
                            f"No compatible bank transaction found matching {l_rec.direction} "
                            f"amount ₹{l_rec.amount:.2f} (merchant '{l_rec.merchant}') within candidate window."
                        ),
                        amount_difference=None,
                        timestamp_difference=None,
                        merchant_similarity=None,
                        reference_similarity=None,
                    )
                )
                consumed_ledger_ids.add(l_rec.ledger_id)

        return results
