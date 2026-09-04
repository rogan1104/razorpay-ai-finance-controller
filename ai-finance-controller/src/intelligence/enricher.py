"""End-to-end intelligence enrichment pipeline combining reconciliation results with supporting ML signals."""

from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

from .categorizer import CategorizationEnricher
from .anomaly import AnomalyEnricher
from .priority import ExceptionPriorityEngine


class IntelligencePipeline:
    """Orchestrates ML enrichment (categorization, anomaly/risk, and transparent review priority)

    for reconciliation outputs without overriding deterministic reconciliation decisions.
    """

    def __init__(
        self,
        categorization_model_path: str | Path = "models/categorization_pipeline.joblib",
        anomaly_model_path: str | Path = "models/anomaly_detector_pipeline.joblib",
    ):
        self.categorizer = CategorizationEnricher(model_path=categorization_model_path)
        self.anomaly_detector = AnomalyEnricher(model_path=anomaly_model_path)
        self.priority_engine = ExceptionPriorityEngine()

    def enrich_predictions(
        self,
        df_predictions: pd.DataFrame,
        df_bank: Optional[pd.DataFrame] = None,
        df_ledger: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Enrich every reconciliation prediction row with supporting ML and priority signals.

        Guarantees:
            - Deterministic reconciliation status is NEVER modified.
            - Match confidence and match method are preserved exactly.
            - All original fields remain intact.
        """
        # Build quick lookups for merchant descriptions and amounts from raw sources if provided
        bank_info: Dict[str, Dict[str, Any]] = {}
        if df_bank is not None:
            for _, r in df_bank.iterrows():
                b_id = str(r["bank_txn_id"])
                bank_info[b_id] = {
                    "merchant": str(r.get("merchant", "")),
                    "amount": float(r.get("amount", 0.0)),
                    "timestamp": str(r.get("timestamp", "")),
                    "direction": str(r.get("direction", "")),
                    "reference": str(r.get("reference", "")),
                }

        ledger_info: Dict[str, Dict[str, Any]] = {}
        if df_ledger is not None:
            for _, r in df_ledger.iterrows():
                l_id = str(r["ledger_id"])
                ledger_info[l_id] = {
                    "merchant": str(r.get("merchant", "")),
                    "amount": float(r.get("amount", 0.0)),
                    "timestamp": str(r.get("timestamp", "")),
                    "direction": str(r.get("direction", "")),
                    "reference": str(r.get("reference", "")),
                }

        enriched_rows: List[Dict[str, Any]] = []

        for _, row in df_predictions.iterrows():
            row_dict = row.to_dict()
            b_id = str(row["bank_txn_id"]) if pd.notna(row.get("bank_txn_id")) and str(row.get("bank_txn_id")).strip() else None
            l_id = str(row["ledger_id"]) if pd.notna(row.get("ledger_id")) and str(row.get("ledger_id")).strip() else None
            pred_status = str(row.get("predicted_status", "UNKNOWN"))
            amt_diff = row.get("amount_difference")
            match_conf = float(row.get("match_confidence", 0.0))

            # 1. Determine transaction description & amount for ML inference
            description = ""
            bank_amt = None
            ledger_amt = None

            if b_id and b_id in bank_info:
                description = bank_info[b_id]["merchant"]
                bank_amt = bank_info[b_id]["amount"]
            if l_id and l_id in ledger_info:
                if not description:
                    description = ledger_info[l_id]["merchant"]
                ledger_amt = ledger_info[l_id]["amount"]

            # Fallback if raw tables not provided
            if not description:
                description = str(row.get("merchant", ""))

            # 2. Transaction Categorization ML Inference
            cat_result = self.categorizer.predict(description)
            row_dict["category"] = cat_result["category"]
            row_dict["categorization_confidence"] = cat_result["categorization_confidence"]
            row_dict["categorization_source"] = cat_result["categorization_source"]

            # 3. Anomaly / Risk Signal Evaluation
            is_exception = (pred_status != "MATCH")
            anomaly_payload = {
                "transaction_description": description,
                "amount": bank_amt or ledger_amt or 0.0,
            }
            # Attempt scoring with available transaction fields
            anomaly_result = self.anomaly_detector.score_transaction(anomaly_payload, is_exception=is_exception)
            row_dict["anomaly_flag"] = anomaly_result["anomaly_flag"]
            row_dict["anomaly_score"] = anomaly_result["anomaly_score"]
            row_dict["anomaly_status"] = anomaly_result["anomaly_status"]
            row_dict["anomaly_reason"] = anomaly_result["anomaly_reason"]

            # 4. Transparent Exception Priority Evaluation
            priority, priority_reasons = self.priority_engine.evaluate_priority(
                predicted_status=pred_status,
                amount_difference=amt_diff,
                bank_amount=bank_amt,
                ledger_amount=ledger_amt,
                match_confidence=match_conf,
                anomaly_flag=anomaly_result["anomaly_flag"],
                anomaly_status=anomaly_result["anomaly_status"],
                category=cat_result["category"],
                categorization_confidence=cat_result["categorization_confidence"],
            )
            row_dict["priority"] = priority
            row_dict["priority_reasons"] = priority_reasons

            enriched_rows.append(row_dict)

        return pd.DataFrame(enriched_rows)
