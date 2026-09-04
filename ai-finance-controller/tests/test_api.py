"""Unit and integration tests for FastAPI backend."""

import io
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
import src.api.main as api_main
from src.api.services import ReconciliationService


@pytest.fixture(autouse=True)
def init_service():
    """Ensure service is initialized for testing."""
    api_main.reconciliation_service = ReconciliationService()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_csv_files():
    """Create controlled in-memory CSV files for testing."""
    bank_csv = (
        "bank_txn_id,timestamp,amount,direction,merchant,reference,payment_method\n"
        "B001,2026-06-01 10:00:00,1000.0,CREDIT,SWIGGY*BLR,UPI-1001,UPI\n"
        "B002,2026-06-01 11:00:00,500.0,DEBIT,FLIPKART,UPI-1002,UPI\n"
        "B003,2026-06-01 12:00:00,2500.0,CREDIT,ZOMATO,UPI-1003,UPI\n"
        "B004,2026-06-01 13:00:00,8000.0,CREDIT,UNKNOWN STORE,UPI-1004,UPI\n"
    )
    ledger_csv = (
        "ledger_id,timestamp,amount,direction,merchant,reference,invoice_id\n"
        "L001,2026-06-01 10:05:00,1000.0,CREDIT,SWIGGY,UPI1001,INV-1\n"
        "L002,2026-06-01 11:05:00,450.0,DEBIT,FLIPKART,UPI1002,INV-2\n"
        "L003,2026-06-01 12:05:00,2500.0,CREDIT,ZOMATO,UPI1003,INV-3\n"
        "L005,2026-06-01 14:00:00,300.0,CREDIT,AMAZON,UPI1005,INV-5\n"
    )
    return bank_csv.encode("utf-8"), ledger_csv.encode("utf-8")


# ==============================================================================
# TESTS
# ==============================================================================

