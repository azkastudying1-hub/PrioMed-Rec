"""
api/tasks/queue_tick.py
-------------------------
Tick antrean 60 detik — batch scoring, SLA escalation, lease cleanup.

Dijalankan oleh APScheduler (idempoten, aman dua instance).
Tidak memanggil LLM/Langflow (ADR-20, Q5).

Alur tick():
  1. Fetch semua OPEN/CLAIMED entries (≤~5.000)
  2. Hitung ulang priority_score (batch_rescore)
  3. Naikan tier entri yang next_due_at ≤ now (SLA escalation)
  4. Catat sla_events untuk eskalasi baru
  5. Bersihkan klaim yang kedaluwarsa (→ OPEN, usia tetap)
  6. Bulk update ke DB dalam satu transaksi
  7. Tulis queue_events (diff untuk SSE)

Target: < 800 ms untuk 5.000 entri (G5, diukur di Q-012).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import sqlalchemy as sa

from priomedrec_core.queue_config import DEFAULT_CONFIG, QueueConfig
from priomedrec_core.queue_engine import batch_rescore, TIER_FROM_RANK, TIER_RANK
from priomedrec_core.queue_transitions import expire_claim

logger = logging.getLogger("priomed.queue_tick")

# Global queue_version counter untuk monoton lintas tick
# Di produksi multi-instance, gunakan sequence DB atau Redis INCR
_GLOBAL_QUEUE_VERSION = 0


def _now_utc_str() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def run_queue_tick(cfg: QueueConfig = DEFAULT_CONFIG) -> Dict[str, Any]:
    """
    Main queue tick — dipanggil APScheduler setiap 60 detik.

    Returns: {"checked": int, "rescored": int, "escalated": int, "expired": int, "errors": int}
    Idempoten: jalankan dua kali pada input yang sama → hasil yang sama.
    """
    global _GLOBAL_QUEUE_VERSION
    t_start = time.perf_counter()
    checked = rescored = escalated = expired = errors = 0

    try:
        from api.db.session import session_scope as get_session
        from api.db.models import QueueEntry, QueueEvent, SlaEvent, Encounter

        with get_session() as session:
            now = _now_dt()
            now_iso = now.isoformat()

            # ---------------------------------------------------------------
            # Step 1: Fetch semua OPEN/CLAIMED entries
            # ---------------------------------------------------------------
            rows = session.query(QueueEntry).filter(
                QueueEntry.state.in_(["OPEN", "CLAIMED"])
            ).all()
            checked = len(rows)

            if not rows:
                return _result(checked, rescored, escalated, expired, errors, t_start)

            # ---------------------------------------------------------------
            # Step 2: Batch rescore
            # ---------------------------------------------------------------
            entries_dict: List[Dict[str, Any]] = [
                {
                    "encounter_id":     e.encounter_id,
                    "queue_type":       e.queue_type,
                    "ward":             e.ward,
                    "state":            e.state,
                    "tier_rank":        e.tier_rank,
                    "tier_source":      e.tier_source,
                    "priority_score":   e.priority_score or 0.0,
                    "ml_score":         0.5,  # default jika tidak disimpan di QueueEntry
                    "admitted_at":      e.admitted_at,
                    "discharge_planned_at": e.discharge_planned_at,
                    "discrepancy_counts": {},
                    "next_due_at":      e.next_due_at,
                    "claim_expires_at": e.claim_expires_at,
                    "claimed_by":       e.claimed_by,
                    "queue_version":    e.queue_version,
                }
                for e in rows
            ]

            rescored_entries = batch_rescore(entries_dict, now, cfg)
            rescored = len(rescored_entries)

            # Index untuk lookup cepat
            entry_map = {e.encounter_id: e for e in rows}
            rescored_map = {e["encounter_id"]: e for e in rescored_entries}

            # ---------------------------------------------------------------
            # Step 3 & 4: SLA escalation — entri yang next_due_at ≤ now
            # ---------------------------------------------------------------
            for enc_id, new_data in rescored_map.items():
                db_entry = entry_map.get(enc_id)
                if not db_entry:
                    continue

                next_due = db_entry.next_due_at
                sla_escalated = False

                if next_due:
                    try:
                        due_dt = datetime.fromisoformat(next_due.replace("Z", "+00:00"))
                        if due_dt.tzinfo is None:
                            due_dt = due_dt.replace(tzinfo=timezone.utc)
                        if now >= due_dt:
                            # SLA threshold terlewati → cek perlu escalation
                            old_rank = db_entry.tier_rank
                            new_rank = new_data.get("tier_rank", old_rank)

                            # SLA hanya menaikkan tier (termasuk dari RULE MEDIUM)
                            if new_rank > old_rank and old_rank < 2:
                                db_entry.tier_rank   = new_rank
                                db_entry.tier_source = "SLA"
                                sla_escalated = True
                                escalated += 1

                                # Catat sla_event
                                _create_sla_event_if_new(
                                    session,
                                    enc_id,
                                    "ESCALATED",
                                    TIER_FROM_RANK.get(old_rank, "LOW"),
                                    TIER_FROM_RANK.get(new_rank, "MEDIUM"),
                                    now_iso,
                                )
                                # Queue event
                                _append_queue_event(session, enc_id, "promote", {
                                    "from_tier": old_rank,
                                    "to_tier": new_rank,
                                    "reason": "SLA",
                                })

                                # Sinkronkan tier encounter agar Worklist ikut naik.
                                encounter = session.query(Encounter).filter(
                                    Encounter.id == enc_id
                                ).first()
                                if encounter is not None:
                                    current_rank = TIER_RANK.get(
                                        str(encounter.latest_tier or "LOW").upper(), 0
                                    )
                                    if new_rank > current_rank:
                                        encounter.latest_tier = TIER_FROM_RANK.get(
                                            new_rank, "MEDIUM"
                                        )
                                    encounter.updated_at = now_iso
                    except Exception as exc:
                        logger.debug(f"[tick] Error parsing next_due_at {enc_id}: {exc}")
                        errors += 1

                # Update priority_score + next_due_at
                db_entry.priority_score = new_data.get("priority_score", db_entry.priority_score)
                db_entry.next_due_at    = new_data.get("next_due_at")
                db_entry.queue_version  = (db_entry.queue_version or 0) + 1
                db_entry.updated_at     = now_iso

            # ---------------------------------------------------------------
            # Step 5: Bersihkan klaim kedaluwarsa
            # ---------------------------------------------------------------
            for enc_id, db_entry in entry_map.items():
                if db_entry.state != "CLAIMED":
                    continue
                expires_at = db_entry.claim_expires_at
                if not expires_at:
                    continue
                try:
                    exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                    if now >= exp_dt:
                        # Lease kedaluwarsa → kembali ke OPEN
                        old_claimed_by = db_entry.claimed_by
                        existing = {
                            "encounter_id":  db_entry.encounter_id,
                            "admitted_at":   db_entry.admitted_at,
                            "queue_version": db_entry.queue_version,
                            "state":         "CLAIMED",
                            "claimed_by":    old_claimed_by,
                            "claim_expires_at": expires_at,
                        }
                        updated, event_dict = expire_claim(existing, now=now, cfg=cfg)

                        db_entry.state           = "OPEN"
                        db_entry.claimed_by      = None
                        db_entry.claim_expires_at = None
                        db_entry.queue_version   = (db_entry.queue_version or 0) + 1
                        db_entry.updated_at      = now_iso
                        expired += 1

                        import json
                        _append_queue_event(session, enc_id, "expire", {
                            "action": "claim_expired",
                            "was_claimed_by": old_claimed_by,
                        })
                except Exception as exc:
                    logger.debug(f"[tick] Error expiring claim {enc_id}: {exc}")
                    errors += 1

            # ---------------------------------------------------------------
            # Step 6: Commit dalam satu transaksi
            # ---------------------------------------------------------------
            session.commit()

    except Exception as exc:
        logger.error(f"[queue_tick] Fatal error: {exc}", exc_info=True)
        errors += 1

    result = _result(checked, rescored, escalated, expired, errors, t_start)
    elapsed_ms = round((time.perf_counter() - t_start) * 1000, 1)
    logger.info(
        f"[queue_tick] checked={checked} rescored={rescored} "
        f"escalated={escalated} expired={expired} errors={errors} {elapsed_ms}ms"
    )
    return result


def _result(checked, rescored, escalated, expired, errors, t_start) -> Dict[str, Any]:
    elapsed_ms = round((time.perf_counter() - t_start) * 1000, 1)
    return {
        "checked":   checked,
        "rescored":  rescored,
        "escalated": escalated,
        "expired":   expired,
        "errors":    errors,
        "elapsed_ms": elapsed_ms,
    }


def _create_sla_event_if_new(
    session, encounter_id: str, event_type: str,
    from_tier: str, to_tier: str, now_iso: str,
) -> bool:
    """Catat SlaEvent baru jika belum ada untuk hari ini."""
    import sqlalchemy as sa
    today = now_iso[:10]
    try:
        existing = session.execute(sa.text(
            "SELECT COUNT(*) FROM sla_events "
            "WHERE encounter_id=:enc AND event_type=:evt AND occurred_at LIKE :today"
        ), {"enc": encounter_id, "evt": event_type, "today": f"{today}%"}).scalar()
        if existing and int(existing) > 0:
            return False

        import uuid
        from api.db.models import SlaEvent
        ev = SlaEvent(
            id           = str(uuid.uuid4()),
            encounter_id = encounter_id,
            event_type   = event_type,
            from_tier    = from_tier,
            to_tier      = to_tier,
            occurred_at  = now_iso,
            notified     = False,
        )
        session.add(ev)
        return True
    except Exception:
        return False


def _append_queue_event(session, encounter_id: str, kind: str, payload: dict) -> None:
    import json
    from api.db.models import QueueEvent
    ev = QueueEvent(
        encounter_id = encounter_id,
        kind         = kind,
        payload_json = json.dumps(payload, ensure_ascii=False),
        at           = _now_utc_str(),
    )
    session.add(ev)
