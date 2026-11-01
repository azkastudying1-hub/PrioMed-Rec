"""
api/routes/health.py
---------------------
GET /health — liveness + version check.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

from api.schemas import HealthResponse

router = APIRouter()

API_VERSION = "1.0.0"

_STARTUP_TIME = datetime.now(timezone.utc)


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """
    Return system liveness status plus version identifiers.
    Does NOT load the ML model — remains fast even if model is missing.
    """
    model_version = "unknown"
    rule_version  = "unknown"

    try:
        with open("models/metadata.json", encoding="utf-8") as fh:
            meta = json.load(fh)
        model_version = meta.get("model_version", "unknown")
    except Exception:  # noqa: BLE001
        pass

    try:
        with open("configs/discrepancy_rules.json", encoding="utf-8") as fh:
            cfg = json.load(fh)
        rule_version = cfg.get("rule_version", "unknown")
    except Exception:  # noqa: BLE001
        pass

    # Check database
    db_status = "unknown"
    try:
        from api.database import get_db
        with get_db() as conn:
            conn.execute("SELECT 1")
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {type(exc).__name__}"

    uptime_seconds = (datetime.now(timezone.utc) - _STARTUP_TIME).total_seconds()

    return HealthResponse(
        status="ok",
        model_version=model_version,
        rule_version=rule_version,
        api_version=API_VERSION,
        db_status=db_status,
        uptime_seconds=uptime_seconds,
    )
