"""
api/main.py
------------
PrioMed-Rec FastAPI application entry point.

Mounts all routers:
  Legacy (kompatibilitas Langflow/MCP):
    GET  /health               — liveness + version check
    GET  /patient/{patient_id} — patient encounter lookup
    GET  /patients/sample      — sample patient IDs (demo)
    POST /prioritize           — admission risk prioritization (ML + SHAP)
    POST /prioritize/batch     — batch prioritization
    POST /discrepancies        — medication discrepancy detection (rule engine)
    POST /review               — pharmacist review action capture
    POST /analyze              — one-shot patient analysis (patient_id-driven)
    POST /bpmh/{patient_id}    — BPMH record
    GET  /wards                — ward config
    POST /interactions/check   — DDI check

  Versioned /api/v1/* (baru):
    GET  /api/v1/health        — liveness check (versi baru)
    GET  /version              — versi semua komponen
    (+ endpoint baru lainnya ditambahkan di fase berikutnya)

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
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
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
from api.routes.bpmh import router as bpmh_router
from api.routes.wards import router as wards_router
from api.routes.interactions import router as interactions_router
from api.database import init_database
from api.logging_config import setup_logging
from api.errors import (
    ErrorCode,
    error_response,
    global_exception_handler as _global_exc_handler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load ML model artifacts and initialize database/logging on startup."""
    try:
        setup_logging()
        print("[startup] Logging configured.")
    except Exception as exc:
        print(f"[startup] WARNING: Logging setup failed: {exc}")

    try:
        init_database()
        print("[startup] Legacy database initialized successfully.")
    except Exception as exc:
        print(f"[startup] WARNING: Legacy database init failed: {exc}")

    try:
        from api.db.session import engine
        from api.db.models import Base
        Base.metadata.create_all(engine)
        print("[startup] SQLAlchemy tables verified/created.")
    except Exception as exc:
        print(f"[startup] WARNING: SQLAlchemy init failed: {exc}")

    try:
        from api.services.prioritization_service import _model, _thresholds, _metadata
        _model()
        _thresholds()
        _metadata()
        print("[startup] ML model and artifacts loaded successfully.")
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] WARNING: Could not pre-load model: {exc}")
        print("[startup] /prioritize will attempt to load on first request.")

    try:
        from api.tasks.scheduler import start_scheduler
        start_scheduler()
        print("[startup] APScheduler started.")
    except Exception as exc:
        print(f"[startup] WARNING: Scheduler start failed: {exc}")

    # Auto-seed demo data if DB is empty (safe for repeated runs — idempotent)
    import os as _os
    if _os.getenv("AUTO_SEED_DEMO", "true").lower() not in {"0", "false", "no"}:
        try:
            from api.db.session import session_scope as _ss
            from api.db.models import Encounter as _Enc
            with _ss() as _sess:
                _count = _sess.query(_Enc).count()
            if _count == 0:
                from scripts.seed_demo import seed as _seed
                _seed()
                print("[startup] Demo data seeded (10 skenario).")
            else:
                print(f"[startup] DB sudah ada {_count} encounter(s) — lewati auto-seed.")
        except Exception as exc:
            print(f"[startup] WARNING: Auto-seed gagal: {exc}")

    # Auto-seed antrean simulasi (QUEUE_PLAN §9) bila antrean kosong — idempoten
    if _os.getenv("AUTO_SEED_QUEUE", "true").lower() not in {"0", "false", "no"}:
        try:
            from scripts.seed_queue import seed_queue as _seed_queue
            _res = _seed_queue(size=_os.getenv("AUTO_SEED_QUEUE_SIZE", "S"))
            if _res.get("skipped"):
                print(f"[startup] Antrean sudah berisi {_res['skipped']} entri — lewati seed antrean.")
            else:
                print(f"[startup] Antrean simulasi di-seed: {_res} (data simulasi, bukan data RS).")
        except Exception as exc:
            print(f"[startup] WARNING: Seed antrean gagal: {exc}")

    yield  # application runs here

    try:
        from api.tasks.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass

    try:
        from api.services.simulation_service import stop_simulation
        stop_simulation()
    except Exception:
        pass


