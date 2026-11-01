from __future__ import annotations

"""
api/routes/review.py
----------------------
POST /review — pharmacist review action capture.

Input  : ReviewRequest (case_id, pharmacist_id, ai_result, action, note)
Output : ReviewResponse (review_id, action, timestamp, final_result)

Action must be APPROVE | REJECT | EDIT.

Clinical safety:
  - The system records the pharmacist's final decision.
  - APPROVE: final_result = ai_result (no modification)
  - REJECT:  final_result = ai_result + rejection note
  - EDIT:    final_result = edited_result (provided by pharmacist)
  - In all cases, priority is recorded from the pharmacist's final decision.
  - The system never overrides or reverses the pharmacist's action.
"""


import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
try:
    from api.database import save_audit as _db_save_audit, get_audit_log as _db_get_audit
    _USE_DB = True
except ImportError:
    _USE_DB = False

from api.schemas import ReviewRequest, ReviewResponse

router = APIRouter()


@router.post("/review", response_model=ReviewResponse, tags=["review"])
def submit_review(request: ReviewRequest) -> ReviewResponse:
    """
    Capture a pharmacist review action for an AI-generated result.

    APPROVE : pharmacist agrees with the AI result.
    REJECT  : pharmacist disagrees; note is required.
    EDIT    : pharmacist modifies the result; edited_result must be provided.
    """
    action = request.action  # already validated/uppercased by Pydantic

    # Determine final_result based on action
    if action == "APPROVE":
        final_result = dict(request.ai_result)
        final_result["pharmacist_action"] = "APPROVED"
        final_result["pharmacist_note"]   = request.pharmacist_note or ""

    elif action == "REJECT":
        final_result = dict(request.ai_result)
        final_result["pharmacist_action"] = "REJECTED"
        final_result["pharmacist_note"]   = request.pharmacist_note or ""

    elif action == "EDIT":
        if not request.edited_result:
            raise HTTPException(
                status_code=422,
                detail="edited_result is required when action is EDIT",
            )
        final_result = dict(request.edited_result)
        final_result["pharmacist_action"] = "EDITED"
        final_result["pharmacist_note"]   = request.pharmacist_note or ""

    else:
        raise HTTPException(status_code=422, detail=f"Unknown action: {action}")

    review_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # Pull model_version and rule_version from ai_result if not supplied directly
    model_version = (
        request.model_version
        or request.ai_result.get("model_version")
        or "unknown"
    )
    rule_version = (
        request.rule_version
        or request.ai_result.get("rule_version")
        or "unknown"
    )

    if _USE_DB:
        try:
            _db_save_audit(
                review_id=review_id,
                case_id=request.case_id,
                patient_id=getattr(request, 'patient_id', None) or request.case_id,
                pharmacist_id=request.pharmacist_id,
                action=action,
                timestamp=timestamp,
                note=request.pharmacist_note,
                model_version=model_version,
                rule_version=rule_version,
                ai_result=dict(request.ai_result),
            )
        except Exception as db_exc:
            print(f"[review] DB save warning: {db_exc}")

    return ReviewResponse(
        review_id=review_id,
        case_id=request.case_id,
        action=action,
        timestamp=timestamp,
        pharmacist_id=request.pharmacist_id,
        model_version=model_version,
        rule_version=rule_version,
        final_result=final_result,
    )


@router.get("/audit", tags=["review"], summary="Get audit log with optional filters")
def get_audit(
    patient_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Return pharmacist review history from database."""
    if _USE_DB:
        try:
            entries = _db_get_audit(
                patient_id=patient_id,
                action=action,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            )
            return {"entries": entries, "count": len(entries)}
        except Exception as exc:
            return {"entries": [], "count": 0, "error": str(exc)}
    return {"entries": [], "count": 0, "note": "Database not available"}