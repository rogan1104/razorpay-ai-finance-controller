"""Transparent, explainable Exception Priority Engine."""

from typing import Dict, Any, List, Tuple


class ExceptionPriorityEngine:
    """Calculates explainable operational review priority (HIGH, MEDIUM, LOW) for reconciliation exceptions."""

    def evaluate_priority(
        self,
        predicted_status: str,
        amount_difference: float | None = None,
        bank_amount: float | None = None,
        ledger_amount: float | None = None,
        match_confidence: float = 1.0,
        anomaly_flag: bool = False,
        anomaly_status: str = "unavailable",
        category: str = "Unknown",
        categorization_confidence: float = 0.0,
    ) -> Tuple[str, str]:
        """Evaluate transparent exception priority and return (priority_level, priority_reasons).

        Returns:
            Tuple of (priority_level: 'HIGH' | 'MEDIUM' | 'LOW', priority_reasons: str)
        """
        reasons: List[str] = []
        effective_amount = bank_amount or ledger_amount or 0.0
        diff = amount_difference if amount_difference is not None and amount_difference != "" else 0.0
        try:
            diff_float = float(diff)
        except (ValueError, TypeError):
            diff_float = 0.0

        try:
            amt_float = float(effective_amount)
        except (ValueError, TypeError):
            amt_float = 0.0

        # Anomaly override rule: Any confirmed anomaly signal elevates priority
        if anomaly_flag:
            reasons.append("Elevated risk signal detected by anomaly detection model (anomaly_flag=True)")
            return "HIGH", "; ".join(reasons)

        # Status-driven transparent priority rules
        if predicted_status == "MATCH":
            if anomaly_flag:
                reasons.append("MATCH transaction with elevated anomaly risk signal")
                return "HIGH", "; ".join(reasons)
            reasons.append("Fully reconciled MATCH record with 0.00 amount difference")
            return "LOW", "; ".join(reasons)

        elif predicted_status == "DUPLICATE":
            reasons.append("Duplicate bank transaction detected (duplicate billing/payout risk)")
            if amt_float > 0:
                reasons.append(f"Transaction value ₹{amt_float:.2f}")
            return "HIGH", "; ".join(reasons)

        elif predicted_status == "AMOUNT_MISMATCH":
            reasons.append(f"AMOUNT_MISMATCH: Discrepancy of ₹{diff_float:.2f}")
            # Large difference >= 1000 INR is HIGH priority
            if diff_float >= 1000.0:
                reasons.append(f"Significant variance exceeding ₹1,000 threshold (₹{diff_float:.2f})")
                return "HIGH", "; ".join(reasons)
            else:
                reasons.append(f"Moderate variance under ₹1,000 threshold (₹{diff_float:.2f})")
                return "MEDIUM", "; ".join(reasons)

        elif predicted_status == "AMBIGUOUS":
            reasons.append("AMBIGUOUS reconciliation: Competing candidates require human verification")
            if diff_float > 0:
                reasons.append(f"Candidate amount difference ₹{diff_float:.2f}")
            return "MEDIUM", "; ".join(reasons)

        elif predicted_status == "UNMATCHED_BANK":
            reasons.append(f"UNMATCHED_BANK: Deposit/Debit of ₹{amt_float:.2f} has no merchant ledger record")
            if amt_float >= 5000.0:
                reasons.append(f"High-value unmatched bank amount exceeding ₹5,000 (₹{amt_float:.2f})")
                return "HIGH", "; ".join(reasons)
            elif amt_float >= 1000.0:
                reasons.append(f"Moderate-value unmatched bank amount (₹{amt_float:.2f})")
                return "MEDIUM", "; ".join(reasons)
            else:
                reasons.append(f"Low-value unmatched bank amount under ₹1,000 (₹{amt_float:.2f})")
                return "LOW", "; ".join(reasons)

        elif predicted_status == "UNMATCHED_LEDGER":
            reasons.append(f"UNMATCHED_LEDGER: Merchant order of ₹{amt_float:.2f} has no bank settlement record")
            if amt_float >= 5000.0:
                reasons.append(f"High-value unmatched ledger invoice exceeding ₹5,000 (₹{amt_float:.2f})")
                return "HIGH", "; ".join(reasons)
            elif amt_float >= 1000.0:
                reasons.append(f"Moderate-value unmatched ledger invoice (₹{amt_float:.2f})")
                return "MEDIUM", "; ".join(reasons)
            else:
                reasons.append(f"Low-value unmatched ledger invoice under ₹1,000 (₹{amt_float:.2f})")
                return "LOW", "; ".join(reasons)

        # Fallback default
        reasons.append(f"Unclassified exception status '{predicted_status}'")
        return "MEDIUM", "; ".join(reasons)
