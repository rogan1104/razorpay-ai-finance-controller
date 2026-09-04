"""Pydantic request and response schemas for AI Finance Controller FastAPI backend."""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = Field(default="ok", description="Service status")
    service: str = Field(default="AI Finance Controller API", description="Service title")
    version: str = Field(default="1.0.0", description="API version")
    models: Dict[str, bool] = Field(
        default_factory=dict,
        description="Availability status of supporting ML models"
    )


class ReconciliationResultItem(BaseModel):
    """Individual reconciled/enriched transaction record schema."""
    bank_txn_id: Optional[str] = Field(default=None, description="Bank transaction identifier")
    ledger_id: Optional[str] = Field(default=None, description="Merchant ledger order identifier")
    predicted_status: str = Field(description="Deterministic reconciliation status")
    match_confidence: float = Field(description="Match confidence score (0.0 to 1.0)")
    match_method: str = Field(description="Engine method used to classify the record")
    reason: str = Field(description="Explainable human-readable audit reason")
    
    amount_difference: Optional[float] = Field(default=None, description="Absolute variance between bank and ledger amounts")
    timestamp_difference: Optional[float] = Field(default=None, description="Time difference in minutes")
    merchant_similarity: Optional[float] = Field(default=None, description="Normalized merchant name similarity (0.0 to 1.0)")
    reference_similarity: Optional[float] = Field(default=None, description="Normalized reference string similarity (0.0 to 1.0)")
    
    duplicate_of_bank_txn_id: Optional[str] = Field(default=None, description="Primary bank txn ID if this is a duplicate")
    has_duplicate_submission: Optional[bool] = Field(default=False, description="Whether companion duplicate submissions exist")
    duplicate_group_id: Optional[str] = Field(default=None, description="Identifier grouping related duplicate submissions")
    
    category: Optional[str] = Field(default="Unknown", description="ML-predicted transaction category")
    categorization_confidence: Optional[float] = Field(default=0.0, description="Confidence of category prediction")
    categorization_source: Optional[str] = Field(default="local_ml", description="Source of category inference")
    
    anomaly_flag: Optional[bool] = Field(default=False, description="Isolation Forest anomaly flag")
    anomaly_score: Optional[float] = Field(default=None, description="Isolation Forest anomaly score")
    anomaly_status: Optional[str] = Field(default="unavailable", description="Anomaly model availability status")
    anomaly_reason: Optional[str] = Field(default=None, description="Reason for anomaly signal result")
    
    priority: Optional[str] = Field(default="LOW", description="Explainable review priority: HIGH, MEDIUM, LOW")
    priority_reasons: Optional[str] = Field(default="", description="Explainable reasons for review priority")


class RunSummary(BaseModel):
    """Aggregate execution and throughput metrics for a reconciliation run."""
    bank_records: int = Field(description="Total bank transactions ingested")
    ledger_records: int = Field(description="Total ledger transactions ingested")
    total_source_records: int = Field(description="Sum of bank and ledger records")
    total_results: int = Field(description="Total output prediction records emitted")
    match_rate: float = Field(description="Ratio of MATCH records to total predictions")
    exception_count: int = Field(description="Total non-MATCH exceptions requiring review")
    reconciliation_runtime_seconds: float = Field(description="Reconciliation engine execution time in seconds")
    intelligence_runtime_seconds: float = Field(description="ML intelligence enrichment time in seconds")
    total_runtime_seconds: float = Field(description="Total processing time in seconds")
    throughput_records_per_second: float = Field(description="Total source records processed per second")


class ReconcileResponse(BaseModel):
    """Full response schema for POST /api/reconcile."""
    run_id: str = Field(description="Unique UUID for this reconciliation run")
    timestamp: str = Field(description="ISO-8601 UTC timestamp of execution")
    summary: RunSummary = Field(description="Execution summary metrics")
    status_counts: Dict[str, int] = Field(description="Count of records by reconciliation status")
    priority_counts: Dict[str, int] = Field(description="Count of records by review priority")
    results: List[ReconciliationResultItem] = Field(description="List of all reconciled and enriched results")


class BenchmarkResponse(BaseModel):
    """Frozen offline evaluation metrics, separate from live reconciliation runs."""
    evaluated_cases: int
    correct_cases: int
    incorrect_cases: int
    accuracy: float
    macro_f1: float
    weighted_f1: float
    match_resolution: float
    benchmark_throughput_records_per_second: float


class ExceptionListResponse(BaseModel):
    """Paginated list of filtered exception results."""
    run_id: str = Field(description="Reconciliation run UUID")
    total_matching: int = Field(description="Total records matching filter criteria")
    limit: int = Field(description="Pagination limit")
    offset: int = Field(description="Pagination offset")
    exceptions: List[ReconciliationResultItem] = Field(description="Page of filtered exception records")


class ExceptionDetailResponse(BaseModel):
    """Detailed result schema for a single transaction query."""
    run_id: str = Field(description="Reconciliation run UUID")
    result: ReconciliationResultItem = Field(description="Enriched reconciliation result for the transaction")
    bank_record: Optional[Dict[str, Any]] = Field(default=None, description="Original raw bank record payload")
    ledger_record: Optional[Dict[str, Any]] = Field(default=None, description="Original raw ledger record payload")


class ErrorResponse(BaseModel):
    """Standardized error response payload."""
    detail: str = Field(description="Human-readable error description")
    error_code: Optional[str] = Field(default=None, description="Machine-readable error classification")
