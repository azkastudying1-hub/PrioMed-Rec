"""Service-to-service deterministic endpoints used by Langflow.

These routes deliberately never call Langflow. They are the anti-recursion
boundary: Langflow orchestrates, FastAPI owns the deterministic engine and
state. Browser traffic must continue to use the versioned public API.
"""
from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from priomedrec_core.contracts import AnalysisInput
from priomedrec_core.pipeline import run_full, run_phase_a, run_phase_b
from priomedrec_core.priority import compute_priority

router = APIRouter(prefix="/internal/v1", tags=["internal"])


def require_service_key(x_service_key: str | None = Header(default=None, alias="X-Service-Key")) -> None:
    expected = os.getenv("SERVICE_API_KEY_LANGFLOW", "").strip()
    if expected and not secrets.compare_digest(x_service_key or "", expected):
        raise HTTPException(status_code=401, detail="Service key tidak valid")


@router.post("/analysis/run", dependencies=[Depends(require_service_key)])
def internal_analysis_run(payload: AnalysisInput) -> dict[str, Any]:
    return run_full(payload).model_dump(mode="json")


@router.post("/phase-a", dependencies=[Depends(require_service_key)])
def internal_phase_a(payload: AnalysisInput) -> dict[str, Any]:
    return run_phase_a(payload)


@router.post("/phase-b", dependencies=[Depends(require_service_key)])
def internal_phase_b(payload: AnalysisInput) -> dict[str, Any]:
    return run_phase_b(payload)


@router.post("/priority", dependencies=[Depends(require_service_key)])
def internal_priority(payload: dict[str, Any]) -> dict[str, Any]:
    return compute_priority(
        payload.get("ml_score"),
        payload.get("discrepancies"),
        payload.get("sla_hours_elapsed"),
        payload.get("sla_config"),
        payload.get("current_tier"),
    )


@router.post("/narrative/template", dependencies=[Depends(require_service_key)])
def internal_narrative_template(payload: dict[str, Any]) -> dict[str, Any]:
    from api.services.llm_chain_service import _build_sbar_template

    return {"sbar_text": _build_sbar_template(payload), "source": "template"}


@router.post("/narrative/guardrail", dependencies=[Depends(require_service_key)])
def internal_narrative_guardrail(payload: dict[str, Any]) -> dict[str, Any]:
    from api.services.guardrail_service import validate

    report = validate(payload.get("text", ""), payload.get("context", {}))
    return report.__dict__ if hasattr(report, "__dict__") else dict(report)


@router.post("/normalize", dependencies=[Depends(require_service_key)])
def internal_normalize(payload: dict[str, Any]) -> dict[str, Any]:
    from api.services.normalizer_service import normalize_batch

    names = payload.get("drug_names", [])
    return {"items": [item.to_dict() for item in normalize_batch(names)]}


@router.post("/safety", dependencies=[Depends(require_service_key)])
def internal_safety(payload: dict[str, Any]) -> dict[str, Any]:
    from src.rules.safety_flags_engine import check_medication_list

    return check_medication_list(payload.get("medications", []))


@router.post("/interactions", dependencies=[Depends(require_service_key)])
def internal_interactions(payload: dict[str, Any]) -> dict[str, Any]:
    from api.routes.interactions import InteractionCheckRequest, check_interactions

    request = InteractionCheckRequest(drugs=payload.get("drugs", []))
    return check_interactions(request).model_dump()

