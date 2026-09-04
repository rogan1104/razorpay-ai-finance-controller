"""Service layer for AI Finance Controller API.

Manages CSV ingestion, validation, engine execution, model caching, and in-memory run storage.
"""

import io
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
from fastapi import HTTPException, UploadFile, status

from src.reconciliation.engine import ReconciliationEngine
from src.reconciliation.schemas import BankRecord, LedgerRecord, ReconciliationConfig
from src.reconciliation.normalize import normalize_merchant, normalize_reference
from src.intelligence.enricher import IntelligencePipeline


REQUIRED_BANK_COLUMNS = {"bank_txn_id", "timestamp", "amount", "direction", "merchant", "reference"}
REQUIRED_LEDGER_COLUMNS = {"ledger_id", "timestamp", "amount", "direction", "merchant", "reference"}
MAX_IN_MEMORY_RUNS = 50


class RunStorage:
    """Bounded thread-safe in-memory store for local reconciliation runs."""

    def __init__(self, max_size: int = MAX_IN_MEMORY_RUNS):
        self.max_size = max_size
        self._runs: OrderedDict[str, Dict[str, Any]] = OrderedDict()

    def store_run(self, run_id: str, data: Dict[str, Any]) -> None:
        if len(self._runs) >= self.max_size:
            self._runs.popitem(last=False)  # Evict oldest
        self._runs[run_id] = data

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self._runs.get(run_id)

    def list_runs(self) -> List[str]:
        return list(self._runs.keys())


