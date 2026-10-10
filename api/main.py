"""
api/main.py
------------
PrioMed-Rec FastAPI application entry point.

Mounts all routers:
  GET  /health               — liveness + version check
  GET  /patient/{patient_id} — patient encounter lookup
  GET  /patients/sample      — sample patient IDs (demo)
  POST /prioritize           — admission risk prioritization (ML + SHAP)
  POST /discrepancies        — medication discrepancy detection (rule engine)
  POST /review               — pharmacist review action capture
  POST /analyze              — one-shot patient analysis (patient_id-driven)

Clinical safety:
  - All prediction endpoints return model_version + rule_version.
  - No autonomous clinical instructions appear in any response.
  - All discrepancy flags carry verification_required=True.
  - Model failure → 503 (never fabricates a prediction).

Run:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Load .env file automatically (if it exists)
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv optional — env vars may be set by other means

from api.routes.health import router as health_router
from api.routes.patient import router as patient_router
from api.routes.prioritization import router as prioritization_router
from api.routes.discrepancy import router as discrepancy_router
from api.routes.review import router as review_router
from api.routes.analyze import router as analyze_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load ML model artifacts on startup."""
    try:
        from api.services.prioritization_service import _model, _thresholds, _metadata
        _model()
        _thresholds()
        _metadata()
        print("[startup] ML model and artifacts loaded successfully.")
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] WARNING: Could not pre-load model: {exc}")
        print("[startup] /prioritize will attempt to load on first request.")
    yield  # application runs here


app = FastAPI(
    title="PrioMed-Rec API",
    description=(
        "AI-assisted admission medication-reconciliation prioritization for clinical pharmacists. "
        "Decision support only — pharmacist judgment is required for all clinical decisions. "
        "Outputs: Medication Review Priority · Predicted Discrepancy Likelihood."
    ),
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health_router)
app.include_router(patient_router)
app.include_router(prioritization_router)
app.include_router(discrepancy_router)
app.include_router(review_router)
app.include_router(analyze_router)


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Internal server error: {type(exc).__name__}",
            "note": "Please contact the system administrator.",
        },
    )