def test_1_health_endpoint(client):
    """1. Test GET /api/health returns ok status and model availability."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "AI Finance Controller API"
    assert "models" in data
    assert "categorization_model" in data["models"]
    assert data["models"]["categorization_model"] is True


def test_2_valid_reconciliation_request(client, sample_csv_files):
    """2. Test POST /api/reconcile with valid CSV uploads."""
    bank_bytes, ledger_bytes = sample_csv_files
    files = {
        "bank_file": ("bank.csv", bank_bytes, "text/csv"),
        "ledger_file": ("ledger.csv", ledger_bytes, "text/csv"),
    }
    response = client.post("/api/reconcile", files=files)
    assert response.status_code == 200
    data = response.json()

    assert "run_id" in data
    assert "summary" in data
    assert data["summary"]["bank_records"] == 4
    assert data["summary"]["ledger_records"] == 4
    assert "status_counts" in data
    assert "priority_counts" in data
    assert "results" in data
    assert len(data["results"]) > 0


def test_3_invalid_file_type(client, sample_csv_files):
    """3. Test POST /api/reconcile rejects non-CSV files with HTTP 400."""
    bank_bytes, ledger_bytes = sample_csv_files
    files = {
        "bank_file": ("bank.pdf", bank_bytes, "application/pdf"),
        "ledger_file": ("ledger.csv", ledger_bytes, "text/csv"),
    }
    response = client.post("/api/reconcile", files=files)
    assert response.status_code == 400
    assert "Only CSV files are accepted" in response.json()["detail"]


def test_4_missing_required_columns(client):
    """4. Test POST /api/reconcile rejects CSV missing required columns with HTTP 400."""
    bad_bank = b"bank_txn_id,amount,merchant\nB1,100,SWIGGY\n"
    good_ledger = b"ledger_id,timestamp,amount,direction,merchant,reference\nL1,2026-06-01 10:00:00,100,CREDIT,SWIGGY,UPI1\n"

    files = {
        "bank_file": ("bank.csv", bad_bank, "text/csv"),
        "ledger_file": ("ledger.csv", good_ledger, "text/csv"),
    }
    response = client.post("/api/reconcile", files=files)
    assert response.status_code == 400
    assert "Missing required columns in bank CSV" in response.json()["detail"]


def test_5_empty_csv(client):
    """5. Test POST /api/reconcile rejects empty CSV with HTTP 400."""
    empty_bank = b""
    good_ledger = b"ledger_id,timestamp,amount,direction,merchant,reference\nL1,2026-06-01 10:00:00,100,CREDIT,SWIGGY,UPI1\n"

    files = {
        "bank_file": ("bank.csv", empty_bank, "text/csv"),
        "ledger_file": ("ledger.csv", good_ledger, "text/csv"),
    }
    response = client.post("/api/reconcile", files=files)
    assert response.status_code == 400
    assert "is empty" in response.json()["detail"]


def test_6_result_retrieval(client, sample_csv_files):
    """6. Test GET /api/reconcile/{run_id} retrieves previous run results."""
    bank_bytes, ledger_bytes = sample_csv_files
    files = {
        "bank_file": ("bank.csv", bank_bytes, "text/csv"),
        "ledger_file": ("ledger.csv", ledger_bytes, "text/csv"),
    }
    post_res = client.post("/api/reconcile", files=files)
    run_id = post_res.json()["run_id"]

    get_res = client.get(f"/api/reconcile/{run_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["run_id"] == run_id
    assert data["summary"]["bank_records"] == 4


def test_7_exception_filtering(client, sample_csv_files):
    """7. Test GET /api/reconcile/{run_id}/exceptions with status, priority, and search filters."""
    bank_bytes, ledger_bytes = sample_csv_files
    files = {
        "bank_file": ("bank.csv", bank_bytes, "text/csv"),
        "ledger_file": ("ledger.csv", ledger_bytes, "text/csv"),
    }
    post_res = client.post("/api/reconcile", files=files)
    run_id = post_res.json()["run_id"]

    # Filter by status
    res_status = client.get(f"/api/reconcile/{run_id}/exceptions?status=AMOUNT_MISMATCH")
    assert res_status.status_code == 200
    items = res_status.json()["exceptions"]
    for item in items:
        assert item["predicted_status"] == "AMOUNT_MISMATCH"

    # Filter by priority
    res_prio = client.get(f"/api/reconcile/{run_id}/exceptions?priority=LOW")
    assert res_prio.status_code == 200
    items_prio = res_prio.json()["exceptions"]
    for item in items_prio:
        assert item["priority"] == "LOW"

    # Filter by search keyword
    res_search = client.get(f"/api/reconcile/{run_id}/exceptions?search=FLIPKART")
    assert res_search.status_code == 200
    assert res_search.json()["total_matching"] >= 1


def test_8_exception_detail(client, sample_csv_files):
    """8. Test GET /api/reconcile/{run_id}/exceptions/{bank_txn_id} returns detail + raw records."""
    bank_bytes, ledger_bytes = sample_csv_files
    files = {
        "bank_file": ("bank.csv", bank_bytes, "text/csv"),
        "ledger_file": ("ledger.csv", ledger_bytes, "text/csv"),
    }
    post_res = client.post("/api/reconcile", files=files)
    run_id = post_res.json()["run_id"]

    detail_res = client.get(f"/api/reconcile/{run_id}/exceptions/B001")
    assert detail_res.status_code == 200
    data = detail_res.json()
    assert data["run_id"] == run_id
    assert data["result"]["bank_txn_id"] == "B001"
    assert data["bank_record"]["merchant"] == "SWIGGY*BLR"
    assert data["ledger_record"]["ledger_id"] == "L001"


def test_9_unknown_run_id(client):
    """9. Test unknown run ID returns HTTP 404."""
    response = client.get("/api/reconcile/non-existent-uuid-12345")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

    detail_res = client.get("/api/reconcile/non-existent-uuid-12345/exceptions/B001")
    assert detail_res.status_code == 404


def test_10_ground_truth_not_required(client, sample_csv_files):
    """10. Test that reconciliation API executes fully without needing ground-truth data."""
    bank_bytes, ledger_bytes = sample_csv_files
    files = {
        "bank_file": ("bank.csv", bank_bytes, "text/csv"),
        "ledger_file": ("ledger.csv", ledger_bytes, "text/csv"),
    }
    response = client.post("/api/reconcile", files=files)
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) > 0


def test_11_reconciliation_status_preserved(client, sample_csv_files):
    """11. Test that reconciliation status and confidence values are unmodified by the API."""
    bank_bytes, ledger_bytes = sample_csv_files
    files = {
        "bank_file": ("bank.csv", bank_bytes, "text/csv"),
        "ledger_file": ("ledger.csv", ledger_bytes, "text/csv"),
    }
    response = client.post("/api/reconcile", files=files)
    data = response.json()
    for r in data["results"]:
        assert r["predicted_status"] in [
            "MATCH", "AMOUNT_MISMATCH", "DUPLICATE", "AMBIGUOUS", "UNMATCHED_BANK", "UNMATCHED_LEDGER"
        ]
        assert 0.0 <= r["match_confidence"] <= 1.0


def test_12_model_failure_does_not_fabricate_results(client):
    """12. Test that missing/unsupported model data gracefully outputs fallback without hallucinating."""
    bank_csv = b"bank_txn_id,timestamp,amount,direction,merchant,reference\nB1,2026-06-01 10:00:00,100,CREDIT,,UPI1\n"
    ledger_csv = b"ledger_id,timestamp,amount,direction,merchant,reference\nL1,2026-06-01 10:00:00,100,CREDIT,,UPI1\n"

    files = {
        "bank_file": ("bank.csv", bank_csv, "text/csv"),
        "ledger_file": ("ledger.csv", ledger_csv, "text/csv"),
    }
    response = client.post("/api/reconcile", files=files)
    assert response.status_code == 200
    res = response.json()["results"][0]
    assert res["category"] == "Unknown"
    assert res["categorization_confidence"] == 0.0
    assert res["anomaly_status"] == "unavailable"


def test_13_cors_behavior(client):
    """13. Test CORS preflight and allowed origins."""
    headers = {
        "Origin": "http://localhost:5500",
        "Access-Control-Request-Method": "POST",
    }
    response = client.options("/api/reconcile", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5500"


def test_14_response_schema_validation(client, sample_csv_files):
    """14. Test OpenAPI schema validation and required response structure."""
    openapi_res = client.get("/openapi.json")
    assert openapi_res.status_code == 200
    schema = openapi_res.json()
    assert "/api/health" in schema["paths"]
    assert "/api/reconcile" in schema["paths"]
    assert "/api/reconcile/{run_id}" in schema["paths"]
    assert "/api/reconcile/{run_id}/exceptions" in schema["paths"]
    assert "/api/reconcile/{run_id}/exceptions/{bank_txn_id}" in schema["paths"]
