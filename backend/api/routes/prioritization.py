"""
api/routes/prioritization.py
------------------------------
POST /prioritize — admission risk prioritization.

Input  : PrioritizeRequest (16 validated features)
Output : PrioritizeResponse (risk_probability, priority, top_features)

Clinical safety:
  - priority is set by the ML model + thresholds only.
  - LLM or any downstream service MUST NOT modify priority.
  - Model failure returns 503, never a fabricated prediction.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import (
    PrioritizeRequest, PrioritizeResponse,
    BatchPrioritizeRequest, BatchPrioritizeResponse,
)

router = APIRouter()


@router.post("/prioritize", response_model=PrioritizeResponse, tags=["prioritization"])
def prioritize(request: PrioritizeRequest) -> PrioritizeResponse:
    """
    Predict medication discrepancy risk for a single admission encounter.

    Returns risk_probability [0,1], priority {LOW|MEDIUM|HIGH},
    model_version, threshold_version, and top contributing features.
    """
    try:
        from api.services.prioritization_service import prioritize as _prioritize
        result = _prioritize(feature_dict=request.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Model artifact not found: {exc}. Cannot produce a prediction.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"Prioritization service error: {exc}",
        ) from exc

    return PrioritizeResponse(**result)


@router.post("/prioritize/batch", response_model=BatchPrioritizeResponse, tags=["prioritization"])
def prioritize_batch(request: BatchPrioritizeRequest) -> BatchPrioritizeResponse:
    """
    Rank and prioritize a batch of patients/encounters.

    Accepts an optional list of patient_ids or samples top `limit` patients from cohort.
    Returns ranked list sorted by discrepancy_likelihood descending.
    """
    try:
        from api.services.prioritization_service import prioritize_batch as _prioritize_batch
        result = _prioritize_batch(
            patient_ids=request.patient_ids,
            limit=request.limit,
            priority_filter=request.priority_filter,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"Batch prioritization error: {exc}",
        ) from exc

    return BatchPrioritizeResponse(**result)


@router.get(
    "/worklist",
    tags=["prioritization"],
    summary="Get worklist with patient status from database",
)
def get_worklist(limit: int = 50):
    """
    Return worklist with patient workflow status from database.
    Combines patient data with stored workflow status.
    """
    try:
        from api.database import get_db
        with get_db() as conn:
            rows = conn.execute(
                """SELECT ps.patient_id, ps.encounter_id, ps.workflow_status, 
                          ps.updated_at, ps.updated_by
                   FROM patient_status ps
                   ORDER BY ps.updated_at DESC
                   LIMIT ?""",
                (limit,)
            ).fetchall()
            return {
                "patients": [dict(r) for r in rows],
                "count": len(rows),
            }
    except Exception as exc:
        return {"patients": [], "count": 0, "error": str(exc)}

