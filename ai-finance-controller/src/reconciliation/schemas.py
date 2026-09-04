"""Data schemas, models, and configuration for the Reconciliation Engine (Phase 2.5)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any


class ReconciliationStatus(str, Enum):
    """Allowed reconciliation statuses."""
    MATCH = "MATCH"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    DUPLICATE = "DUPLICATE"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED_BANK = "UNMATCHED_BANK"
    UNMATCHED_LEDGER = "UNMATCHED_LEDGER"


class MatchMethod(str, Enum):
    """Explainable method or stage that determined the reconciliation result."""
    EXACT_REFERENCE_AMOUNT = "EXACT_REFERENCE_AMOUNT"
    REFERENCE_AMOUNT_MISMATCH = "REFERENCE_AMOUNT_MISMATCH"
    DUPLICATE_MULTIPLE_BANK = "DUPLICATE_MULTIPLE_BANK"
    FUZZY_HIGH_CONFIDENCE = "FUZZY_HIGH_CONFIDENCE"
    AMBIGUOUS_FUZZY_DISCREPANCY = "AMBIGUOUS_FUZZY_DISCREPANCY"
    AMBIGUOUS_MULTI_CANDIDATE = "AMBIGUOUS_MULTI_CANDIDATE"
    AMBIGUOUS_LOW_CONFIDENCE = "AMBIGUOUS_LOW_CONFIDENCE"
    UNMATCHED_NO_CANDIDATE = "UNMATCHED_NO_CANDIDATE"
    UNMATCHED_SETTLEMENT = "UNMATCHED_SETTLEMENT"


@dataclass(frozen=True)
class BankRecord:
    """Represents an ingested and normalized bank transaction."""
    bank_txn_id: str
    timestamp: datetime
    amount: float
    direction: str  # "CREDIT" or "DEBIT"
    merchant: str
    reference: str
    payment_method: str
    norm_merchant: str
    norm_reference: str


@dataclass(frozen=True)
class LedgerRecord:
    """Represents an ingested and normalized merchant ledger transaction."""
    ledger_id: str
    timestamp: datetime
    amount: float
    direction: str  # "CREDIT" or "DEBIT"
    merchant: str
    reference: str
    invoice_id: str
    norm_merchant: str
    norm_reference: str


@dataclass
class ReconciliationResult:
    """Standardized output record for a reconciled or unmatched case."""
    bank_txn_id: Optional[str]
    ledger_id: Optional[str]
    predicted_status: ReconciliationStatus
    match_confidence: float
    match_method: str
    reason: str
    amount_difference: Optional[float] = None
    timestamp_difference: Optional[float] = None  # in minutes
    merchant_similarity: Optional[float] = None
    reference_similarity: Optional[float] = None
    # Explicit duplicate relationship representation (Refinement 2)
    duplicate_of_bank_txn_id: Optional[str] = None
    has_duplicate_submission: bool = False
    duplicate_group_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for CSV and JSON serialization."""
        return {
            "bank_txn_id": self.bank_txn_id if self.bank_txn_id is not None else "",
            "ledger_id": self.ledger_id if self.ledger_id is not None else "",
            "predicted_status": self.predicted_status.value if isinstance(self.predicted_status, ReconciliationStatus) else str(self.predicted_status),
            "match_confidence": round(self.match_confidence, 4) if self.match_confidence is not None else 0.0,
            "match_method": str(self.match_method),
            "reason": self.reason,
            "amount_difference": round(self.amount_difference, 2) if self.amount_difference is not None else "",
            "timestamp_difference": round(self.timestamp_difference, 2) if self.timestamp_difference is not None else "",
            "merchant_similarity": round(self.merchant_similarity, 4) if self.merchant_similarity is not None else "",
            "reference_similarity": round(self.reference_similarity, 4) if self.reference_similarity is not None else "",
            "duplicate_of_bank_txn_id": self.duplicate_of_bank_txn_id if self.duplicate_of_bank_txn_id else "",
            "has_duplicate_submission": self.has_duplicate_submission,
            "duplicate_group_id": self.duplicate_group_id if self.duplicate_group_id else "",
        }


@dataclass
class ReconciliationConfig:
    """Explicit, configurable parameters, tolerances, and weights for the engine."""
    # Exact matching tolerances
    amount_exact_tolerance: float = 0.01  # Tolerance in rupees for exact amount matching
    timestamp_window_days: float = 7.0    # Maximum timestamp window for candidate blocking
    duplicate_window_hours: float = 48.0  # Maximum time difference between duplicate bank submissions

    # Candidate generation multi-signal evidence gates
    candidate_ref_min_sim: float = 0.75   # Minimum reference similarity when amount differs
    candidate_amt_min_sim: float = 0.95   # Minimum amount similarity when reference is partial
    candidate_merch_min_sim: float = 0.80 # Minimum merchant similarity for partial-ref candidates

    # Explainable fuzzy scoring weights (must sum to 1.0)
    reference_weight: float = 0.40
    amount_weight: float = 0.30
    merchant_weight: float = 0.20
    timestamp_weight: float = 0.10

    # Decision thresholds
    high_confidence_threshold: float = 0.85  # Minimum score for a high-confidence match
    ambiguity_threshold: float = 0.70        # Minimum score to consider a candidate plausible
    ambiguity_margin: float = 0.05           # Score margin between top candidates to trigger AMBIGUOUS

    def validate(self) -> None:
        """Validate configuration settings."""
        total_weight = (
            self.reference_weight
            + self.amount_weight
            + self.merchant_weight
            + self.timestamp_weight
        )
        if abs(total_weight - 1.0) > 1e-4:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total_weight:.4f}")
        if self.high_confidence_threshold < self.ambiguity_threshold:
            raise ValueError("high_confidence_threshold must be >= ambiguity_threshold")
