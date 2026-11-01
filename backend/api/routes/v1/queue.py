"""
api/routes/v1/queue.py
------------------------
Endpoint antrean manajemen skala RS (Q-004, Q-010, Q-011).

GET  /queue                 — Daftar antrean (keyset pagination)
POST /queue/next            — Ambil & klaim entri teratas (atomik)
POST /queue/{id}/heartbeat  — Perpanjang lease
POST /queue/{id}/release    — Lepas klaim
POST /queue/{id}/admit      — Ingest encounter baru (dari SIM-RS / simulator)
POST /queue/{id}/discharge  — Pasien pulang → CLOSED + missed_rec
POST /queue/{id}/transfer   — Pindah bangsal → re-triage
POST /queue/{id}/bpmh_submit— BPMH selesai → pindah A→B
POST /queue/{id}/cancel     — Batal admisi
GET  /queue/metrics         — Metrik antrean (backlog, WIP, SLA, missed_rec)

Keselamatan:
  Q5: Tidak ada panggilan LLM/Langflow (ADR-20).
  Q1: tier HIGH(RULE) tidak pernah turun.
  Q7: missed_reconciliation dicatat saat discharge sebelum selesai.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from api.auth.rbac import TokenData, require_roles, UserRole
from api.db.session import session_scope as get_session
from api.services.queue_service import (
    get_queue,
    next_for_user,
    heartbeat,
    release_claim,
    admit_encounter,
    discharge_encounter,
    get_metrics,
    lab_critical_event,
    order_change_event,
)
from api.services.queue_view_service import (
    advance_encounter,
    enrich_entries,
    enrich_one,
    get_command_center,
    get_my_queue,
    release_encounter_claim,
)

router = APIRouter(prefix="/queue", tags=["queue"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class QueueItemResponse(BaseModel):
    encounter_id:        str
    queue_type:          str
    ward:                str
    state:               str
    tier_rank:           int
    tier_source:         str
    priority_score:      float
    ml_percentile:       Optional[float] = None
    depth_level:         int
    admitted_at:         str
    sla_due_at:          Optional[str] = None
    next_due_at:         Optional[str] = None
    discharge_planned_at: Optional[str] = None
    claimed_by:          Optional[str] = None
    claim_expires_at:    Optional[str] = None
    queue_version:       int

    # Diperkaya oleh queue_view_service (data pasien, SLA, alasan prioritas)
    tier:                Optional[str] = None
    patient_id:          Optional[str] = None
    patient_name:        Optional[str] = None
    dpjp_name:           Optional[str] = None
    ml_score:            Optional[float] = None
    workflow_status:     Optional[str] = None
    row_version:         int = 0
    priority_reasons:    List[Dict[str, Any]] = []
    hours_waiting:       Optional[float] = None
    sla_target_hours:    Optional[float] = None
    sla_ratio:           Optional[float] = None
    claimed_by_name:     Optional[str] = None
    lease_seconds_left:  Optional[int] = None
    why:                 List[str] = []

    model_config = {"from_attributes": True}


class QueueListResponse(BaseModel):
    items:       List[QueueItemResponse]
    has_next:    bool
    next_cursor: Optional[str] = None
    count:       int
    total:       int = 0


class AdmitRequest(BaseModel):
    ward:             str
    admitted_at:      str
    ml_score:         Optional[float] = None
    has_rule_finding: bool = False


class DischargeRequest(BaseModel):
    workflow_status: str
    reason:          str = "DISCHARGE_BEFORE_REVIEW"


class TransferRequest(BaseModel):
    new_ward:         str
    has_rule_finding: bool = False
    ml_score:         Optional[float] = None


class BpmhSubmitRequest(BaseModel):
    has_rule_finding:   bool = False
    is_high_alert:      bool = False
    discrepancy_counts: Optional[Dict[str, int]] = None
    ml_score:           Optional[float] = None


class LabCriticalRequest(BaseModel):
    lab_type:  str
    lab_value: Optional[str] = None


class OrderChangeRequest(BaseModel):
    order_details:    Optional[Dict[str, Any]] = None
    has_rule_finding: bool = False


# ---------------------------------------------------------------------------
# GET /queue
# ---------------------------------------------------------------------------

@router.get("", response_model=QueueListResponse, summary="Daftar antrean (keyset)")
async def list_queue(
    queue_type:   Optional[str] = Query(None,   description="BPMH | REVIEW"),
    ward:         Optional[str] = Query(None,   description="Filter bangsal"),
    tier:         Optional[str] = Query(None,   description="HIGH | MEDIUM | LOW"),
    state:        Optional[str] = Query("OPEN", description="OPEN | CLAIMED | PARKED_DPJP | CLOSED"),
    search:       Optional[str] = Query(None,   description="Cari nama/ID pasien atau encounter"),
    after_cursor: Optional[str] = Query(None,   description="Keyset cursor dari response sebelumnya"),
    limit:        int           = Query(50, ge=1, le=100),
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.TECHNICIAN,
                      UserRole.COORDINATOR, UserRole.ADMIN, UserRole.AUDITOR)
    ),
):
    """
    Ambil daftar antrean dengan keyset pagination.
    Urutan: tier_rank↓, priority_score↓, admitted_at↑, encounter_id↑.
    """
    with get_session() as session:
        result = get_queue(
            session,
            queue_type=queue_type,
            ward=ward,
            tier=tier,
            state=state,
            search=search,
            after_cursor=after_cursor,
            limit=limit,
        )
        enrich_entries(session, result["items"])
    return QueueListResponse(**result)


# ---------------------------------------------------------------------------
# GET /queue/mine — Antrean Saya
# ---------------------------------------------------------------------------

@router.get("/mine", summary="Antrean Saya: klaim aktif + pratinjau berikutnya")
async def queue_mine(
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.TECHNICIAN, UserRole.COORDINATOR, UserRole.ADMIN)
    ),
):
    with get_session() as session:
        return get_my_queue(session, current_user.user_id)


# ---------------------------------------------------------------------------
# GET /queue/command-center — koordinator
# ---------------------------------------------------------------------------

@router.get("/command-center", summary="Data Command Center (kapasitas, panas bangsal, aging, risiko SLA)")
async def queue_command_center(
    pharmacists: Optional[int] = Query(None, ge=1, le=100,
                                       description="Apoteker bertugas (what-if kapasitas)"),
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.ADMIN, UserRole.AUDITOR)
    ),
):
    with get_session() as session:
        return get_command_center(session, pharmacists=pharmacists)


# ---------------------------------------------------------------------------
# POST /queue/next
# ---------------------------------------------------------------------------

@router.post("/next", summary="Ambil & klaim entri teratas (atomik)")
async def queue_next(
    queue_type:  str        = Query("REVIEW", description="BPMH | REVIEW"),
    ward_scope:  Optional[str] = Query(None, description="Koma-separated bangsal, kosong=semua"),
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.TECHNICIAN)
    ),
):
    """
    Ambil entri teratas dari antrean dan klaim atomik.
    Lease 15 menit; perpanjang via /heartbeat.
    TTK hanya boleh menarik Antrean A (BPMH); Antrean B (Telaah) khusus apoteker/koordinator.

    G3: Tidak mungkin dua pengguna mendapat encounter yang sama.
    """
    qt = queue_type.upper()
    if qt not in ("BPMH", "REVIEW"):
        raise HTTPException(status_code=422, detail="queue_type harus BPMH atau REVIEW.")
    if current_user.role == UserRole.TECHNICIAN and qt != "BPMH":
        raise HTTPException(
            status_code=403,
            detail="TTK hanya dapat mengambil pasien dari Antrean BPMH.",
        )
    scope = [w.strip() for w in ward_scope.split(",") if w.strip()] if ward_scope else None

    with get_session() as session:
        entry = next_for_user(
            session,
            user_id=current_user.user_id,
            queue_type=qt,
            ward_scope=scope,
        )
        if entry is not None and qt == "REVIEW":
            # Telaah dimulai: encounter masuk DRAFT_REVIEW agar aksi telaah sah di state machine.
            advance_encounter(
                session, entry["encounter_id"], "DRAFT_REVIEW",
                actor_id=current_user.user_id, claimed_by=current_user.user_id,
            )
        entry = enrich_one(session, entry)
        session.commit()

    if entry is None:
        return {"message": "Antrean kosong atau tidak ada entri yang sesuai cakupan."}

    return entry


# ---------------------------------------------------------------------------
# POST /queue/{encounter_id}/heartbeat
# ---------------------------------------------------------------------------

@router.post("/{encounter_id}/heartbeat", summary="Perpanjang lease klaim")
async def queue_heartbeat(
    encounter_id: str,
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.TECHNICIAN)
    ),
):
    with get_session() as session:
        try:
            result = heartbeat(session, encounter_id, current_user.user_id)
            session.commit()
        except ValueError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
    return result


# ---------------------------------------------------------------------------
# POST /queue/{encounter_id}/release
# ---------------------------------------------------------------------------

@router.post("/{encounter_id}/release", summary="Lepas klaim")
async def queue_release(
    encounter_id: str,
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.ADMIN, UserRole.TECHNICIAN)
    ),
):
    with get_session() as session:
        try:
            result = release_claim(
                session, encounter_id,
                user_id=current_user.user_id,
                user_role=current_user.role,
            )
            release_encounter_claim(session, encounter_id)
            session.commit()
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
    return result


# ---------------------------------------------------------------------------
# POST /queue/{encounter_id}/resume — DPJP merespons, kembali ke antrean
# ---------------------------------------------------------------------------

@router.post("/{encounter_id}/resume", summary="Kembalikan kasus PARKED_DPJP ke antrean")
async def queue_resume(
    encounter_id: str,
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.ADMIN)
    ),
):
    from priomedrec_core.queue_transitions import unpark_dpjp as _unpark
    from api.db.models import QueueEntry
    from api.services.queue_service import _entry_to_dict, _append_event

    with get_session() as session:
        entry = session.query(QueueEntry).filter(
            QueueEntry.encounter_id == encounter_id
        ).first()
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry tidak ditemukan.")
        if entry.state != "PARKED_DPJP":
            raise HTTPException(status_code=409, detail="Entri tidak sedang menunggu DPJP.")
        updated, event_dict = _unpark(_entry_to_dict(entry))
        entry.state         = "OPEN"
        entry.queue_version = updated["queue_version"]
        entry.next_due_at   = updated.get("next_due_at")
        entry.updated_at    = updated["updated_at"]
        payload = json.loads(event_dict["payload_json"])
        payload.update({"ward": entry.ward, "queue_type": entry.queue_type})
        _append_event(session, encounter_id, event_dict["kind"], payload)
        session.commit()
    return {"encounter_id": encounter_id, "state": "OPEN"}


# ---------------------------------------------------------------------------
# POST /queue/{encounter_id}/admit  (Q-010)
# ---------------------------------------------------------------------------

@router.post("/{encounter_id}/admit", summary="Ingest encounter baru ke antrean")
async def queue_admit(
    encounter_id: str,
    body: AdmitRequest,
    current_user: TokenData = Depends(
        require_roles(UserRole.TECHNICIAN, UserRole.PHARMACIST,
                      UserRole.COORDINATOR, UserRole.ADMIN)
    ),
):
    """
    Masukkan encounter baru ke Antrean A (BPMH).
    Idempoten: panggilan berulang dengan encounter_id yang sama tidak membuat duplikat.
    """
    with get_session() as session:
        result = admit_encounter(
            session,
            encounter_id=encounter_id,
            ward=body.ward,
            admitted_at=body.admitted_at,
            ml_score=body.ml_score,
            has_rule_finding=body.has_rule_finding,
        )
        session.commit()
    return result


# ---------------------------------------------------------------------------
# POST /queue/{encounter_id}/discharge  (Q-010)
# ---------------------------------------------------------------------------

@router.post("/{encounter_id}/discharge", summary="Pasien pulang → CLOSED + missed_rec")
async def queue_discharge(
    encounter_id: str,
    body: DischargeRequest,
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.ADMIN)
    ),
):
    """
    Tutup entri saat pasien pulang.
    Q7: Jika rekonsiliasi belum selesai, catat missed_reconciliation.
    """
    with get_session() as session:
        result = discharge_encounter(
            session,
            encounter_id=encounter_id,
            workflow_status=body.workflow_status,
            reason=body.reason,
        )
        session.commit()
    return result


# ---------------------------------------------------------------------------
# POST /queue/{encounter_id}/transfer  (Q-010)
# ---------------------------------------------------------------------------

@router.post("/{encounter_id}/transfer", summary="Pindah bangsal → re-triage")
async def queue_transfer(
    encounter_id: str,
    body: TransferRequest,
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.ADMIN)
    ),
):
    """
    Re-triage saat transfer bangsal. Klaim dilepas; lantai RULE dipertahankan.
    """
    from priomedrec_core.queue_transitions import transfer as _transfer
    with get_session() as session:
        from api.db.models import QueueEntry
        entry = session.query(QueueEntry).filter(
            QueueEntry.encounter_id == encounter_id
        ).first()
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry tidak ditemukan.")

        from api.services.queue_service import _entry_to_dict, _append_event
        entry_dict = _entry_to_dict(entry)
        updated, event_dict = _transfer(
            entry_dict, body.new_ward,
            has_rule_finding=body.has_rule_finding,
            ml_score=body.ml_score,
        )
        entry.ward           = updated["ward"]
        entry.tier_rank      = updated["tier_rank"]
        entry.tier_source    = updated["tier_source"]
        entry.state          = "OPEN"
        entry.claimed_by     = None
        entry.claim_expires_at = None
        entry.priority_score = updated["priority_score"]
        entry.queue_version  = updated["queue_version"]
        entry.updated_at     = updated["updated_at"]

        _append_event(session, encounter_id, event_dict["kind"],
                      json.loads(event_dict["payload_json"]))
        session.commit()
    return updated


# ---------------------------------------------------------------------------
# POST /queue/{encounter_id}/bpmh_submit  (Q-010)
# ---------------------------------------------------------------------------

@router.post("/{encounter_id}/bpmh_submit", summary="BPMH selesai → pindah A→B")
async def queue_bpmh_submit(
    encounter_id: str,
    body: BpmhSubmitRequest,
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.TECHNICIAN, UserRole.COORDINATOR)
    ),
):
    """
    Pindahkan encounter dari Antrean A (BPMH) ke Antrean B (REVIEW).
    Hitung ulang tier berdasarkan temuan Fase B.
    ADR-21: tier hanya naik.
    """
    from priomedrec_core.queue_transitions import bpmh_submit as _bpmh_submit
    with get_session() as session:
        from api.db.models import QueueEntry
        from api.services.queue_service import _entry_to_dict, _append_event

        entry = session.query(QueueEntry).filter(
            QueueEntry.encounter_id == encounter_id
        ).first()
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry tidak ditemukan.")

        entry_dict = _entry_to_dict(entry)
        updated, event_dict = _bpmh_submit(
            entry_dict,
            has_rule_finding=body.has_rule_finding,
            is_high_alert=body.is_high_alert,
            discrepancy_counts=body.discrepancy_counts,
            ml_score=body.ml_score,
        )

        entry.queue_type      = "REVIEW"
        entry.state           = "OPEN"
        entry.tier_rank       = updated["tier_rank"]
        entry.tier_source     = updated["tier_source"]
        entry.priority_score  = updated["priority_score"]
        entry.claimed_by      = None
        entry.claim_expires_at = None
        entry.queue_version   = updated["queue_version"]
        entry.updated_at      = updated["updated_at"]

        _append_event(session, encounter_id, event_dict["kind"],
                      json.loads(event_dict["payload_json"]))
        # Sinkron: BPMH selesai → encounter siap ditelaah (MENUNGGU_TELAAH)
        advance_encounter(session, encounter_id, "MENUNGGU_TELAAH")
        release_encounter_claim(session, encounter_id)
        session.commit()
    return updated


# ---------------------------------------------------------------------------
# POST /queue/{encounter_id}/cancel  (Q-010)
# ---------------------------------------------------------------------------

@router.post("/{encounter_id}/cancel", summary="Batal admisi")
async def queue_cancel(
    encounter_id: str,
    reason: str = Query("CANCEL_ADMISSION"),
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.ADMIN)
    ),
):
    from priomedrec_core.queue_transitions import cancel as _cancel
    with get_session() as session:
        from api.db.models import QueueEntry
        from api.services.queue_service import _entry_to_dict, _append_event

        entry = session.query(QueueEntry).filter(
            QueueEntry.encounter_id == encounter_id
        ).first()
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry tidak ditemukan.")

        entry_dict = _entry_to_dict(entry)
        updated, event_dict = _cancel(entry_dict, reason=reason)

        entry.state          = "CLOSED"
        entry.claimed_by     = None
        entry.claim_expires_at = None
        entry.queue_version  = updated["queue_version"]
        entry.updated_at     = updated["updated_at"]

        _append_event(session, encounter_id, event_dict["kind"],
                      json.loads(event_dict["payload_json"]))
        session.commit()
    return updated


# ---------------------------------------------------------------------------
# POST /queue/{encounter_id}/lab_critical  (Q-010)
# ---------------------------------------------------------------------------

@router.post("/{encounter_id}/lab_critical", summary="Eskalasi hasil lab kritis")
async def queue_lab_critical(
    encounter_id: str,
    body: LabCriticalRequest,
    current_user: TokenData = Depends(
        require_roles(UserRole.TECHNICIAN, UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.ADMIN)
    ),
):
    with get_session() as session:
        result = lab_critical_event(
            session, encounter_id, lab_type=body.lab_type, lab_value=body.lab_value
        )
        session.commit()
    return result


# ---------------------------------------------------------------------------
# POST /queue/{encounter_id}/order_change  (Q-010)
# ---------------------------------------------------------------------------

@router.post("/{encounter_id}/order_change", summary="Pembaruan order obat dokter")
async def queue_order_change(
    encounter_id: str,
    body: OrderChangeRequest,
    current_user: TokenData = Depends(
        require_roles(UserRole.TECHNICIAN, UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.ADMIN)
    ),
):
    with get_session() as session:
        result = order_change_event(
            session, encounter_id, order_details=body.order_details, has_rule_finding=body.has_rule_finding
        )
        session.commit()
    return result


# ---------------------------------------------------------------------------
# GET /queue/metrics  (Q-011)
# ---------------------------------------------------------------------------

@router.get("/metrics", summary="Metrik antrean (backlog, WIP, SLA, missed_rec)")
async def queue_metrics(
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR,
                      UserRole.ADMIN, UserRole.AUDITOR)
    ),
):
    """
    Metrik antrean real-time (cache 10 detik).
    Mencakup: backlog per tier, WIP, distribusi usia, kepatuhan SLA HIGH,
    missed reconciliation, klaim kedaluwarsa, rasio tier_source.
    """
    with get_session() as session:
        result = get_metrics(session)
    return result
