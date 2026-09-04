"""Reconciliation API endpoints for executing runs and inspecting results."""
import io
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from src.api.schemas import (
    ErrorResponse,
    BenchmarkResponse,
    ExceptionDetailResponse,
    ExceptionListResponse,
    ReconcileResponse,
    ReconciliationResultItem,
)
from src.api.services import ReconciliationService

router = APIRouter(tags=["Reconciliation"])
def get_service() -> ReconciliationService:
    from src.api.main import reconciliation_service
    return reconciliation_service


@router.get(
    "/benchmark",
    response_model=BenchmarkResponse,
    summary="Get Frozen Offline Benchmark",
    description="Return frozen evaluation metrics. Ground truth is never loaded during live reconciliation.",
)
async def get_benchmark() -> BenchmarkResponse:
    """Read the committed evaluation summary without involving the live pipeline."""
    project_root = Path(__file__).resolve().parents[3]
    metrics_path = project_root / "evaluation" / "day2_reconciliation_metrics.json"
    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        total_cases = int(metrics["total_evaluated_cases"])
        correct_cases = round(total_cases * float(metrics["overall_accuracy"]))
        return BenchmarkResponse(
            evaluated_cases=total_cases,
            correct_cases=correct_cases,
            incorrect_cases=total_cases - correct_cases,
            accuracy=float(metrics["overall_accuracy"]),
            macro_f1=float(metrics["macro_avg"]["f1_score"]),
            weighted_f1=float(metrics["weighted_avg"]["f1_score"]),
            match_resolution=float(metrics["match_rates"]["ground_truth_match_resolution_rate"]),
            benchmark_throughput_records_per_second=float(
                metrics["throughput"]["throughput_total_records_per_second"]
            ),
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Frozen offline benchmark artifact is unavailable.",
        ) from exc

@router.post(
    "/reconcile/demo",
    response_model=ReconcileResponse,
    status_code=status.HTTP_200_OK,
    summary="Run Bundled Demo Reconciliation",
    description=(
        "Run reconciliation against the bundled synthetic bank transaction "
        "and merchant ledger datasets. Ground truth is not loaded or used "
        "during this runtime execution."
    ),
)
async def reconcile_demo(
    service: ReconciliationService = Depends(get_service),
) -> ReconcileResponse:
    """Execute reconciliation using the bundled synthetic demo datasets."""

    # Project root:
    # src/api/routes/reconciliation.py
    # -> routes -> api -> src -> ai-finance-controller
    project_root = Path(__file__).resolve().parents[3]
    demo_dir = project_root / "data" / "reconciliation"

    bank_path = demo_dir / "bank_transactions.csv"
    ledger_path = demo_dir / "merchant_ledger.csv"

    if not bank_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bundled demo bank dataset not found: {bank_path}",
        )

    if not ledger_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bundled demo ledger dataset not found: {ledger_path}",
        )

    try:
        bank_content = bank_path.read_bytes()
        ledger_content = ledger_path.read_bytes()

        bank_upload = UploadFile(
            filename="bank_transactions.csv",
            file=io.BytesIO(bank_content),
        )
        ledger_upload = UploadFile(
            filename="merchant_ledger.csv",
            file=io.BytesIO(ledger_content),
        )

        df_bank, bank_records = await service.parse_and_validate_csv(
            bank_upload,
            expected_type="bank",
        )

        df_ledger, ledger_records = await service.parse_and_validate_csv(
            ledger_upload,
            expected_type="ledger",
        )

        # IMPORTANT:
        # This calls the same production reconciliation + intelligence
        # pipeline used by uploaded datasets.
        #
        # reconciliation_ground_truth.csv is intentionally NOT loaded.
        run_payload = service.process_reconciliation(
            df_bank,
            df_ledger,
            bank_records,
            ledger_records,
        )

        return ReconcileResponse(
            run_id=run_payload["run_id"],
            timestamp=run_payload["timestamp"],
            summary=run_payload["summary"],
            status_counts=run_payload["status_counts"],
            priority_counts=run_payload["priority_counts"],
            results=run_payload["results"],
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Demo reconciliation failed: {str(exc)}",
        ) from exc


@router.post(
    "/reconcile",
    response_model=ReconcileResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Financial Reconciliation",
    description="Upload bank transactions and merchant ledger CSV files to run deterministic reconciliation and ML intelligence enrichment.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file type, missing required columns, or empty file."},
    },
)
async def reconcile_files(
    bank_file: UploadFile = File(..., description="Bank transactions CSV file"),
    ledger_file: UploadFile = File(..., description="Merchant ledger CSV file"),
    service: ReconciliationService = Depends(get_service),
) -> ReconcileResponse:
    # Validate and parse bank file
    df_bank, bank_records = await service.parse_and_validate_csv(bank_file, expected_type="bank")

    # Validate and parse ledger file
    df_ledger, ledger_records = await service.parse_and_validate_csv(ledger_file, expected_type="ledger")

    # Execute deterministic reconciliation + ML enrichment
    run_payload = service.process_reconciliation(df_bank, df_ledger, bank_records, ledger_records)

    return ReconcileResponse(
        run_id=run_payload["run_id"],
        timestamp=run_payload["timestamp"],
        summary=run_payload["summary"],
        status_counts=run_payload["status_counts"],
        priority_counts=run_payload["priority_counts"],
        results=run_payload["results"],
    )


