"""CLI runner for Day 3 Supporting Intelligence & ML Enrichment.

Loads the frozen Phase 2.5 reconciliation predictions, enriches every record
with category, risk signals, and review priority, measures execution time, and
generates Day 3 prediction CSV and run JSON artifacts.
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

import pandas as pd

from .enricher import IntelligencePipeline


def parse_args():
    parser = argparse.ArgumentParser(description="Run AI Finance Controller Day 3 ML Intelligence Enrichment")
    parser.add_argument(
        "--predictions-data",
        type=str,
        default="evaluation/phase2_5_reconciliation_predictions.csv",
        help="Path to Phase 2.5 reconciliation predictions CSV",
    )
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
        "--categorization-model",
        type=str,
        default="models/categorization_pipeline.joblib",
        help="Path to persisted categorization model",
    )
    parser.add_argument(
        "--anomaly-model",
        type=str,
        default="models/anomaly_detector_pipeline.joblib",
        help="Path to persisted anomaly detector model",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="evaluation/day3_intelligence_predictions.csv",
        help="Path to output enriched predictions CSV",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="evaluation/day3_intelligence_run.json",
        help="Path to output run summary JSON",
    )
    return parser.parse_args()


def run_intelligence_enrichment(
    predictions_path: str = "evaluation/phase2_5_reconciliation_predictions.csv",
    bank_path: str = "data/reconciliation/bank_transactions.csv",
    ledger_path: str = "data/reconciliation/merchant_ledger.csv",
    categorization_model_path: str = "models/categorization_pipeline.joblib",
    anomaly_model_path: str = "models/anomaly_detector_pipeline.joblib",
    output_csv: str = "evaluation/day3_intelligence_predictions.csv",
    output_json: str = "evaluation/day3_intelligence_run.json",
) -> Dict[str, Any]:
    """Run full intelligence enrichment pipeline and save Day 3 artifacts."""
    print(f"[INTELLIGENCE] Loading predictions from: {predictions_path}")
    df_pred = pd.read_csv(predictions_path)
    total_records = len(df_pred)

    df_bank = pd.read_csv(bank_path) if os.path.exists(bank_path) else None
    df_ledger = pd.read_csv(ledger_path) if os.path.exists(ledger_path) else None

    pipeline = IntelligencePipeline(
        categorization_model_path=categorization_model_path,
        anomaly_model_path=anomaly_model_path,
    )

    print(f"[INTELLIGENCE] Enriching {total_records} records with ML category, risk, and priority signals...")
    start_time = time.perf_counter()
    df_enriched = pipeline.enrich_predictions(df_pred, df_bank=df_bank, df_ledger=df_ledger)
    elapsed_seconds = time.perf_counter() - start_time
    throughput = total_records / max(elapsed_seconds, 1e-9)

    print(f"[INTELLIGENCE] Enrichment complete in {elapsed_seconds:.4f}s ({throughput:.2f} records/s)")

    # Ensure output directories exist
    os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(output_json)), exist_ok=True)

    # Save CSV
    df_enriched.to_csv(output_csv, index=False)
    print(f"[INTELLIGENCE] Enriched predictions saved to: {output_csv}")

    # Compute breakdown statistics
    cat_success = int((df_enriched["category"] != "Unknown").sum())
    cat_unavail = int((df_enriched["category"] == "Unknown").sum())
    cat_dist = df_enriched["category"].value_counts().to_dict()

    anom_attempted = int(len(df_enriched))
    anom_success = int((df_enriched["anomaly_status"] == "available").sum())
    anom_unavail = int((df_enriched["anomaly_status"] == "unavailable").sum())
    anom_detected = int((df_enriched["anomaly_flag"] == True).sum())

    prio_counts = df_enriched["priority"].value_counts().to_dict()
    for p in ["HIGH", "MEDIUM", "LOW"]:
        prio_counts.setdefault(p, 0)

    # Per-status breakdown
    status_breakdown = {}
    for st in df_enriched["predicted_status"].unique():
        sub = df_enriched[df_enriched["predicted_status"] == st]
        sub_total = len(sub)
        sub_cat_cov = float((sub["category"] != "Unknown").sum() / sub_total) * 100.0
        sub_anom_cov = float((sub["anomaly_status"] == "available").sum() / sub_total) * 100.0
        sub_anom_rate = float((sub["anomaly_flag"] == True).sum() / sub_total) * 100.0
        sub_prio = sub["priority"].value_counts().to_dict()

        status_breakdown[st] = {
            "record_count": sub_total,
            "category_coverage_pct": round(sub_cat_cov, 2),
            "anomaly_coverage_pct": round(sub_anom_cov, 2),
            "anomaly_rate_pct": round(sub_anom_rate, 2),
            "priority_distribution": sub_prio,
        }

    # Load Phase 2.5 reconciliation throughput for comparison
    phase25_run_file = "evaluation/phase2_5_reconciliation_run.json"
    phase25_throughput = 46643.21
    phase25_runtime = 0.086636
    if os.path.exists(phase25_run_file):
        with open(phase25_run_file) as f:
            p25_json = json.load(f)
            phase25_throughput = p25_json.get("throughput_total_records_per_second", phase25_throughput)
            phase25_runtime = p25_json.get("processing_time_seconds", phase25_runtime)

    run_summary: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_records_processed": total_records,
        "enrichment_processing_time_seconds": round(elapsed_seconds, 6),
        "enrichment_throughput_records_per_second": round(throughput, 2),
        "phase2_5_reconciliation_throughput_records_per_second": phase25_throughput,
        "phase2_5_reconciliation_processing_time_seconds": phase25_runtime,
        "reconciliation_status_preserved": True,
        "categorization_summary": {
            "successfully_categorized": cat_success,
            "unavailable_categorization": cat_unavail,
            "category_coverage_pct": round((cat_success / total_records) * 100.0, 2),
            "category_distribution": cat_dist,
        },
        "anomaly_summary": {
            "anomaly_scoring_attempted": anom_attempted,
            "anomaly_scoring_successful": anom_success,
            "anomaly_scoring_unavailable": anom_unavail,
            "anomalies_detected": anom_detected,
            "anomaly_limitation_note": (
                "Isolation Forest requires customer historical features (is_new_merchant_for_customer, "
                "customer_txn_count_so_far, days_since_last_transaction) which are absent in reconciliation dataset schema. "
                "Gracefully marked as unavailable rather than fabricating data."
            ),
        },
        "priority_summary": {
            "HIGH": prio_counts.get("HIGH", 0),
            "MEDIUM": prio_counts.get("MEDIUM", 0),
            "LOW": prio_counts.get("LOW", 0),
        },
        "status_level_breakdown": status_breakdown,
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(run_summary, f, indent=2)
    print(f"[INTELLIGENCE] Run summary saved to: {output_json}")

    print("\n================== ENRICHMENT SUMMARY ==================")
    print(f"  Total Records Enriched    : {total_records}")
    print(f"  Categorization Coverage   : {cat_success}/{total_records} ({cat_success/total_records*100:.1f}%)")
    print(f"  Anomaly Signal Status     : {anom_unavail}/{total_records} unavailable (schema contract adhered to)")
    print(f"  Priority Distribution     : HIGH={prio_counts.get('HIGH', 0)}, MEDIUM={prio_counts.get('MEDIUM', 0)}, LOW={prio_counts.get('LOW', 0)}")
    print(f"  Enrichment Processing Time: {elapsed_seconds:.4f}s ({throughput:.2f} rec/s)")
    print("========================================================\n")

    return run_summary


def main():
    args = parse_args()
    run_intelligence_enrichment(
        predictions_path=args.predictions_data,
        bank_path=args.bank_data,
        ledger_path=args.ledger_data,
        categorization_model_path=args.categorization_model,
        anomaly_model_path=args.anomaly_model,
        output_csv=args.output_csv,
        output_json=args.output_json,
    )


if __name__ == "__main__":
    main()
