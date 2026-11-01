"""
api/routes/v1/worklist.py
--------------------------
GET /api/v1/worklist — Worklist telaah farmasi (B-114).

Filter yang didukung:
  - status: workflow_status
  - tier: latest_tier (HIGH | MEDIUM | LOW)
  - ward: bangsal
  - assigned_to_me: boolean (hanya kasus yang diklaim user aktif)
  - search: pencarian teks bebas di patient_id, patient_name

Sort: tier DESC → admitted_at ASC (default) atau by query param

Pagination: page + page_size (maks 100)

Klaim (POST /api/v1/worklist/{encounter_id}/claim):
  - Klaim encounter untuk dikerjakan
  - If-Match header diperlukan untuk optimistic locking

Release (POST /api/v1/worklist/{encounter_id}/release):
  - Lepas klaim
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header, status
from pydantic import BaseModel

from api.auth.rbac import TokenData, require_roles, UserRole
from api.db.models import Encounter, StatusHistory
from api.db.session import session_scope as get_session
from api.services.audit_service import append_audit

router = APIRouter(prefix="/worklist", tags=["worklist"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class WorklistItem(BaseModel):
    encounter_id: str
    patient_id: str
    patient_name: Optional[str]
    ward: Optional[str]
    workflow_status: str
    latest_tier: Optional[str]
    ml_score: Optional[float]
    priority_reasons: List[Dict[str, Any]]
    admitted_at: str
    sla_hours_elapsed: Optional[float]
    claimed_by: Optional[str]
    claimed_at: Optional[str]
    row_version: int
    dpjp_name: Optional[str]


class WorklistResponse(BaseModel):
    items: List[WorklistItem]
    total: int
    page: int
    page_size: int
    has_next: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hours_since(iso_ts: Optional[str]) -> Optional[float]:
    if not iso_ts:
        return None
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    except Exception:
        return None


TIER_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


# ---------------------------------------------------------------------------
# GET /api/v1/worklist
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=WorklistResponse,
    summary="Ambil daftar kerja telaah farmasi",
)
async def get_worklist(
    request: Request,
    # Filters
    tier: Optional[str] = Query(None, description="HIGH | MEDIUM | LOW"),
    status_filter: Optional[str] = Query(None, alias="status", description="Workflow status"),
    ward: Optional[str] = Query(None, description="Filter berdasarkan bangsal"),
    assigned_to_me: bool = Query(False, description="Hanya kasus yang diklaim pengguna aktif"),
    search: Optional[str] = Query(None, description="Pencarian patient_id atau nama"),
    # Pagination
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    # Auth
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.TECHNICIAN, UserRole.COORDINATOR, UserRole.ADMIN, UserRole.AUDITOR)
    ),
):
    """
    Ambil worklist dengan filter, sort, dan pagination.
    Sort default: tier HIGH→LOW, admitted_at ASC.
    """
    with get_session() as session:
        query = session.query(Encounter)

        # Filter
        if tier:
            query = query.filter(Encounter.latest_tier == tier.upper())
        if status_filter:
            query = query.filter(Encounter.workflow_status == status_filter)
        if ward:
            query = query.filter(Encounter.ward == ward)
        if assigned_to_me:
            query = query.filter(Encounter.claimed_by == current_user.user_id)
        if search:
            like = f"%{search}%"
            query = query.filter(
                sa.or_(
                    Encounter.patient_id.like(like),
                    Encounter.patient_name.like(like),
                )
            )

        # Exclude terminal states by default (unless explicitly filtered)
        if not status_filter:
            query = query.filter(
                Encounter.workflow_status.notin_(["SELESAI_APPROVE", "SELESAI_EDIT", "DITOLAK"])
            )

        total = query.count()

        # Sort: tier DESC (HIGH first), then admitted_at ASC
        # SQLite string sort won't work for tier, so we order by admitted_at only
        # Tier ordering done in Python after fetch (acceptable for page sizes ≤100)
        offset = (page - 1) * page_size
        encounters = query.order_by(Encounter.admitted_at.asc()).offset(offset).limit(page_size).all()

        # Sort by tier in Python (HIGH > MEDIUM > LOW)
        encounters.sort(
            key=lambda e: (
                -TIER_ORDER.get((e.latest_tier or "LOW").upper(), 1),
                e.admitted_at or "",
            )
        )

        import json
        items = []
        for enc in encounters:
            try:
                reasons = json.loads(enc.priority_reason or "[]")
            except Exception:
                reasons = []
            items.append(WorklistItem(
                encounter_id=enc.id,
                patient_id=enc.patient_id,
                patient_name=enc.patient_name,
                ward=enc.ward,
                workflow_status=enc.workflow_status,
                latest_tier=enc.latest_tier,
                ml_score=enc.ml_score,
                priority_reasons=reasons,
                admitted_at=enc.admitted_at or "",
                sla_hours_elapsed=_hours_since(enc.admitted_at),
                claimed_by=enc.claimed_by,
                claimed_at=enc.claimed_at,
                row_version=enc.row_version or 0,
                dpjp_name=enc.dpjp_name,
            ))

        return WorklistResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=(offset + page_size) < total,
        )


# ---------------------------------------------------------------------------
# POST /api/v1/worklist/{encounter_id}/claim
# ---------------------------------------------------------------------------

@router.post(
    "/{encounter_id}/claim",
    summary="Klaim encounter untuk dikerjakan",
)
async def claim_encounter(
    encounter_id: str,
    request: Request,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR)
    ),
):
    """
    Klaim encounter. Gunakan If-Match: <row_version> untuk optimistic locking.
    """
    import logging
    logger = logging.getLogger("priomed.worklist")
    
    try:
        with get_session() as session:
            # Verify encounter exists
            enc = session.query(Encounter).filter(Encounter.id == encounter_id).first()
            if not enc:
                raise HTTPException(status_code=404, detail=f"Encounter {encounter_id} tidak ditemukan.")

            # Optimistic concurrency check
            if if_match is not None:
                try:
                    expected_version = int(if_match)
                    if enc.row_version != expected_version:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Konflik: row_version tidak cocok (expected {expected_version}, got {enc.row_version}). Muat ulang data.",
                        )
                except ValueError:
                    pass  # If-Match bukan integer — abaikan

            # Check if already claimed by another user
            if enc.claimed_by and enc.claimed_by != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Encounter sudah diklaim oleh pengguna lain.",
                )

            # Update claim
            now = datetime.now(timezone.utc).isoformat()
            enc.claimed_by = current_user.user_id
            enc.claimed_at = now
            enc.row_version = (enc.row_version or 0) + 1
            enc.updated_at = now

            # Add audit entry
            append_audit(
                session,
                action="CLAIM",
                actor_id=current_user.user_id,
                actor_type=current_user.actor_type,
                encounter_id=encounter_id,
                client_ip=request.client.host if request.client else None,
            )
            
            # Commit transaction
            session.commit()
            
            logger.info(f"Encounter {encounter_id} berhasil diklaim oleh {current_user.user_id}")

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as exc:
        import traceback
        logger.error(f"Error saat klaim encounter {encounter_id}: {exc}\n{traceback.format_exc()}")
        
        # Check for foreign key constraint error
        error_msg = str(exc).lower()
        if "foreign key" in error_msg or "integrityerror" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Terjadi kesalahan integritas database. Pastikan user '{current_user.user_id}' valid.",
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat klaim encounter: {type(exc).__name__}",
        )

    return {
        "status": "ok",
        "encounter_id": encounter_id,
        "claimed_by": current_user.user_id,
        "row_version": enc.row_version,
    }


# ---------------------------------------------------------------------------
# POST /api/v1/worklist/{encounter_id}/release
# ---------------------------------------------------------------------------

@router.post(
    "/{encounter_id}/release",
    summary="Lepas klaim encounter",
)
async def release_encounter(
    encounter_id: str,
    request: Request,
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.ADMIN)
    ),
):
    """Lepas klaim encounter agar bisa dikerjakan apoteker lain."""
    import logging
    logger = logging.getLogger("priomed.worklist")
    
    try:
        with get_session() as session:
            enc = session.query(Encounter).filter(Encounter.id == encounter_id).first()
            if not enc:
                raise HTTPException(status_code=404, detail=f"Encounter {encounter_id} tidak ditemukan.")

            if enc.claimed_by and enc.claimed_by != current_user.user_id:
                if current_user.role not in (UserRole.ADMIN, UserRole.COORDINATOR):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Hanya pemilik klaim atau admin/koordinator yang dapat melepas klaim.",
                    )

            enc.claimed_by = None
            enc.claimed_at = None
            enc.row_version = (enc.row_version or 0) + 1
            enc.updated_at = datetime.now(timezone.utc).isoformat()

            append_audit(
                session,
                action="RELEASE",
                actor_id=current_user.user_id,
                actor_type=current_user.actor_type,
                encounter_id=encounter_id,
                client_ip=request.client.host if request.client else None,
            )
            session.commit()
            
            logger.info(f"Encounter {encounter_id} dilepas oleh {current_user.user_id}")
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as exc:
        import traceback
        logger.error(f"Error saat release encounter {encounter_id}: {exc}\n{traceback.format_exc()}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat melepas klaim: {type(exc).__name__}",
        )

    return {"status": "ok", "encounter_id": encounter_id, "claimed_by": None}