@router.get(
    "/reconcile/{run_id}",
    response_model=ReconcileResponse,
    summary="Retrieve Reconciliation Run",
    description="Retrieve the complete results and summary for a previous reconciliation run by run ID.",
    responses={
        404: {"model": ErrorResponse, "description": "Run ID not found in memory store."},
    },
)
async def get_run_results(
    run_id: str,
    service: ReconciliationService = Depends(get_service),
) -> ReconcileResponse:
    run_data = service.storage.get_run(run_id)
    if not run_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reconciliation run '{run_id}' not found in active session memory.",
        )

    return ReconcileResponse(
        run_id=run_data["run_id"],
        timestamp=run_data["timestamp"],
        summary=run_data["summary"],
        status_counts=run_data["status_counts"],
        priority_counts=run_data["priority_counts"],
        results=run_data["results"],
    )


@router.get(
    "/reconcile/{run_id}/exceptions",
    response_model=ExceptionListResponse,
    summary="List Filtered Exceptions",
    description="Retrieve paginated exceptions from a reconciliation run, filterable by status, review priority, and keyword search.",
    responses={
        404: {"model": ErrorResponse, "description": "Run ID not found."},
    },
)
async def list_exceptions(
    run_id: str,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: MATCH, AMOUNT_MISMATCH, DUPLICATE, AMBIGUOUS, UNMATCHED_BANK, UNMATCHED_LEDGER"),
    priority_filter: Optional[str] = Query(None, alias="priority", description="Filter by priority: HIGH, MEDIUM, LOW"),
    search: Optional[str] = Query(None, description="Keyword search across txn ID, ledger ID, reason, category"),
    limit: int = Query(100, ge=1, le=1000, description="Page size limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    service: ReconciliationService = Depends(get_service),
) -> ExceptionListResponse:
    run_data = service.storage.get_run(run_id)
    if not run_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reconciliation run '{run_id}' not found in active session memory.",
        )

    results = run_data["results"]

    # Filter by status
    if status_filter:
        target_status = status_filter.strip().upper()
        results = [r for r in results if r.get("predicted_status", "").upper() == target_status]

    # Filter by priority
    if priority_filter:
        target_priority = priority_filter.strip().upper()
        results = [r for r in results if r.get("priority", "").upper() == target_priority]

    # Filter by keyword search
    if search and search.strip():
        q = search.strip().lower()
        bank_map = run_data.get("bank_map", {})
        ledger_map = run_data.get("ledger_map", {})
        filtered = []
        for r in results:
            b_id = str(r.get("bank_txn_id") or "")
            l_id = str(r.get("ledger_id") or "")
            raw_b_merch = str(bank_map.get(b_id, {}).get("merchant", ""))
            raw_l_merch = str(ledger_map.get(l_id, {}).get("merchant", ""))
            raw_b_ref = str(bank_map.get(b_id, {}).get("reference", ""))
            raw_l_ref = str(ledger_map.get(l_id, {}).get("reference", ""))

            fields_to_search = [
                b_id,
                l_id,
                raw_b_merch,
                raw_l_merch,
                raw_b_ref,
                raw_l_ref,
                str(r.get("reason") or ""),
                str(r.get("category") or ""),
                str(r.get("priority_reasons") or ""),
                str(r.get("predicted_status") or ""),
            ]
            if any(q in f.lower() for f in fields_to_search):
                filtered.append(r)
        results = filtered

    total_matching = len(results)
    page_results = results[offset : offset + limit]

    return ExceptionListResponse(
        run_id=run_id,
        total_matching=total_matching,
        limit=limit,
        offset=offset,
        exceptions=page_results,
    )


@router.get(
    "/reconcile/{run_id}/exceptions/{bank_txn_id}",
    response_model=ExceptionDetailResponse,
    summary="Get Exception Detail",
    description="Retrieve detailed reconciliation and ML intelligence analysis for a single transaction ID (supports bank_txn_id or ledger_id).",
    responses={
        404: {"model": ErrorResponse, "description": "Transaction or Run ID not found."},
    },
)
async def get_exception_detail(
    run_id: str,
    bank_txn_id: str,
    service: ReconciliationService = Depends(get_service),
) -> ExceptionDetailResponse:
    run_data = service.storage.get_run(run_id)
    if not run_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reconciliation run '{run_id}' not found in active session memory.",
        )

    target_id = bank_txn_id.strip()

    # Find the result record
    matched_result = None
    for r in run_data["results"]:
        if r.get("bank_txn_id") == target_id or r.get("ledger_id") == target_id:
            matched_result = r
            break

    if not matched_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction identifier '{target_id}' not found in reconciliation run '{run_id}'.",
        )

    b_id = matched_result.get("bank_txn_id")
    l_id = matched_result.get("ledger_id")

    raw_bank = run_data.get("bank_map", {}).get(b_id) if b_id else None
    raw_ledger = run_data.get("ledger_map", {}).get(l_id) if l_id else None

    return ExceptionDetailResponse(
        run_id=run_id,
        result=ReconciliationResultItem(**matched_result),
        bank_record=raw_bank,
        ledger_record=raw_ledger,
    )
