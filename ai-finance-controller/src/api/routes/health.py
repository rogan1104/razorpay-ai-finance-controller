"""Health check and model status route."""

from fastapi import APIRouter, Depends
from src.api.schemas import HealthResponse
from src.api.services import ReconciliationService

router = APIRouter(tags=["Health"])


def get_service() -> ReconciliationService:
    from src.api.main import reconciliation_service
    return reconciliation_service


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Returns the operating status of the API and availability of supporting ML models.",
)
async def health_check(service: ReconciliationService = Depends(get_service)) -> HealthResponse:
    model_status = service.check_models_health()
    return HealthResponse(
        status="ok",
        service="AI Finance Controller API",
        version="1.0.0",
        models=model_status,
    )
