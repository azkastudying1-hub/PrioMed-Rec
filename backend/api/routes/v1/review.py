"""
api/routes/v1/review.py
------------------------
Endpoint telaah farmasi v1 (B-108, B-112).

POST /api/v1/encounters/{encounter_id}/review

Aksi yang didukung:
  APPROVE        — Setuju tanpa perubahan
  EDIT           — Setuju dengan perubahan (alasan wajib)
  REJECT         — Tolak / batalkan telaah (alasan wajib)
  ESCALATE       — Eskalasi ke koordinator/DPJP (alasan wajib)
  DRAFT_REVIEW   — Simpan progres sementara (tanpa mengakhiri telaah)

Prinsip keselamatan (S1, S2, B-112):
  - APPROVE ditolak 422 jika ada diskrepansi high-alert belum dikonfirmasi
  - Alasan wajib untuk EDIT, REJECT, ESCALATE
  - actor_id SELALU dari token, tidak dari body
  - Idempotency-Key header didukung (mengembalikan hasil sebelumnya jika duplikat)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from api.auth.rbac import TokenData, require_roles, UserRole
from api.db.models import Encounter, AuditEntry
from api.db.session import session_scope as get_session
from api.services.audit_service import append_audit
from api.services.case_state_service import transition as state_transition
from api.services.queue_view_service import release_encounter_claim, sync_after_review

router = APIRouter(prefix="/encounters", tags=["review"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_ACTION_TO_STATUS = {
    "APPROVE":      "SELESAI_APPROVE",
    "EDIT":         "SELESAI_EDIT",
    "REJECT":       "DITOLAK",
    "ESCALATE":     "ESKALASI",
    "DRAFT_REVIEW": "DRAFT_REVIEW",
}


class ReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(APPROVE|EDIT|REJECT|ESCALATE|DRAFT_REVIEW)$")
    reason: Optional[str] = Field(None, max_length=2000)
    note: Optional[str] = Field(None, max_length=4000)
    ai_snapshot: Optional[Dict[str, Any]] = None  # Snapshot ML/rules yang dilihat apoteker saat memutuskan


class ReviewResponse(BaseModel):
    status: str
    encounter_id: str
    action: str
    new_workflow_status: str
    row_version: int
    audit_entry_id: str
    idempotent: bool = False


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/{encounter_id}/review",
    response_model=ReviewResponse,
    summary="Aksi telaah apoteker (APPROVE/EDIT/REJECT/ESCALATE/DRAFT_REVIEW)",
)
async def submit_review(
    encounter_id: str,
    body: ReviewRequest,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    if_match: Optional[str] = Header(None, alias="If-Match"),
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.ADMIN)
    ),
):
    """
    Submit aksi telaah farmasi.

    Header opsional:
      - If-Match: <row_version> untuk optimistic locking
      - Idempotency-Key: UUID unik per request (deduplikasi)
    """
    with get_session() as session:
        # -----------------------------------------------------------------------
        # 1. Idempotency check
        # -----------------------------------------------------------------------
        if idempotency_key:
            prev = session.query(AuditEntry).filter(
                AuditEntry.reason_code == f"IDEM:{idempotency_key}"
            ).first()
            if prev:
                enc = session.query(Encounter).filter(Encounter.id == encounter_id).first()
                return ReviewResponse(
                    status="ok",
                    encounter_id=encounter_id,
                    action=body.action,
                    new_workflow_status=enc.workflow_status if enc else "UNKNOWN",
                    row_version=enc.row_version if enc else 0,
                    audit_entry_id=prev.id,
                    idempotent=True,
                )

        # -----------------------------------------------------------------------
        # 2. Load encounter
        # -----------------------------------------------------------------------
        enc = session.query(Encounter).filter(Encounter.id == encounter_id).first()
        if not enc:
            raise HTTPException(status_code=404, detail=f"Encounter {encounter_id} tidak ditemukan.")

        # -----------------------------------------------------------------------
        # 3. Optimistic concurrency
        # -----------------------------------------------------------------------
        if if_match is not None:
            try:
                expected = int(if_match)
                if enc.row_version != expected:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Konflik: data telah diperbarui (row_version {enc.row_version} ≠ {expected}). "
                            "Muat ulang dan coba lagi."
                        ),
                    )
            except ValueError:
                pass

        # -----------------------------------------------------------------------
        # 4. State transition (includes high-alert guard for APPROVE)
        # -----------------------------------------------------------------------
        to_status = _ACTION_TO_STATUS[body.action]
        if not (to_status == "DRAFT_REVIEW" and enc.workflow_status == "DRAFT_REVIEW"):
            state_transition(
                session=session,
                encounter=enc,
                to_status=to_status,
                actor_id=current_user.user_id,
                actor_type=current_user.actor_type,
                reason=body.reason,
                check_high_alert=(body.action == "APPROVE"),
            )

        # Sinkron antrean: selesai → CLOSED, eskalasi → PARKED_DPJP, draf → tetap diklaim
        sync_after_review(session, encounter_id, body.action)
        if body.action != "DRAFT_REVIEW":
            release_encounter_claim(session, encounter_id)

        # -----------------------------------------------------------------------
        # 5. Audit trail
        # -----------------------------------------------------------------------
        ai_snap = body.ai_snapshot or {}
        ai_snap["rule_version"] = _get_rule_version()
        ai_snap["model_version"] = _get_model_version()

        audit_entry = append_audit(
            session,
            action=body.action,
            actor_id=current_user.user_id,
            actor_type=current_user.actor_type,
            encounter_id=encounter_id,
            reason_code=f"IDEM:{idempotency_key}" if idempotency_key else body.action,
            note=body.note or body.reason,
            ai_snapshot=ai_snap,
            rule_version=_get_rule_version(),
            model_version=_get_model_version(),
            client_ip=request.client.host if request.client else None,
        )

        session.commit()

        return ReviewResponse(
            status="ok",
            encounter_id=encounter_id,
            action=body.action,
            new_workflow_status=enc.workflow_status,
            row_version=enc.row_version,
            audit_entry_id=audit_entry.id,
        )


# ---------------------------------------------------------------------------
# GET /api/v1/encounters/{encounter_id}/review/history
# ---------------------------------------------------------------------------

@router.get(
    "/{encounter_id}/review/history",
    summary="Riwayat aksi telaah untuk satu encounter",
)
async def get_review_history(
    encounter_id: str,
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.ADMIN, UserRole.AUDITOR)
    ),
):
    """Mengembalikan riwayat status dan audit untuk satu encounter."""
    with get_session() as session:
        enc = session.query(Encounter).filter(Encounter.id == encounter_id).first()
        if not enc:
            raise HTTPException(status_code=404, detail=f"Encounter {encounter_id} tidak ditemukan.")

        audit_rows = session.execute(
            sa.text(
                """
                SELECT id, action, actor_id, actor_type, reason_code, note, ts, timestamp
                FROM audit_entries
                WHERE encounter_id = :enc_id
                ORDER BY seq ASC
                """
            ),
            {"enc_id": encounter_id},
        ).fetchall()

        history = [
            {
                "audit_entry_id": row[0],
                "action": row[1],
                "actor_id": row[2],
                "actor_type": row[3],
                "reason_code": row[4],
                "note": row[5],
                "timestamp": row[7] if row[7] else row[6],  # Prefer timestamp (legacy) over ts
            }
            for row in audit_rows
        ]

        return {
            "encounter_id": encounter_id,
            "current_status": enc.workflow_status,
            "latest_tier": enc.latest_tier,
            "row_version": enc.row_version,
            "history": history,
        }


# ---------------------------------------------------------------------------
# GET /api/v1/audit/verify
# ---------------------------------------------------------------------------

audit_router = APIRouter(prefix="/audit", tags=["audit"])


@audit_router.get("/verify", summary="Verifikasi integritas rantai hash audit")
async def verify_audit_chain(
    full: bool = False,
    current_user: TokenData = Depends(
        require_roles(UserRole.AUDITOR, UserRole.ADMIN)
    ),
):
    """
    Verifikasi integritas rantai hash audit_entries.
    full=true: rehash setiap entri (lebih lambat, lebih akurat).
    """
    from api.services.audit_service import verify_chain, verify_chain_full
    with get_session() as session:
        if full:
            result = verify_chain_full(session)
        else:
            result = verify_chain(session)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_rule_version() -> str:
    try:
        import json as _json
        with open("configs/discrepancy_rules.json", encoding="utf-8") as fh:
            return _json.load(fh).get("rule_version", "unknown")
    except Exception:
        return "unknown"


def _get_model_version() -> str:
    try:
        import json as _json
        with open("models/metadata.json", encoding="utf-8") as fh:
            return _json.load(fh).get("model_version", "unknown")
    except Exception:
        return "unknown"
