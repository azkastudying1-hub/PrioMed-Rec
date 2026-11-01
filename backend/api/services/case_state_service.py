"""
api/services/case_state_service.py
------------------------------------
State machine untuk workflow encounter admisi (B-104).

Status:
  MENUNGGU_BPMH       → BPMH_LENGKAP (TTK/PHARMACIST submit BPMH)
  BPMH_LENGKAP        → DALAM_ANALISIS (sistem/auto trigger analisis)
  DALAM_ANALISIS      → MENUNGGU_TELAAH (analisis selesai)
  MENUNGGU_TELAAH     → DRAFT_REVIEW (pharmacist klaim & mulai telaah)
  DRAFT_REVIEW        → SELESAI_APPROVE | SELESAI_EDIT | ESKALASI
  MENUNGGU_TELAAH     → DITOLAK (edge: discarded without review)
  DRAFT_REVIEW        → DITOLAK
  Semua status (kecuali terminal) → RETRIAGE (re-analysis diperlukan)

Terminal states: SELESAI_APPROVE, SELESAI_EDIT, DITOLAK, ESKALASI

Prinsip keselamatan:
  - Guard menolak transisi tidak sah (HTTPException 422)
  - High-Alert belum dikonfirmasi memblokir APPROVE (S2/B-112)
  - Semua transisi dicatat di status_history (audit)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Set, Dict

from fastapi import HTTPException
from starlette import status

from api.db.models import Encounter, StatusHistory


# ---------------------------------------------------------------------------
# Definisi state machine
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: Dict[str, Set[str]] = {
    "MENUNGGU_BPMH":    {"BPMH_LENGKAP", "RETRIAGE"},
    "BPMH_LENGKAP":     {"DALAM_ANALISIS", "RETRIAGE"},
    "DALAM_ANALISIS":   {"MENUNGGU_TELAAH", "RETRIAGE"},
    "MENUNGGU_TELAAH":  {"DRAFT_REVIEW", "DITOLAK", "RETRIAGE"},
    "DRAFT_REVIEW":     {"SELESAI_APPROVE", "SELESAI_EDIT", "DITOLAK", "ESKALASI", "RETRIAGE"},
    # Terminal states — no forward transition (only RETRIAGE possible via admin)
    "SELESAI_APPROVE":  {"RETRIAGE"},
    "SELESAI_EDIT":     {"RETRIAGE"},
    "DITOLAK":          {"RETRIAGE"},
    "ESKALASI":         {"DRAFT_REVIEW", "RETRIAGE"},
    "RETRIAGE":         {"DALAM_ANALISIS", "MENUNGGU_TELAAH"},
}

TERMINAL_STATES: Set[str] = {"SELESAI_APPROVE", "SELESAI_EDIT", "DITOLAK"}

# Actions that require a mandatory reason field
REASON_REQUIRED_TRANSITIONS: Set[str] = {"DITOLAK", "ESKALASI", "SELESAI_EDIT"}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def transition(
    session,
    encounter: Encounter,
    to_status: str,
    actor_id: Optional[str],
    actor_type: str = "human",
    reason: Optional[str] = None,
    check_high_alert: bool = True,
) -> Encounter:
    """
    Lakukan transisi status encounter.

    Args:
        session: SQLAlchemy session (caller harus commit setelah pemanggilan ini).
        encounter: ORM Encounter object (harus dari session yang sama).
        to_status: Status tujuan.
        actor_id: ID pengguna dari token (bukan body).
        actor_type: "human" | "system" | "agent_via_mcp"
        reason: Wajib untuk DITOLAK, ESKALASI, SELESAI_EDIT.
        check_high_alert: Jika True, blokir SELESAI_APPROVE bila ada high-alert belum dikonfirmasi.

    Returns:
        encounter yang telah diperbarui (belum di-commit).

    Raises:
        HTTPException 422: transisi tidak sah atau guard gagal.
    """
    from_status = encounter.workflow_status

    # 1. Validate transition
    allowed = VALID_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Transisi tidak sah: '{from_status}' → '{to_status}'. "
                f"Transisi yang diizinkan: {sorted(allowed)}"
            ),
        )

    # 2. Reason required guard
    if to_status in REASON_REQUIRED_TRANSITIONS and not reason:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Alasan wajib diisi untuk transisi ke '{to_status}'.",
        )

    # 3. High-Alert hard stop for APPROVE (S2, B-112)
    if to_status == "SELESAI_APPROVE" and check_high_alert:
        _check_high_alert_clearance(session, encounter.id)

    # 4. Apply transition
    encounter.workflow_status = to_status
    encounter.updated_at = _now_utc()
    encounter.row_version = (encounter.row_version or 0) + 1

    # 5. Record in status_history
    history = StatusHistory(
        id=str(uuid.uuid4()),
        encounter_id=encounter.id,
        from_status=from_status,
        to_status=to_status,
        changed_by=actor_id,
        changed_by_type=actor_type,
        reason=reason,
        changed_at=_now_utc(),
    )
    session.add(history)

    return encounter


def _check_high_alert_clearance(session, encounter_id: str) -> None:
    """
    Periksa apakah ada diskrepansi high-alert yang belum dikonfirmasi.
    Memblokir APPROVE jika ditemukan (S2, B-112).
    """
    import sqlalchemy as sa
    from api.db.models import Discrepancy

    unconfirmed = session.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM discrepancies
            WHERE encounter_id = :enc_id
              AND is_high_alert = 1
              AND is_relevant IS NULL
            """
        ),
        {"enc_id": encounter_id},
    ).scalar()

    if unconfirmed and int(unconfirmed) > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"APPROVE ditolak: terdapat {unconfirmed} diskrepansi high-alert "
                "yang belum dikonfirmasi relevansinya oleh apoteker. "
                "Konfirmasi setiap temuan high-alert sebelum menyetujui."
            ),
        )


def can_transition(from_status: str, to_status: str) -> bool:
    """Check (non-raising) whether a transition is allowed."""
    return to_status in VALID_TRANSITIONS.get(from_status, set())
