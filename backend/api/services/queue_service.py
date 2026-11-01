"""
api/services/queue_service.py
-------------------------------
Layer database untuk operasi antrean.

Dipisahkan dari route handler agar dapat diuji unit tanpa HTTP overhead.
Semua operasi atomik (SELECT + UPDATE dalam satu transaksi).

Fungsi utama:
  get_queue()         — GET /queue (keyset pagination)
  next_for_user()     — POST /queue/next (atomik, 0 duplikat)
  heartbeat()         — perpanjang lease
  release_claim()     — lepas klaim manual
  admit_encounter()   — admit → queue_entries (BPMH)
  discharge_encounter() — discharge → CLOSED + missed_rec
  get_metrics()       — agregasi metrik (cache 10 dtk)

Q5: Tidak ada panggilan LLM/Langflow di sini (ADR-20).
Q1: Lantai RULE tidak pernah turun (via queue_transitions, bukan di sini).
"""
from __future__ import annotations

import base64
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import sqlalchemy as sa
from sqlalchemy.orm import Session

from api.db.models import Encounter, QueueEntry, QueueEvent, MissedReconciliation, User
from priomedrec_core.queue_config import DEFAULT_CONFIG, QueueConfig
from priomedrec_core.queue_transitions import (
    admit as _admit_transition,
    discharge as _discharge_transition,
    expire_claim as _expire_transition,
)
from priomedrec_core.queue_engine import sort_queue

# ---------------------------------------------------------------------------
# Konstanta
# ---------------------------------------------------------------------------

OPEN_STATES = {"OPEN", "CLAIMED", "PARKED_DPJP"}
_metrics_cache: Dict[str, Any] = {}
_METRICS_TTL = 10  # sekunder


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _synthetic_initials(encounter_id: str) -> str:
    """Inisial sintetis deterministik (privasi) untuk encounter tanpa nama — data simulasi."""
    letters = "ABCDEFGHJKLMNPRSTUWY"
    h = sum(ord(c) * (i + 3) for i, c in enumerate(encounter_id))
    return f"{letters[h % len(letters)]}.{letters[(h // 7) % len(letters)]}."


# ---------------------------------------------------------------------------
# Keyset cursor helpers
# ---------------------------------------------------------------------------

def encode_cursor(tier_rank: int, priority_score: float, encounter_id: str) -> str:
    payload = json.dumps(
        {"t": tier_rank, "s": round(priority_score, 4), "e": encounter_id},
        separators=(",", ":"),
    )
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> Optional[Tuple[int, float, str]]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return payload["t"], float(payload["s"]), payload["e"]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# GET /queue — keyset pagination
# ---------------------------------------------------------------------------

