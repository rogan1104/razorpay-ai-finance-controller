"""Runner entrypoint for Day 1 Reconciliation Engine.

Loads reconciliation dataset, executes deterministic reconciliation pipeline,
measures runtime/throughput using monotonic performance counter, and outputs
Day 1 prediction CSV and run JSON artifacts.
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

import pandas as pd

from .engine import ReconciliationEngine
from .schemas import ReconciliationConfig, ReconciliationStatus


def parse_args():
    parser = argparse.ArgumentParser(description="Run AI Finance Controller Reconciliation Engine")
    parser.add_argument(
        "--bank-data",
        type=str,
        default="data/reconciliation/bank_transactions.csv",
        help="Path to bank transactions CSV",
    )
    parser.add_argument(
        "--ledger-data",
        type=str,
        default="data/reconciliation/merchant_ledger.csv",
        help="Path to merchant ledger CSV",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="evaluation/day1_reconciliation_predictions.csv",
        help="Path to output predictions CSV",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="evaluation/day1_reconciliation_run.json",
        help="Path to output run summary JSON",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.01,
        help="Exact amount tolerance in rupees",
    )
    parser.add_argument(
        "--window-days",
        type=float,
        default=7.0,
        help="Timestamp window in days",
    )
    return parser.parse_args()


def run_reconciliation(
    bank_path: str,
    ledger_path: str,
    output_csv: str,
    output_json: str,
    config: ReconciliationConfig = None,
) -> Dict[str, Any]:
    """Run full reconciliation pipeline and write prediction & run metadata artifacts."""
    if config is None:
        config = ReconciliationConfig()
    config.validate()

    engine = ReconciliationEngine(config=config)

    # Ingestion & Normalization
    print(f"[RECONCILIATION] Loading bank data from: {bank_path}")
    print(f"[RECONCILIATION] Loading ledger data from: {ledger_path}")
    bank_records, ledger_records = engine.load_data(bank_path, ledger_path)
    bank_count = len(bank_records)
    ledger_count = len(ledger_records)
    total_source_count = bank_count + ledger_count
    print(f"[RECONCILIATION] Bank records: {bank_count}, Ledger records: {ledger_count} (Total: {total_source_count})")

    # Measure actual processing time with monotonic timer
    start_time = time.perf_counter()
    results = engine.reconcile(bank_records, ledger_records)
    elapsed_seconds = time.perf_counter() - start_time

    # Compute throughput
    bank_throughput = bank_count / max(elapsed_seconds, 1e-9)
    total_throughput = total_source_count / max(elapsed_seconds, 1e-9)

    print(f"[RECONCILIATION] Processed in {elapsed_seconds:.4f}s ({total_throughput:.2f} total records/s, {bank_throughput:.2f} bank records/s)")

    # Build predictions dataframe
    results_data = [r.to_dict() for r in results]
    df_results = pd.DataFrame(results_data)

    # Count predicted statuses
    status_counts: Dict[str, int] = {status.value: 0 for status in ReconciliationStatus}
    for r in results:
        status_key = r.predicted_status.value if isinstance(r.predicted_status, ReconciliationStatus) else str(r.predicted_status)
        status_counts[status_key] = status_counts.get(status_key, 0) + 1

    # Ensure output directories exist
    os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(output_json)), exist_ok=True)

    # Write predictions CSV
    df_results.to_csv(output_csv, index=False)
    print(f"[RECONCILIATION] Predictions saved to: {output_csv} ({len(df_results)} rows)")

    # Build run summary JSON
    run_summary: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "amount_exact_tolerance": config.amount_exact_tolerance,
            "timestamp_window_days": config.timestamp_window_days,
            "reference_weight": config.reference_weight,
            "amount_weight": config.amount_weight,
            "merchant_weight": config.merchant_weight,
            "timestamp_weight": config.timestamp_weight,
            "high_confidence_threshold": config.high_confidence_threshold,
            "ambiguity_threshold": config.ambiguity_threshold,
            "ambiguity_margin": config.ambiguity_margin,
        },
        "bank_record_count": bank_count,
        "ledger_record_count": ledger_count,
        "total_source_records": total_source_count,
        "reconciliation_result_counts": status_counts,
        "total_predictions": len(results),
        "processing_time_seconds": round(elapsed_seconds, 6),
        "throughput_bank_records_per_second": round(bank_throughput, 2),
        "throughput_total_records_per_second": round(total_throughput, 2),
        "throughput_definition": "total_source_records (bank_records + ledger_records) / processing_time_seconds",
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(run_summary, f, indent=2)
    print(f"[RECONCILIATION] Run summary saved to: {output_json}")

    print("\n================== STATUS DISTRIBUTION ==================")
    for status, count in status_counts.items():
        print(f"  {status:20s}: {count:5d}")
    print("=========================================================\n")

    return run_summary


def main():
    args = parse_args()
    config = ReconciliationConfig(
        amount_exact_tolerance=args.tolerance,
        timestamp_window_days=args.window_days,
    )
    run_reconciliation(
        bank_path=args.bank_data,
        ledger_path=args.ledger_data,
        output_csv=args.output_csv,
        output_json=args.output_json,
        config=config,
    )


if __name__ == "__main__":
    main()
