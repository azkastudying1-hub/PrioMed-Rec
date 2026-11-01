"""
api/services/sla_service.py
-----------------------------
SLA tracking dan escalation logic (B-106).

SLA default (dari dokumen strategi Bagian 5.3):
  HIGH:   target 2 jam, warning 1 jam
  MEDIUM: target 8 jam, warning 4 jam
  LOW:    target 24 jam, warning 16 jam

Logika:
  - Setiap 60 detik APScheduler memanggil run_sla_check()
  - Cek semua encounter aktif (bukan terminal)
  - Buat SlaEvent jika warning/breach baru
  - Kirim Notification ke assigned_to atau semua apoteker
  - SLA floor dinaikkan ke tier berikutnya saat breach (via priority_service)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List

import sqlalchemy as sa

from api.db.models import Encounter, SlaEvent, Notification, SlaConfig
from api.db.session import session_scope as get_session


# ---------------------------------------------------------------------------
# Default SLA config (dipakai jika DB belum terisi)
# ---------------------------------------------------------------------------

DEFAULT_SLA_CONFIG: Dict[str, Dict[str, Any]] = {
    "HIGH":   {"target_hours": 2.0,  "warning_hours": 1.0,  "escalate_to_tier": None},
    "MEDIUM": {"target_hours": 8.0,  "warning_hours": 4.0,  "escalate_to_tier": "HIGH"},
    "LOW":    {"target_hours": 24.0, "warning_hours": 16.0, "escalate_to_tier": "MEDIUM"},
}

ACTIVE_STATUSES = {
    "MENUNGGU_BPMH", "BPMH_LENGKAP", "DALAM_ANALISIS",
    "MENUNGGU_TELAAH", "DRAFT_REVIEW", "RETRIAGE",
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hours_since(iso_ts: str) -> float:
    """Compute hours elapsed since an ISO 8601 UTC timestamp."""
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return delta.total_seconds() / 3600.0
    except Exception:
        return 0.0


def load_sla_config(session) -> Dict[str, Dict[str, Any]]:
    """Load SLA config from DB, fallback to defaults."""
    try:
        rows = session.query(SlaConfig).all()
        if not rows:
            return DEFAULT_SLA_CONFIG
        return {
            row.tier: {
                "target_hours": row.target_hours,
                "warning_hours": row.warning_hours,
                "escalate_to_tier": row.escalate_to_tier,
            }
            for row in rows
        }
    except Exception:
        return DEFAULT_SLA_CONFIG


def run_sla_check() -> Dict[str, Any]:
    """
    Main SLA check — dipanggil oleh APScheduler setiap 60 detik.

    Returns:
        {"checked": int, "warnings": int, "breaches": int, "errors": int}
    """
    checked = warnings = breaches = errors = 0

    try:
        with get_session() as session:
            sla_cfg = load_sla_config(session)

            # Fetch all active encounters
            encounters = session.execute(
                sa.text(
                    """
                    SELECT id, latest_tier, admitted_at, assigned_to, workflow_status
                    FROM encounters
                    WHERE workflow_status IN (
                        'MENUNGGU_BPMH','BPMH_LENGKAP','DALAM_ANALISIS',
                        'MENUNGGU_TELAAH','DRAFT_REVIEW','RETRIAGE'
                    )
                    """
                )
            ).fetchall()

            for enc in encounters:
                enc_id, tier, admitted_at, assigned_to, wf_status = enc
                checked += 1
                tier = (tier or "MEDIUM").upper()
                if tier not in sla_cfg:
                    tier = "MEDIUM"

                hours = _hours_since(admitted_at) if admitted_at else 0.0
                cfg = sla_cfg[tier]

                try:
                    # Check breach
                    if hours >= cfg["target_hours"]:
                        if _create_sla_event_if_new(session, enc_id, "BREACH", tier, hours, cfg["target_hours"]):
                            breaches += 1
                            _notify_sla(session, enc_id, assigned_to, "SLA_BREACH",
                                        f"SLA Breach: Encounter {enc_id[:8]} melewati batas {cfg['target_hours']}j")
                    # Check warning (only if not already breached)
                    elif hours >= cfg["warning_hours"]:
                        if _create_sla_event_if_new(session, enc_id, "WARNING", tier, hours, cfg["warning_hours"]):
                            warnings += 1
                            _notify_sla(session, enc_id, assigned_to, "SLA_WARNING",
                                        f"SLA Warning: Encounter {enc_id[:8]} mendekati batas ({hours:.1f}j/{cfg['target_hours']}j)")
                except Exception:
                    errors += 1

            session.commit()

    except Exception:
        errors += 1

    return {"checked": checked, "warnings": warnings, "breaches": breaches, "errors": errors}


def _create_sla_event_if_new(
    session, encounter_id: str, event_type: str, tier: str, wait_hours: float, target_hours: float
) -> bool:
    """
    Buat SlaEvent hanya jika belum ada event yang sama untuk encounter ini hari ini.
    Idempoten: tidak membuat duplikat event dalam satu hari yang sama.
    Returns True jika event baru dibuat.
    """
    # Check existing event of same type today
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing = session.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM sla_events
            WHERE encounter_id = :enc_id
              AND event_type = :evt_type
              AND occurred_at LIKE :today_prefix
            """
        ),
        {"enc_id": encounter_id, "evt_type": event_type, "today_prefix": f"{today}%"},
    ).scalar()

    if existing and int(existing) > 0:
        return False  # Sudah ada event hari ini

    event = SlaEvent(
        id=str(uuid.uuid4()),
        encounter_id=encounter_id,
        event_type=event_type,
        from_tier=tier,
        wait_hours=wait_hours,
        sla_target_hours=target_hours,
        occurred_at=_now_utc(),
        notified=False,
    )
    session.add(event)
    return True


def _notify_sla(
    session, encounter_id: str, assigned_to_user_id, notif_type: str, message: str
) -> None:
    """Buat notifikasi SLA. Jika tidak ada assigned, notifikasi ke semua PHARMACIST/COORDINATOR."""
    if assigned_to_user_id:
        user_ids = [assigned_to_user_id]
    else:
        rows = session.execute(
            sa.text("SELECT id FROM users WHERE role IN ('PHARMACIST','COORDINATOR') AND is_active=1")
        ).fetchall()
        user_ids = [r[0] for r in rows]

    for uid in user_ids:
        notif = Notification(
            id=str(uuid.uuid4()),
            user_id=uid,
            encounter_id=encounter_id,
            type=notif_type,
            title=notif_type.replace("_", " "),
            body=message,
            is_read=False,
            created_at=_now_utc(),
        )
        session.add(notif)