def get_queue(
    session: Session,
    queue_type: Optional[str] = None,
    ward: Optional[str] = None,
    tier: Optional[str] = None,
    state: Optional[str] = "OPEN",
    search: Optional[str] = None,
    after_cursor: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Ambil daftar antrean dengan keyset pagination.

    Keyset key: (tier_rank DESC, priority_score DESC, encounter_id ASC)
    Lebih stabil dari OFFSET — baris baru tidak menggeser halaman.
    """
    query = session.query(QueueEntry)

    if queue_type:
        query = query.filter(QueueEntry.queue_type == queue_type.upper())
    if ward:
        query = query.filter(QueueEntry.ward == ward)
    if state:
        query = query.filter(QueueEntry.state == state)
    if tier:
        tier_rank_map = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
        tr = tier_rank_map.get(tier.upper())
        if tr is not None:
            query = query.filter(QueueEntry.tier_rank == tr)
    if search and search.strip():
        like = f"%{search.strip()}%"
        query = query.join(Encounter, Encounter.id == QueueEntry.encounter_id).filter(
            sa.or_(
                QueueEntry.encounter_id.like(like),
                Encounter.patient_id.like(like),
                Encounter.patient_name.like(like),
            )
        )

    total = query.count()

    # Keyset pagination
    if after_cursor:
        decoded = decode_cursor(after_cursor)
        if decoded:
            prev_tier, prev_score, prev_enc = decoded
            # Ambil baris setelah (tier_rank, priority_score, encounter_id)
            query = query.filter(
                sa.or_(
                    QueueEntry.tier_rank < prev_tier,
                    sa.and_(
                        QueueEntry.tier_rank == prev_tier,
                        QueueEntry.priority_score < prev_score,
                    ),
                    sa.and_(
                        QueueEntry.tier_rank == prev_tier,
                        QueueEntry.priority_score == prev_score,
                        QueueEntry.encounter_id > prev_enc,
                    ),
                )
            )

    query = query.order_by(
        QueueEntry.tier_rank.desc(),
        QueueEntry.priority_score.desc(),
        QueueEntry.encounter_id.asc(),
    )

    entries = query.limit(limit + 1).all()
    has_next = len(entries) > limit
    entries = entries[:limit]

    items = [_entry_to_dict(e) for e in entries]

    next_cursor = None
    if has_next and items:
        last = items[-1]
        next_cursor = encode_cursor(last["tier_rank"], last["priority_score"], last["encounter_id"])

    return {
        "items": items,
        "has_next": has_next,
        "next_cursor": next_cursor,
        "count": len(items),
        "total": total,
    }


# ---------------------------------------------------------------------------
# POST /queue/next — atomik (Q3)
# ---------------------------------------------------------------------------

def next_for_user(
    session: Session,
    user_id: str,
    queue_type: str = "REVIEW",
    ward_scope: Optional[List[str]] = None,
    cfg: QueueConfig = DEFAULT_CONFIG,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Atomically claim the top available queue entry."""
    _now = now or _now_dt()
    expires_at = (_now + timedelta(seconds=cfg.claim_ttl_seconds)).isoformat()

    usr = session.query(User).filter_by(id=user_id).first()
    if not usr:
        usr = User(
            id=user_id,
            username=user_id.lower(),
            full_name=f"Pengguna {user_id}",
            role="PHARMACIST",
            hashed_password="sim_demo_hash",
        )
        session.add(usr)
        session.flush()

    base_query = session.query(QueueEntry.encounter_id).filter(
        QueueEntry.queue_type == queue_type.upper(),
        QueueEntry.state == "OPEN",
        QueueEntry.claimed_by.is_(None),
    )
    if ward_scope:
        base_query = base_query.filter(QueueEntry.ward.in_(ward_scope))

    subquery = (
        base_query.order_by(
            QueueEntry.tier_rank.desc(),
            QueueEntry.priority_score.desc(),
            QueueEntry.encounter_id.asc(),
        )
        .limit(1)
        .subquery()
    )

    stmt = (
        sa.update(QueueEntry)
        .where(QueueEntry.encounter_id == subquery.c.encounter_id)
        .values(
            state="CLAIMED",
            claimed_by=user_id,
            claim_expires_at=expires_at,
            queue_version=QueueEntry.queue_version + 1,
            updated_at=_now.isoformat(),
        )
        .returning(*[c for c in QueueEntry.__table__.c])
    )
    result = session.execute(stmt).first()
    if result:
        entry = session.query(QueueEntry).filter_by(encounter_id=result.encounter_id).first()
        _append_event(
            session,
            entry.encounter_id,
            "claim",
            {
                "claimed_by": user_id,
                "expires_at": expires_at,
                "tier_rank": entry.tier_rank,
                "priority_score": entry.priority_score,
            },
        )
        session.flush()
        return _entry_to_dict(entry)
    return None


# ---------------------------------------------------------------------------
# POST /queue/{enc}/heartbeat — perpanjang lease
# ---------------------------------------------------------------------------

def heartbeat(
    session: Session,
    encounter_id: str,
    user_id: str,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> Dict[str, Any]:
    """Perpanjang lease 15 menit. Hanya owner klaim yang bisa."""
    entry = _get_entry_or_404(session, encounter_id)

    if entry.claimed_by != user_id:
        raise ValueError(f"Encounter {encounter_id} diklaim oleh pengguna lain.")

    now = _now_dt()
    new_expires = (now + timedelta(seconds=cfg.claim_ttl_seconds)).isoformat()
    entry.claim_expires_at = new_expires
    entry.queue_version = (entry.queue_version or 0) + 1
    entry.updated_at = now.isoformat()

    _append_event(session, encounter_id, "upsert", {
        "action": "heartbeat",
        "new_expires_at": new_expires,
    })
    session.flush()
    return {"encounter_id": encounter_id, "claim_expires_at": new_expires}


# ---------------------------------------------------------------------------
# POST /queue/{enc}/release — lepas klaim
# ---------------------------------------------------------------------------

def release_claim(
    session: Session,
    encounter_id: str,
    user_id: str,
    user_role: str = "PHARMACIST",
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> Dict[str, Any]:
    """Lepas klaim. Owner atau ADMIN/COORDINATOR dapat melepas."""
    entry = _get_entry_or_404(session, encounter_id)

    allowed_override_roles = {"ADMIN", "COORDINATOR"}
    if entry.claimed_by and entry.claimed_by != user_id:
        if user_role.upper() not in allowed_override_roles:
            raise PermissionError(
                "Hanya pemilik klaim atau ADMIN/COORDINATOR yang dapat melepas klaim."
            )

    now = _now_dt()
    entry.state = "OPEN"
    entry.claimed_by = None
    entry.claim_expires_at = None
    entry.queue_version = (entry.queue_version or 0) + 1
    entry.updated_at = now.isoformat()

    _append_event(session, encounter_id, "release", {"released_by": user_id})
    session.flush()
    return {"encounter_id": encounter_id, "state": "OPEN"}


# ---------------------------------------------------------------------------
# POST /queue/{enc}/admit — ingest encounter baru
# ---------------------------------------------------------------------------

def admit_encounter(
    session: Session,
    encounter_id: str,
    ward: str,
    admitted_at: str,
    ml_score: Optional[float] = None,
    has_rule_finding: bool = False,
    cfg: QueueConfig = DEFAULT_CONFIG,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Buat queue_entry baru untuk encounter yang baru masuk (Antrean A: BPMH).
    Idempoten: jika encounter_id sudah ada, kembalikan entry yang ada.
    """
    existing = session.query(QueueEntry).filter(
        QueueEntry.encounter_id == encounter_id
    ).first()
    if existing:
        return _entry_to_dict(existing)

    enc = session.query(Encounter).filter_by(id=encounter_id).first()
    if not enc:
        enc = Encounter(
            id=encounter_id,
            patient_id=f"PAT-{encounter_id[:8]}",
            patient_name=_synthetic_initials(encounter_id),
            ward=ward,
            admitted_at=admitted_at,
            workflow_status="MENUNGGU_BPMH",
            ml_score=ml_score,
        )
        session.add(enc)
        session.flush()

    _now = now or _now_dt()
    entry_dict, event_dict = _admit_transition(
        encounter_id=encounter_id,
        ward=ward,
        admitted_at=admitted_at,
        ml_score=ml_score,
        has_rule_finding=has_rule_finding,
        now=_now,
        cfg=cfg,
    )

    entry = QueueEntry(
        encounter_id    = entry_dict["encounter_id"],
        queue_type      = entry_dict["queue_type"],
        ward            = entry_dict["ward"],
        state           = entry_dict["state"],
        tier_rank       = entry_dict["tier_rank"],
        tier_source     = entry_dict["tier_source"],
        priority_score  = entry_dict["priority_score"],
        ml_percentile   = entry_dict.get("ml_percentile"),
        depth_level     = entry_dict["depth_level"],
        admitted_at     = entry_dict["admitted_at"],
        sla_due_at      = entry_dict.get("sla_due_at"),
        next_due_at     = entry_dict.get("next_due_at"),
        discharge_planned_at = entry_dict.get("discharge_planned_at"),
        claimed_by      = None,
        claim_expires_at = None,
        queue_version   = entry_dict["queue_version"],
        updated_at      = entry_dict["updated_at"],
    )
    session.add(entry)
    _append_event(session, encounter_id, event_dict["kind"],
                  json.loads(event_dict["payload_json"]))
    session.flush()
    return entry_dict


# ---------------------------------------------------------------------------
# POST /queue/{enc}/discharge — pasien pulang
# ---------------------------------------------------------------------------

def discharge_encounter(
    session: Session,
    encounter_id: str,
    workflow_status: str,
    reason: str = "DISCHARGE_BEFORE_REVIEW",
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Tutup entri saat pasien pulang.
    Q7: Catat missed_reconciliation jika belum SELESAI.
    """
    entry = session.query(QueueEntry).filter(
        QueueEntry.encounter_id == encounter_id
    ).first()

    if not entry:
        # Encounter tidak ada di antrean — mungkin tidak pernah di-admit atau sudah CLOSED
        return {"encounter_id": encounter_id, "state": "not_found"}

    _now = now or _now_dt()
    existing = _entry_to_dict(entry)
    updated, event_dict, missed = _discharge_transition(
        existing_entry=existing,
        workflow_status=workflow_status,
        reason=reason,
        now=_now,
    )

    entry.state = "CLOSED"
    entry.claimed_by = None
    entry.claim_expires_at = None
    entry.queue_version = (entry.queue_version or 0) + 1
    entry.updated_at = _now.isoformat()

    _append_event(session, encounter_id, event_dict["kind"],
                  json.loads(event_dict["payload_json"]))

    # Q7: catat missed_reconciliation
    if missed:
        existing_missed = session.query(MissedReconciliation).filter(
            MissedReconciliation.encounter_id == encounter_id
        ).first()
        if not existing_missed:
            mr = MissedReconciliation(
                encounter_id  = missed["encounter_id"],
                discharged_at = missed["discharged_at"],
                last_state    = missed["last_state"],
                last_tier     = missed["last_tier"],
                reason        = missed["reason"],
            )
            session.add(mr)

    session.flush()
    return {"encounter_id": encounter_id, "state": "CLOSED", "missed_reconciliation": missed is not None}


# ---------------------------------------------------------------------------
# POST /queue/{enc}/lab_critical — hasil lab kritis (Q-010)
# ---------------------------------------------------------------------------

_lab_critical_dedup: Dict[Tuple[str, str], float] = {}

def lab_critical_event(
    session: Session,
    encounter_id: str,
    lab_type: str,
    lab_value: Optional[str] = None,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> Dict[str, Any]:
    """
    Penanganan event LAB_CRITICAL (Q-010).
    Dedup 1 jam per (encounter_id, lab_type).
    Lantai aturan RULE diterapkan: tier_rank = 2 (HIGH), tier_source = "RULE".
    """
    global _lab_critical_dedup
    now_ts = time.time()
    dedup_key = (encounter_id, lab_type)
    if dedup_key in _lab_critical_dedup and (now_ts - _lab_critical_dedup[dedup_key]) < 3600:
        entry = session.query(QueueEntry).filter_by(encounter_id=encounter_id).first()
        return _entry_to_dict(entry) if entry else {"encounter_id": encounter_id, "status": "deduped"}

    _lab_critical_dedup[dedup_key] = now_ts

    entry = session.query(QueueEntry).filter_by(encounter_id=encounter_id).first()
    if not entry:
        return {"encounter_id": encounter_id, "status": "not_in_queue"}

    from priomedrec_core.queue_transitions import lab_critical as _lab_crit_trans
    entry_dict = _entry_to_dict(entry)
    updated, event_dict = _lab_crit_trans(
        entry_dict, lab_type=lab_type, lab_value=lab_value, now=_now_dt(), cfg=cfg
    )

    entry.tier_rank = updated["tier_rank"]
    entry.tier_source = updated["tier_source"]
    entry.priority_score = updated["priority_score"]
    entry.next_due_at = updated["next_due_at"]
    entry.queue_version = updated["queue_version"]
    entry.updated_at = updated["updated_at"]

    _append_event(session, encounter_id, event_dict["kind"],
                  json.loads(event_dict["payload_json"]))
    session.flush()
    return updated


# ---------------------------------------------------------------------------
# POST /queue/{enc}/order_change — perubahan order dokter (Q-010)
# ---------------------------------------------------------------------------

_order_change_debounce: Dict[str, float] = {}

def order_change_event(
    session: Session,
    encounter_id: str,
    order_details: Optional[Dict[str, Any]] = None,
    has_rule_finding: bool = False,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> Dict[str, Any]:
    """
    Penanganan event ORDER_CHANGE (Q-010).
    Debounce 30 detik per encounter.
    """
    global _order_change_debounce
    now_ts = time.time()
    if encounter_id in _order_change_debounce and (now_ts - _order_change_debounce[encounter_id]) < 30:
        entry = session.query(QueueEntry).filter_by(encounter_id=encounter_id).first()
        return _entry_to_dict(entry) if entry else {"encounter_id": encounter_id, "status": "debounced"}

    _order_change_debounce[encounter_id] = now_ts

    entry = session.query(QueueEntry).filter_by(encounter_id=encounter_id).first()
    if not entry:
        return {"encounter_id": encounter_id, "status": "not_in_queue"}

    from priomedrec_core.queue_transitions import order_change as _order_change_trans
    entry_dict = _entry_to_dict(entry)
    updated, event_dict = _order_change_trans(
        entry_dict, order_details=order_details, has_rule_finding=has_rule_finding, now=_now_dt(), cfg=cfg
    )

    entry.tier_rank = updated["tier_rank"]
    entry.tier_source = updated["tier_source"]
    entry.priority_score = updated["priority_score"]
    entry.next_due_at = updated["next_due_at"]
    entry.queue_version = updated["queue_version"]
    entry.updated_at = updated["updated_at"]

    _append_event(session, encounter_id, event_dict["kind"],
                  json.loads(event_dict["payload_json"]))
    session.flush()
    return updated


# ---------------------------------------------------------------------------
# GET /queue/metrics — agregasi (cache 10 dtk)
# ---------------------------------------------------------------------------

def get_metrics(session: Session) -> Dict[str, Any]:
    """
    Hitung metrik antrean.
    Cache 10 detik untuk menghindari query berat per request.
    """
    global _metrics_cache
    now_ts = time.time()
    if _metrics_cache.get("_ts", 0) + _METRICS_TTL > now_ts:
        return _metrics_cache.get("data", {})

    now = _now_dt()
    tier_map = {2: "HIGH", 1: "MEDIUM", 0: "LOW"}

    # --- Backlog per queue_type × tier ---
    backlog_rows = session.execute(sa.text("""
        SELECT queue_type, tier_rank, COUNT(*) as cnt
        FROM queue_entries
        WHERE state IN ('OPEN', 'CLAIMED', 'PARKED_DPJP')
        GROUP BY queue_type, tier_rank
    """)).fetchall()

    backlog: Dict[str, Dict[str, int]] = {"BPMH": {}, "REVIEW": {}}
    for qt, tr, cnt in backlog_rows:
        tier_str = tier_map.get(tr, "LOW")
        backlog.setdefault(qt, {})[tier_str] = cnt

    # --- WIP (CLAIMED) ---
    wip_total = session.query(QueueEntry).filter(QueueEntry.state == "CLAIMED").count()

    # --- Usia menunggu per tier (p50/p90/p99) ---
    open_entries = session.execute(sa.text("""
        SELECT tier_rank, admitted_at
        FROM queue_entries
        WHERE state IN ('OPEN', 'CLAIMED')
        AND admitted_at IS NOT NULL
    """)).fetchall()

    age_by_tier: Dict[str, List[float]] = {"HIGH": [], "MEDIUM": [], "LOW": []}
    for tr, admitted_at in open_entries:
        tier_str = tier_map.get(tr, "LOW")
        try:
            dt = datetime.fromisoformat(admitted_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            hours = (now - dt).total_seconds() / 3600.0
            age_by_tier[tier_str].append(hours)
        except Exception:
            pass

    age_distribution: Dict[str, Dict[str, Optional[float]]] = {}
    for tier_str, ages in age_by_tier.items():
        if not ages:
            age_distribution[tier_str] = {"p50_hours": None, "p90_hours": None, "p99_hours": None}
        else:
            ages_sorted = sorted(ages)
            n = len(ages_sorted)
            age_distribution[tier_str] = {
                "p50_hours": round(ages_sorted[int(n * 0.50)], 2),
                "p90_hours": round(ages_sorted[min(int(n * 0.90), n - 1)], 2),
                "p99_hours": round(ages_sorted[min(int(n * 0.99), n - 1)], 2),
            }

    # --- SLA compliance HIGH ---
    high_cfg = DEFAULT_CONFIG.sla.get("HIGH")
    target_h = high_cfg.target_hours if high_cfg else 4.0

    high_total = len(age_by_tier["HIGH"])
    high_within_sla = sum(1 for h in age_by_tier["HIGH"] if h <= target_h)
    sla_high_pct = round(100.0 * high_within_sla / max(high_total, 1), 1)

    # --- Missed reconciliations ---
    today = now.strftime("%Y-%m-%d")
    missed_today = session.execute(sa.text(
        "SELECT COUNT(*) FROM missed_reconciliations WHERE discharged_at LIKE :today"
    ), {"today": f"{today}%"}).scalar() or 0
    missed_total = session.query(MissedReconciliation).count()

    # --- Expired claims ---
    now_iso = now.isoformat()
    expired_claims = session.execute(sa.text("""
        SELECT COUNT(*) FROM queue_entries
        WHERE state = 'CLAIMED'
        AND claim_expires_at IS NOT NULL
        AND claim_expires_at < :now
    """), {"now": now_iso}).scalar() or 0

    # --- Tier source ratio ---
    source_rows = session.execute(sa.text("""
        SELECT tier_source, COUNT(*) FROM queue_entries
        WHERE state IN ('OPEN', 'CLAIMED')
        GROUP BY tier_source
    """)).fetchall()
    source_total = sum(cnt for _, cnt in source_rows) or 1
    tier_source_ratio = {src: round(cnt / source_total, 3) for src, cnt in source_rows}

    # --- Queue version max ---
    max_version = session.execute(
        sa.text("SELECT COALESCE(MAX(queue_version), 0) FROM queue_entries")
    ).scalar() or 0

    result = {
        "backlog":           backlog,
        "wip":               {"total": wip_total},
        "age_distribution":  age_distribution,
        "sla_compliance":    {"HIGH_pct": sla_high_pct},
        "missed_reconciliations": {"today": missed_today, "total": missed_total},
        "expired_claims":    expired_claims,
        "tier_source_ratio": tier_source_ratio,
        "queue_version":     max_version,
        "cached_at":         now_iso,
    }

    _metrics_cache = {"_ts": now_ts, "data": result}
    return result


# ---------------------------------------------------------------------------
# Helpers interal
# ---------------------------------------------------------------------------

def _entry_to_dict(entry: QueueEntry) -> Dict[str, Any]:
    return {
        "encounter_id":        entry.encounter_id,
        "queue_type":          entry.queue_type,
        "ward":                entry.ward,
        "state":               entry.state,
        "tier_rank":           entry.tier_rank,
        "tier_source":         entry.tier_source,
        "priority_score":      entry.priority_score,
        "ml_percentile":       entry.ml_percentile,
        "depth_level":         entry.depth_level,
        "admitted_at":         entry.admitted_at,
        "sla_due_at":          entry.sla_due_at,
        "next_due_at":         entry.next_due_at,
        "discharge_planned_at": entry.discharge_planned_at,
        "claimed_by":          entry.claimed_by,
        "claim_expires_at":    entry.claim_expires_at,
        "queue_version":       entry.queue_version,
        "updated_at":          entry.updated_at,
    }


def _get_entry_or_404(session: Session, encounter_id: str) -> QueueEntry:
    entry = session.query(QueueEntry).filter(
        QueueEntry.encounter_id == encounter_id
    ).first()
    if not entry:
        raise KeyError(f"Queue entry {encounter_id} tidak ditemukan.")
    return entry


def _append_event(
    session: Session,
    encounter_id: str,
    kind: str,
    payload: Dict[str, Any],
) -> None:
    """Tambahkan queue_event row (dipakai untuk diff SSE + audit operasional)."""
    max_seq = session.query(sa.func.coalesce(sa.func.max(QueueEvent.seq), 0)).scalar() or 0
    event = QueueEvent(
        seq          = max_seq + 1,
        encounter_id = encounter_id,
        kind         = kind,
        payload_json = json.dumps(payload, ensure_ascii=False),
        at           = _now_utc(),
    )
    session.add(event)
    # Flush agar pemanggilan berikutnya dalam transaksi yang sama tidak
    # menghitung ulang max(seq) dari baris yang belum ter-flush (autoflush=False).
    session.flush()