class ReconciliationService:
    """Orchestrates reconciliation and ML intelligence pipeline execution for API requests."""

    def __init__(
        self,
        categorization_model_path: str | Path = "models/categorization_pipeline.joblib",
        anomaly_model_path: str | Path = "models/anomaly_detector_pipeline.joblib",
    ):
        self.config = ReconciliationConfig()
        self.engine = ReconciliationEngine(config=self.config)
        self.intelligence_pipeline = IntelligencePipeline(
            categorization_model_path=categorization_model_path,
            anomaly_model_path=anomaly_model_path,
        )
        self.storage = RunStorage()

    def check_models_health(self) -> Dict[str, bool]:
        """Check availability of persisted model artifacts."""
        cat_available = (
            self.intelligence_pipeline.categorizer.pipeline is not None
        )
        anom_available = (
            self.intelligence_pipeline.anomaly_detector.is_loaded
        )
        return {
            "categorization_model": cat_available,
            "anomaly_detector_model": anom_available,
        }

    async def parse_and_validate_csv(
        self,
        upload_file: UploadFile,
        expected_type: str,  # "bank" or "ledger"
    ) -> Tuple[pd.DataFrame, List[Any]]:
        """Validate, parse, and instantiate typed records from an uploaded CSV."""
        filename = upload_file.filename or ""
        if not (filename.lower().endswith(".csv") or filename.lower().endswith(".txt")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file extension for {expected_type} file '{filename}'. Only CSV files are accepted.",
            )

        content = await upload_file.read()
        if not content or len(content.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded {expected_type} file '{filename}' is empty.",
            )

        try:
            df = pd.read_csv(io.BytesIO(content))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse {expected_type} CSV: {str(e)}",
            )

        if df.empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded {expected_type} CSV contains no data rows.",
            )

        # Validate required columns
        df_cols = set(df.columns)
        required = REQUIRED_BANK_COLUMNS if expected_type == "bank" else REQUIRED_LEDGER_COLUMNS
        missing = required - df_cols
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns in {expected_type} CSV: {sorted(list(missing))}. Expected: {sorted(list(required))}",
            )

        # Build typed records for engine
        records: List[Any] = []
        if expected_type == "bank":
            for _, row in df.iterrows():
                merchant_raw = str(row["merchant"]) if pd.notna(row["merchant"]) else ""
                ref_raw = str(row["reference"]) if pd.notna(row["reference"]) else ""
                records.append(
                    BankRecord(
                        bank_txn_id=str(row["bank_txn_id"]),
                        timestamp=pd.to_datetime(row["timestamp"]).to_pydatetime(),
                        amount=float(row["amount"]),
                        direction=str(row["direction"]).strip().upper(),
                        merchant=merchant_raw,
                        reference=ref_raw,
                        payment_method=str(row.get("payment_method", "UNKNOWN")) if pd.notna(row.get("payment_method")) else "UNKNOWN",
                        norm_merchant=normalize_merchant(merchant_raw),
                        norm_reference=normalize_reference(ref_raw),
                    )
                )
        else:
            for _, row in df.iterrows():
                merchant_raw = str(row["merchant"]) if pd.notna(row["merchant"]) else ""
                ref_raw = str(row["reference"]) if pd.notna(row["reference"]) else ""
                records.append(
                    LedgerRecord(
                        ledger_id=str(row["ledger_id"]),
                        timestamp=pd.to_datetime(row["timestamp"]).to_pydatetime(),
                        amount=float(row["amount"]),
                        direction=str(row["direction"]).strip().upper(),
                        merchant=merchant_raw,
                        reference=ref_raw,
                        invoice_id=str(row.get("invoice_id", "")) if pd.notna(row.get("invoice_id")) else "",
                        norm_merchant=normalize_merchant(merchant_raw),
                        norm_reference=normalize_reference(ref_raw),
                    )
                )

        return df, records

    def process_reconciliation(
        self,
        df_bank: pd.DataFrame,
        df_ledger: pd.DataFrame,
        bank_records: List[BankRecord],
        ledger_records: List[LedgerRecord],
    ) -> Dict[str, Any]:
        """Execute reconciliation and ML intelligence pipeline, and cache the run."""
        run_id = str(uuid.uuid4())
        total_source = len(bank_records) + len(ledger_records)

        # 1. Deterministic Reconciliation
        rec_start = time.perf_counter()
        raw_results = self.engine.reconcile(bank_records, ledger_records)
        rec_time = time.perf_counter() - rec_start

        df_results = pd.DataFrame([r.to_dict() for r in raw_results])

        # 2. ML Intelligence Enrichment
        intel_start = time.perf_counter()
        df_enriched = self.intelligence_pipeline.enrich_predictions(
            df_results, df_bank=df_bank, df_ledger=df_ledger
        )
        intel_time = time.perf_counter() - intel_start

        total_time = rec_time + intel_time
        throughput = total_source / max(total_time, 1e-9)

        # Clean NaN/None/empty strings for Pydantic serialization
        raw_list = df_enriched.to_dict(orient="records")
        results_list = []
        for r in raw_list:
            cleaned = dict(r)
            for f in ["amount_difference", "timestamp_difference", "merchant_similarity", "reference_similarity", "anomaly_score"]:
                val = cleaned.get(f)
                if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
                    cleaned[f] = None
                else:
                    try:
                        cleaned[f] = float(val)
                    except (ValueError, TypeError):
                        cleaned[f] = None

            for f in ["bank_txn_id", "ledger_id", "duplicate_of_bank_txn_id", "duplicate_group_id", "anomaly_reason"]:
                val = cleaned.get(f)
                if val is None or (isinstance(val, float) and pd.isna(val)) or val == "":
                    cleaned[f] = None

            for f in ["has_duplicate_submission", "anomaly_flag"]:
                val = cleaned.get(f)
                cleaned[f] = bool(val) if pd.notna(val) else False

            results_list.append(cleaned)

        # Counts
        status_counts = {}
        for r in results_list:
            st = str(r["predicted_status"])
            status_counts[st] = status_counts.get(st, 0) + 1

        priority_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for r in results_list:
            pr = r.get("priority", "LOW")
            priority_counts[pr] = priority_counts.get(pr, 0) + 1

        matches = status_counts.get("MATCH", 0)
        total_preds = len(results_list)
        match_rate = round(matches / max(total_preds, 1), 4)
        exception_count = total_preds - matches

        summary = {
            "bank_records": len(bank_records),
            "ledger_records": len(ledger_records),
            "total_source_records": total_source,
            "total_results": total_preds,
            "match_rate": match_rate,
            "exception_count": exception_count,
            "reconciliation_runtime_seconds": round(rec_time, 6),
            "intelligence_runtime_seconds": round(intel_time, 6),
            "total_runtime_seconds": round(total_time, 6),
            "throughput_records_per_second": round(throughput, 2),
        }

        # Build raw record lookups for exception detail
        bank_map = {str(r["bank_txn_id"]): r.to_dict() for _, r in df_bank.iterrows()}
        ledger_map = {str(r["ledger_id"]): r.to_dict() for _, r in df_ledger.iterrows()}

        run_payload = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "status_counts": status_counts,
            "priority_counts": priority_counts,
            "results": results_list,
            "bank_map": bank_map,
            "ledger_map": ledger_map,
        }

        self.storage.store_run(run_id, run_payload)
        return run_payload
