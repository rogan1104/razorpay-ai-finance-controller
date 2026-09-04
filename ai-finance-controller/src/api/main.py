"""FastAPI backend application entrypoint for AI Finance Controller."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from src.api.routes.health import router as health_router
from src.api.routes.reconciliation import router as reconciliation_router
from src.api.services import ReconciliationService

# Global service instance
reconciliation_service: ReconciliationService = None  # type: ignore
FRONTEND_DIST = (
    Path(__file__).resolve().parents[3] / "frontend" / "finance-flow-monitor-main" / "dist"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager to load models and initialize services."""
    global reconciliation_service
    reconciliation_service = ReconciliationService()
    yield


app = FastAPI(
    title="AI Finance Controller API",
    description=(
        "Production-grade FastAPI backend for automated financial reconciliation "
        "and supporting ML intelligence. Fully deterministic reconciliation with "
        "explainable audit reasons and transparent exception prioritization."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS configuration
default_origins = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
env_origins = os.environ.get("CORS_ORIGINS", "")
allowed_origins: List[str] = (
    [o.strip() for o in env_origins.split(",") if o.strip()]
    if env_origins
    else default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to sanitize errors and avoid leaking internal traces."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": f"An unexpected server error occurred: {str(exc)}",
            "error_code": "INTERNAL_SERVER_ERROR",
        },
    )


# Mount routers under /api
app.include_router(health_router, prefix="/api")
app.include_router(reconciliation_router, prefix="/api")


@app.get("/", tags=["Root"])
async def root():
    """Serve the frontend entrypoint when a production build is available."""
    index_file = FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {
        "message": "AI Finance Controller API is active.",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/{frontend_path:path}", include_in_schema=False)
async def frontend_fallback(frontend_path: str):
    """Serve frontend assets and fall back to the SPA entrypoint."""
    if frontend_path == "api" or frontend_path.startswith("api/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    index_file = FRONTEND_DIST / "index.html"
    requested_file = (FRONTEND_DIST / frontend_path).resolve()
    try:
        requested_file.relative_to(FRONTEND_DIST.resolve())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from None
    route_index_file = requested_file / "index.html"

    if requested_file.is_file():
        return FileResponse(requested_file)
    if route_index_file.is_file():
        return FileResponse(route_index_file)
    if index_file.is_file():
        return FileResponse(index_file)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
