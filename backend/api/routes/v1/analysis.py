"""Langflow-first analysis API; legacy ``/analyze`` remains unchanged."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from api.services.analysis_orchestrator import run_analysis
from priomedrec_core.contracts import AnalysisInput

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/{encounter_id}/run")
async def run_encounter_analysis(encounter_id: str, body: AnalysisInput) -> dict[str, Any]:
    """Run Langflow first, then deterministic local fallback on any failure."""
    request = body.model_copy(update={"encounter_id": encounter_id})
    return await run_analysis(request)