app = FastAPI(
    title="PrioMed-Rec API",
    description=(
        "AI-assisted admission medication-reconciliation prioritization for clinical pharmacists. "
        "Decision support only — pharmacist judgment is required for all clinical decisions. "
        "Outputs: Prioritas Telaah Farmasi · Kemungkinan ada diskrepansi obat."
    ),
    version="1.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------

from fastapi.middleware.cors import CORSMiddleware

_cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request-ID middleware — tambahkan X-Request-ID ke setiap response
# ---------------------------------------------------------------------------

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    # Simpan di request state agar handler bisa mengaksesnya
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ---------------------------------------------------------------------------
# Exception handlers — envelope error seragam
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    rid = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return error_response(
        code=ErrorCode.VALIDATION_ERROR,
        message="Input validation failed.",
        status_code=422,
        details=[
            {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ],
        request_id=rid,
    )


@app.exception_handler(Exception)
async def _global_handler(request: Request, exc: Exception) -> JSONResponse:
    from fastapi import HTTPException
    rid = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    if isinstance(exc, HTTPException):
        return error_response(
            code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
            status_code=exc.status_code,
            request_id=rid,
        )
    return error_response(
        code=ErrorCode.INTERNAL_ERROR,
        message=f"Internal server error: {type(exc).__name__}",
        status_code=500,
        request_id=rid,
    )


# ---------------------------------------------------------------------------
# Legacy routers (kompatibilitas Langflow/MCP — pertahankan)
# ---------------------------------------------------------------------------

app.include_router(health_router)
app.include_router(patient_router)
app.include_router(prioritization_router)
app.include_router(discrepancy_router)
app.include_router(review_router)
app.include_router(analyze_router)
app.include_router(bpmh_router)
app.include_router(wards_router)
app.include_router(interactions_router)


# ---------------------------------------------------------------------------
# /api/v1 versioned router
# ---------------------------------------------------------------------------

from fastapi import APIRouter as _APIRouter
import json as _json

# Import new v1 sub-routers
from api.routes.v1.auth import router as auth_v1_router
from api.routes.v1.worklist import router as worklist_v1_router
from api.routes.v1.review import router as review_v1_router, audit_router as audit_v1_router
from api.routes.v1.ai import router as ai_v1_router
from api.routes.v1.health import router as health_v1_router  # A-303
from api.routes.v1.knowledge import router as knowledge_v1_router  # A-307 Tool 4
from api.routes.v1.analysis import router as analysis_v1_router  # LF-006 Langflow-first
from api.routes.v1.queue import router as queue_v1_router           # Q-004/010/011
from api.routes.v1.queue_events import router as queue_events_router # Q-006 SSE
from api.routes.v1.simulation import router as simulation_v1_router # CSV replay engine
from api.routes.internal import router as internal_router  # Langflow deterministic boundary

v1_router = _APIRouter(prefix="/api/v1", tags=["v1"])


@v1_router.get("/version", summary="Versi semua komponen", tags=["system"])
async def v1_version():
    """
    Mengembalikan versi API, model, rules, dan metadata terkait.
    Dipakai oleh audit trail untuk mencatat versi yang aktif.
    """
    model_version    = "unknown"
    rule_version     = "unknown"
    feature_version  = "unknown"
    label_version    = "unknown"
    calibration      = "unknown"
    training_date    = "unknown"

    try:
        with open("models/metadata.json", encoding="utf-8") as fh:
            meta = _json.load(fh)
        model_version   = meta.get("model_version", "unknown")
        feature_version = meta.get("feature_version", "unknown")
        label_version   = meta.get("label_version", "unknown")
        calibration     = meta.get("calibration", "unknown")
        training_date   = meta.get("training_date", "unknown")
    except Exception:
        pass

    try:
        with open("configs/discrepancy_rules.json", encoding="utf-8") as fh:
            cfg = _json.load(fh)
        rule_version = cfg.get("rule_version", "unknown")
    except Exception:
        pass

    return {
        "api_version":     "1.2.0",
        "model_version":   model_version,
        "rule_version":    rule_version,
        "feature_version": feature_version,
        "label_version":   label_version,
        "calibration":     calibration,
        "training_date":   training_date,
    }


app.include_router(v1_router)

# v1 sub-routers (prefixed under /api/v1 via their own prefix)
app.include_router(auth_v1_router, prefix="/api/v1")
app.include_router(worklist_v1_router, prefix="/api/v1")
app.include_router(review_v1_router, prefix="/api/v1")
app.include_router(audit_v1_router, prefix="/api/v1")
app.include_router(ai_v1_router, prefix="/api/v1")  # A-301 AI Gateway
app.include_router(health_v1_router, prefix="/api/v1")  # A-303 /health/deps
app.include_router(knowledge_v1_router, prefix="/api/v1")  # A-307 knowledge lookup
app.include_router(analysis_v1_router, prefix="/api/v1")  # LF-006 analysis orchestration
app.include_router(queue_v1_router, prefix="/api/v1")      # Q-004/010/011 Queue management
app.include_router(queue_events_router, prefix="/api/v1")  # Q-006 SSE
app.include_router(simulation_v1_router, prefix="/api/v1")  # CSV replay simulation engine
app.include_router(internal_router)  # Service-to-service only; never called by browser

# ---------------------------------------------------------------------------
# Compatibility shim: some local clients/probes expect an OpenAI-style
# /v1/models endpoint. Return a minimal, secret-free response instead of 404.
# ---------------------------------------------------------------------------
@app.get("/v1/models", include_in_schema=False)
@app.get("/api/v1/models", include_in_schema=False)
def openai_style_models():
    return {"object": "list", "data": []}


# ---------------------------------------------------------------------------
# Mount React SPA (Vite build output at web/dist, atau web/ di dev)
# ---------------------------------------------------------------------------
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_web_dist     = Path(__file__).parent.parent / "web" / "dist"
_web_fallback = Path(__file__).parent.parent / "web"
_static_dir   = _web_dist if _web_dist.exists() else _web_fallback

if _static_dir.exists():
    @app.get("/app", include_in_schema=False)
    @app.get("/app/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str = ""):
        index = _static_dir / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse(
            status_code=404,
            content={"detail": "Web app not built yet. Run: cd web && npm install && npm run build"},
        )

    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
