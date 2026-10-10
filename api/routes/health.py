"""
api/routes/health.py
---------------------
GET /health — liveness + version check.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from api.schemas import HealthResponse

router = APIRouter()

API_VERSION = "1.0.0"


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

    return HealthResponse(
        status="ok",
        model_version=model_version,
        rule_version=rule_version,
        api_version=API_VERSION,
    )
