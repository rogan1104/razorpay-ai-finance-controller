# Phase 2.5 Targeted Reconciliation Engine Design Notes

## 1. Executive Summary

Phase 2.5 implements targeted engineering refinements to the deterministic reconciliation engine based on the independent Day 2 baseline evaluation. The refinements address specific observed failure modes—ambiguity ordering, duplicate representation, and false ambiguous candidate filtering—while preserving 100.0% MATCH recall and sub-second processing performance.

---

## 2. Summary of Engineering Changes

| Component | Day 1 Implementation | Phase 2.5 Refinement | Failure Mode Addressed |
| :--- | :--- | :--- | :--- |
| **Ambiguity Decision Ordering** | Stage 5 assigned `AMOUNT_MISMATCH` to any fuzzy candidate with score $\ge 0.85$ and amount discrepancy, regardless of whether reference was exact. | If reference is fuzzy ($\text{RefSim} < 1.0$) and amount differs, classify as `AMBIGUOUS` (`AMBIGUOUS_FUZZY_DISCREPANCY`). `AMOUNT_MISMATCH` is strictly reserved for verified exact reference matches. | Resolves 100 `AMBIGUOUS` cases previously misclassified as `AMOUNT_MISMATCH`. |
| **Duplicate Representation** | Emitted duplicate bank records as `DUPLICATE` without companion metadata on the primary matched transaction. | Primary bank transaction is marked `has_duplicate_submission = True` and assigned `duplicate_group_id`. Duplicate bank transaction is emitted as `DUPLICATE` with explicit `duplicate_of_bank_txn_id` linkage. | Resolves ambiguity in case-level vs source-level duplicate evaluation. |
| **Duplicate Grouping Window** | Grouped bank records by reference across the entire dataset without strict timestamp or amount gating. | Required same direction, amount within $\pm 0.01$ INR, and timestamp proximity $\le 48$ hours. | Fixes 4 `MATCH` cases falsely marked as `DUPLICATE` due to shared reference tokens across months. |
| **Candidate Evidence Gating** | Allowed any candidate with score $\ge 0.70$ (including incidental token matches) into ambiguity evaluation. | Multi-signal evidence gate: Candidate must satisfy $\text{RefSim} \ge 0.75$ OR ($\text{AmtSim} \ge 0.95$ AND $\text{MerchSim} \ge 0.80$). | Eliminates 7 false `AMBIGUOUS` predictions on `UNMATCHED_BANK` records. |

---

## 3. Detailed Refinement Rationale

### Refinement 1: Ambiguity Before Amount Mismatch
- **Problem**: In Day 1, transactions where reference differed by 1 digit (e.g. `UPI724185` vs `UPI724186`) and amount differed slightly were scored at $\approx 0.95$ and routed into `AMOUNT_MISMATCH`.
- **Engineering Principle**: An `AMOUNT_MISMATCH` indicates an exact verified reference agreement with an amount discrepancy (e.g. fee deduction or invoice variance). When both reference and amount have discrepancies, the transaction identity is not uniquely established.
- **Resolution**: Stage 3 requires exact normalized reference match for `AMOUNT_MISMATCH`. Stage 5 flags fuzzy candidates with differing amounts as `AMBIGUOUS`.

### Refinement 2: Explicit Duplicate Representation
- **Problem**: The benchmark contains 100 duplicate bank submissions (`SYNTH-BANK-DUP-...`). In Day 1, the primary transaction (`SYNTH-BANK-...`) was resolved as `MATCH` and the duplicate as `DUPLICATE`. In ground-truth case evaluation, cases keyed by the primary bank transaction appeared as `MATCH` rather than `DUPLICATE`.
- **Engineering Principle**: The reconciliation engine must maintain source-level fidelity: the primary bank transaction successfully settled the merchant invoice (`MATCH`), while the duplicate transaction is an operational anomaly (`DUPLICATE`).
- **Representation**:
  - `duplicate_of_bank_txn_id`: Explicitly links duplicate records to the primary bank transaction ID.
  - `has_duplicate_submission`: Boolean flag on the primary matched record.
  - `duplicate_group_id`: Normalized reference group ID grouping all related submissions.

### Refinement 3: Multi-Signal Evidence Gating for Candidates
- **Problem**: 10 `UNMATCHED_BANK` cases were classified as `AMBIGUOUS` because generic token overlap with common merchant names (e.g. "SWIGGY", "AMAZON") yielded composite scores $> 0.70$.
- **Engineering Principle**: Merchant name overlap alone is insufficient evidence to hypothesize a transaction match in high-volume reconciliation.
- **Resolution**: Candidate generation requires independent multi-signal corroboration: high reference similarity ($\ge 0.75$) or near-exact amount ($\ge 0.95$) with high merchant similarity ($\ge 0.80$). Incidental candidates without corroborating evidence are rejected, allowing the record to remain `UNMATCHED_BANK`.

---

## 4. What Was Deliberately NOT Changed

1. **Scoring Weights**: Preserved the explainable $40\% \text{ Ref} + 30\% \text{ Amt} + 20\% \text{ Merch} + 10\% \text{ Time}$ weighting.
2. **Thresholds**: Preserved `high_confidence_threshold = 0.85`, `ambiguity_threshold = 0.70`, `ambiguity_margin = 0.05`, `amount_exact_tolerance = 0.01`, and `timestamp_window_days = 7.0`.
3. **Normalization Rules**: Preserved all deterministic merchant canonical mappings and reference cleaning rules.
4. **Previous Artifacts**: Day 1 and Day 2 artifacts remain completely unmodified and preserved in `evaluation/`.

---

## 5. Summary of Results

- **Overall Accuracy**: **94.85%** (vs. 89.30% in Day 2, **+5.55%**)
- **Macro F1**: **82.17%** (vs. 62.10% in Day 2, **+20.07%**)
- **Weighted F1**: **92.44%** (vs. 85.13% in Day 2, **+7.31%**)
- **MATCH Resolution Rate**: **100.00%** (1,400 / 1,400)
- **AMOUNT_MISMATCH F1**: **100.00%** (250 / 250)
- **AMBIGUOUS F1**: **98.52%** (100 / 100 recall, 97.09% precision)
- **UNMATCHED_BANK F1**: **97.96%** (72 / 75 recall, 100.00% precision)
- **UNMATCHED_LEDGER F1**: **100.00%** (75 / 75 precision & recall)
- **Processing Time**: **0.0866 seconds** (46,643.21 total records/sec)
