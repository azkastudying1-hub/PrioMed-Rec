"""
api/services/queue_view_service.py
-----------------------------------
Lapisan "tampilan" untuk menu Antrean Farmasi & Command Center.

Memisahkan logika UI dari `queue_service` (yang sudah diuji dan tidak diubah):

  enrich_entries()     — tambahkan data pasien, SLA, alasan prioritas ("mengapa dia?")
  get_my_queue()       — entri yang sedang diklaim pengguna
  get_command_center() — metrik koordinator: kapasitas, panas bangsal, aging, risiko SLA
  advance_encounter()  — sinkronkan workflow_status encounter dengan antrean
  sync_after_review()  — tutup/parkir entri antrean setelah apoteker memutuskan

Prinsip (QUEUE_PLAN):
  - Tidak ada panggilan LLM/Langflow (ADR-20).
  - Mode lonjakan HANYA memberi rekomendasi; tidak pernah menurunkan tier
    atau menyembunyikan pasien (§3.5).
  - Angka kapasitas = asumsi yang dapat dikonfigurasi, bukan data RS nyata (§8.1).
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Session

from api.db.models import Encounter, QueueEntry, StatusHistory, User
from api.services.queue_service import (
    OPEN_STATES,
    _append_event,
    _entry_to_dict,
    get_metrics,
)
from priomedrec_core.queue_config import DEFAULT_CONFIG

TIER_BY_RANK = {2: "HIGH", 1: "MEDIUM", 0: "LOW"}
TIERS = ("HIGH", "MEDIUM", "LOW")

# Aging bucket (% terhadap target SLA) — §7 "Aging strip"
AGING_BUCKETS = ("<25%", "25-50%", "50-75%", "75-100%", ">100%")

# Asumsi kapasitas (QUEUE_PLAN §8.1) — dapat diubah via env / query param
DEFAULT_PHARMACISTS_ON_DUTY = int(os.getenv("QUEUE_PHARMACISTS_ON_DUTY", "3"))
DEFAULT_SHIFT_MINUTES = int(os.getenv("QUEUE_SHIFT_MINUTES", "420"))        # 7 jam
DEFAULT_PRODUCTIVE_PCT = float(os.getenv("QUEUE_PRODUCTIVE_PCT", "0.60"))   # 60%
SURGE_LOAD_RATIO = float(os.getenv("QUEUE_SURGE_LOAD_RATIO", "1.3"))
SURGE_BACKLOG_N = int(os.getenv("QUEUE_SURGE_BACKLOG", "200"))

ASSUMPTION_NOTE = (
    "Angka kapasitas & menit telaah adalah asumsi awal yang dapat dikonfigurasi, "
    "belum dikalibrasi dengan data RS mitra."
)


# ---------------------------------------------------------------------------
# Util
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _hours_since(ts: Optional[str], now: datetime) -> Optional[float]:
    dt = _parse(ts)
    if dt is None:
        return None
    return max((now - dt).total_seconds() / 3600.0, 0.0)


def _sla_target(tier: str) -> float:
    cfg = DEFAULT_CONFIG.sla.get(tier)
    return float(cfg.target_hours) if cfg else 12.0


def _why(entry: Dict[str, Any], hours: Optional[float], tier: str) -> List[str]:
    """Alasan prioritas yang dapat dibaca manusia — jawaban atas 'mengapa dia?'."""
    reasons: List[str] = []
    src = entry.get("tier_source")
    if src == "RULE":
        reasons.append(
            "Temuan aturan klinis (high-alert / alergi / Tier-1) — lantai HIGH, tidak dapat diturunkan."
        )
    elif src == "SLA":
        reasons.append("Dinaikkan otomatis karena waktu tunggu mendekati/melewati batas SLA.")
    else:
        pct = entry.get("ml_percentile")
        if pct is not None:
            reasons.append(f"Skor risiko ML berada di persentil {round(float(pct) * 100)} pada bangsalnya.")
        else:
            reasons.append("Prioritas dari model ML (urutan relatif, bukan diagnosis).")
    if hours is not None:
        target = _sla_target(tier)
        reasons.append(f"Menunggu {hours:.1f} jam dari target SLA {target:g} jam ({hours / target * 100:.0f}%).")
    if entry.get("discharge_planned_at"):
        reasons.append("Rencana pulang tercatat — dorongan agar rekonsiliasi selesai sebelum pasien pulang.")
    reasons.append(f"Skor prioritas komposit {float(entry.get('priority_score') or 0):.1f}/100.")
    return reasons


def _synth_reasons(entry: Dict[str, Any], tier: str, ml_score: Optional[float]) -> List[Dict[str, str]]:
    """Alasan prioritas bila encounter belum punya `priority_reason` (mis. data simulasi)."""
    src = entry.get("tier_source")
    if src == "RULE":
        return [{"source": "rules", "tier": "HIGH",
                 "reason": "Temuan aturan klinis: obat high-alert / konflik alergi (perlu konfirmasi apoteker)"}]
    if src == "SLA":
        return [{"source": "sla", "tier": tier, "reason": "Dinaikkan karena batas waktu tunggu SLA"}]
    text = "Prioritas dari model ML"
    if ml_score is not None:
        text += f" (skor {float(ml_score):.2f}) — wajib diverifikasi apoteker"
    return [{"source": "ml", "tier": tier, "reason": text}]


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------

def enrich_entries(session: Session, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tambahkan data pasien/SLA ke daftar entri antrean (1 query encounter + 1 query user)."""
    if not items:
        return items
    now = _now()
    enc_ids = [i["encounter_id"] for i in items]
    encs = {
        e.id: e for e in session.query(Encounter).filter(Encounter.id.in_(enc_ids)).all()
    }
    claimer_ids = {i["claimed_by"] for i in items if i.get("claimed_by")}
    users = {}
    if claimer_ids:
        users = {
            u.id: u for u in session.query(User).filter(User.id.in_(claimer_ids)).all()
        }

    for it in items:
        enc = encs.get(it["encounter_id"])
        tier = TIER_BY_RANK.get(it.get("tier_rank", 1), "MEDIUM")
        hours = _hours_since(it.get("admitted_at"), now)
        target = _sla_target(tier)

        reasons: List[Dict[str, Any]] = []
        if enc and enc.priority_reason:
            try:
                reasons = json.loads(enc.priority_reason) or []
            except Exception:
                reasons = []
        if not reasons:
            reasons = _synth_reasons(it, tier, enc.ml_score if enc else None)

        lease_left: Optional[int] = None
        expires = _parse(it.get("claim_expires_at"))
        if expires:
            lease_left = int((expires - now).total_seconds())

        claimer = users.get(it.get("claimed_by")) if it.get("claimed_by") else None

        it.update({
            "tier": tier,
            "patient_id": enc.patient_id if enc else None,
            "patient_name": enc.patient_name if enc else None,
            "dpjp_name": enc.dpjp_name if enc else None,
            "ml_score": enc.ml_score if enc else None,
            "workflow_status": enc.workflow_status if enc else None,
            "row_version": (enc.row_version or 0) if enc else 0,
            "priority_reasons": reasons,
            "hours_waiting": round(hours, 2) if hours is not None else None,
            "sla_target_hours": target,
            "sla_ratio": round(hours / target, 3) if hours is not None and target else None,
            "claimed_by_name": claimer.full_name if claimer else None,
            "lease_seconds_left": lease_left,
            "why": _why(it, hours, tier),
        })
    return items


def enrich_one(session: Session, entry: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if entry is None:
        return None
    return enrich_entries(session, [entry])[0]


# ---------------------------------------------------------------------------
# Antrean saya
# ---------------------------------------------------------------------------

def get_my_queue(session: Session, user_id: str, next_n: int = 5) -> Dict[str, Any]:
    """
    'Antrean Saya' (§7): yang sedang saya tangani + N berikutnya (pratinjau, belum diklaim).
    Pratinjau berurutan sama dengan 'Ambil berikutnya' agar apoteker tahu apa yang akan datang.
    """
    mine = (
        session.query(QueueEntry)
        .filter(QueueEntry.claimed_by == user_id, QueueEntry.state == "CLAIMED")
        .order_by(QueueEntry.tier_rank.desc(), QueueEntry.priority_score.desc(),
                  QueueEntry.encounter_id.asc())
        .all()
    )
    upcoming = (
        session.query(QueueEntry)
        .filter(QueueEntry.queue_type == "REVIEW", QueueEntry.state == "OPEN",
                QueueEntry.claimed_by.is_(None))
        .order_by(QueueEntry.tier_rank.desc(), QueueEntry.priority_score.desc(),
                  QueueEntry.encounter_id.asc())
        .limit(next_n)
        .all()
    )
    return {
        "claimed": enrich_entries(session, [_entry_to_dict(e) for e in mine]),
        "upcoming": enrich_entries(session, [_entry_to_dict(e) for e in upcoming]),
    }


# ---------------------------------------------------------------------------
# Command Center
# ---------------------------------------------------------------------------

def _aging_bucket(ratio: float) -> int:
    if ratio < 0.25:
        return 0
    if ratio < 0.50:
        return 1
    if ratio < 0.75:
        return 2
    if ratio < 1.0:
        return 3
    return 4


def get_command_center(
    session: Session,
    pharmacists: Optional[int] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Data satu layar untuk koordinator (QUEUE_PLAN §7/§8):
    permintaan vs kapasitas, panas bangsal×tier, histogram aging, daftar berisiko SLA,
    snapshot aliran, indikator keselamatan, dan status mode lonjakan.
    """
    _n = now or _now()
    on_duty = max(int(pharmacists if pharmacists is not None else DEFAULT_PHARMACISTS_ON_DUTY), 1)

    base = get_metrics(session)  # cache 10 dtk — tidak diubah

    rows = (
        session.query(QueueEntry)
        .filter(QueueEntry.state.in_(list(OPEN_STATES)))
        .all()
    )

    # --- Panas bangsal × tier, aging, demand ---
    heat: Dict[str, Dict[str, int]] = {}
    aging: Dict[str, List[int]] = {t: [0] * len(AGING_BUCKETS) for t in TIERS}
    at_risk: List[Dict[str, Any]] = []
    review_mins = DEFAULT_CONFIG.review_minutes
    demand_review = 0.0
    pipeline_bpmh = 0.0
    counts = {"bpmh_open": 0, "review_open": 0, "claimed": 0, "parked": 0}
    high_ages: List[float] = []

    for e in rows:
        tier = TIER_BY_RANK.get(e.tier_rank, "MEDIUM")
        heat.setdefault((e.ward or "—").upper(), {t: 0 for t in TIERS})[tier] += 1
        hours = _hours_since(e.admitted_at, _n)
        target = _sla_target(tier)
        ratio = (hours / target) if hours is not None and target else 0.0
        aging[tier][_aging_bucket(ratio)] += 1

        if tier == "HIGH" and hours is not None:
            high_ages.append(hours)

        if e.state == "PARKED_DPJP":
            counts["parked"] += 1
        else:
            if e.state == "CLAIMED":
                counts["claimed"] += 1
            if e.queue_type == "REVIEW":
                counts["review_open"] += 1
                demand_review += review_mins.get(tier, 20.0)
            else:
                counts["bpmh_open"] += 1
                pipeline_bpmh += review_mins.get(tier, 20.0)

        if e.state in ("OPEN", "CLAIMED") and ratio >= 0.75:
            at_risk.append({
                "encounter_id": e.encounter_id, "ward": e.ward, "tier": tier,
                "tier_source": e.tier_source, "queue_type": e.queue_type, "state": e.state,
                "hours_waiting": round(hours or 0.0, 2), "sla_target_hours": target,
                "sla_ratio": round(ratio, 3), "claimed_by": e.claimed_by,
            })

    at_risk.sort(key=lambda r: (-r["sla_ratio"], r["encounter_id"]))
    at_risk_total = len(at_risk)
    at_risk_items = at_risk[:12]
    if at_risk_items:
        names = {
            e.id: e for e in session.query(Encounter)
            .filter(Encounter.id.in_([r["encounter_id"] for r in at_risk_items])).all()
        }
        for r in at_risk_items:
            enc = names.get(r["encounter_id"])
            r["patient_id"] = enc.patient_id if enc else None
            r["patient_name"] = enc.patient_name if enc else None

    # --- Kapasitas ---
    capacity_min = on_duty * DEFAULT_SHIFT_MINUTES * DEFAULT_PRODUCTIVE_PCT
    load_ratio = (demand_review / capacity_min) if capacity_min else 0.0
    extra_minutes = max(demand_review - capacity_min, 0.0)
    extra_pharmacist_hours = round(extra_minutes / 60.0 / DEFAULT_PRODUCTIVE_PCT, 1)

    # --- Mode lonjakan (hanya rekomendasi) ---
    high_cfg = DEFAULT_CONFIG.sla.get("HIGH")
    high_target = float(high_cfg.target_hours) if high_cfg else 4.0
    high_p90 = None
    if high_ages:
        s = sorted(high_ages)
        high_p90 = s[min(int(len(s) * 0.9), len(s) - 1)]
    total_backlog = len(rows)

    reasons: List[str] = []
    if load_ratio > SURGE_LOAD_RATIO:
        reasons.append(f"Beban {load_ratio:.1f}× kapasitas (ambang {SURGE_LOAD_RATIO:g}×)")
    if high_p90 is not None and high_p90 > 0.75 * high_target:
        reasons.append(
            f"p90 usia tunggu HIGH {high_p90:.1f} jam > 75% SLA ({0.75 * high_target:.1f} jam)"
        )
    if total_backlog > SURGE_BACKLOG_N:
        reasons.append(f"Backlog {total_backlog} entri melewati ambang {SURGE_BACKLOG_N}")
    surge_active = bool(reasons)

    recommendations: List[str] = []
    if surge_active:
        if extra_pharmacist_hours > 0:
            recommendations.append(
                f"Tambah ±{extra_pharmacist_hours:g} jam apoteker (floating) untuk menutup selisih beban."
            )
        recommendations.append("Aktifkan overflow lintas-bangsal untuk kasus HIGH yang mendekati SLA.")
        recommendations.append(
            "Pertimbangkan telaah ringan Level 1 untuk LOW tanpa temuan — hanya bila telah disetujui komite farmasi (default OFF)."
        )
        recommendations.append("Eskalasi ke kepala instalasi bila p90 HIGH terus melewati 75% SLA.")

    # --- Aliran (snapshot) ---
    closed_total = session.query(QueueEntry).filter(QueueEntry.state == "CLOSED").count()
    since = (_n - timedelta(hours=24)).isoformat()
    ev_rows = session.execute(
        sa.text("SELECT kind, COUNT(*) FROM queue_events WHERE at >= :s GROUP BY kind"),
        {"s": since},
    ).fetchall()
    events_24h = {k: int(c) for k, c in ev_rows}

    return {
        "as_of": _n.isoformat(),
        "queue_version": base.get("queue_version", 0),
        "simulated_label": "Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS",
        "totals": {
            "open_total": total_backlog,
            "review_open": counts["review_open"],
            "bpmh_open": counts["bpmh_open"],
            "claimed": counts["claimed"],
            "parked_dpjp": counts["parked"],
            "high_open": sum(heat_row["HIGH"] for heat_row in heat.values()),
        },
        "heatmap": {"wards": sorted(heat.keys()), "tiers": list(TIERS), "cells": heat},
        "aging": {"buckets": list(AGING_BUCKETS), "by_tier": aging},
        "at_risk": {"total": at_risk_total, "items": at_risk_items},
        "capacity": {
            "pharmacists_on_duty": on_duty,
            "shift_minutes": DEFAULT_SHIFT_MINUTES,
            "productive_pct": DEFAULT_PRODUCTIVE_PCT,
            "capacity_minutes": round(capacity_min, 1),
            "demand_minutes": round(demand_review, 1),
            "pipeline_minutes": round(pipeline_bpmh, 1),
            "load_ratio": round(load_ratio, 2),
            "extra_pharmacist_hours": extra_pharmacist_hours,
            "review_minutes": dict(review_mins),
            "assumption_note": ASSUMPTION_NOTE,
        },
        "surge": {
            "active": surge_active,
            "reasons": reasons,
            "recommendations": recommendations,
            "thresholds": {"load_ratio": SURGE_LOAD_RATIO, "backlog": SURGE_BACKLOG_N,
                           "high_p90_pct_of_sla": 0.75},
            "note": "Mode lonjakan hanya memberi rekomendasi — tidak menurunkan tier maupun menyembunyikan pasien.",
        },
        "flow": {
            "bpmh_open": counts["bpmh_open"],
            "review_open": counts["review_open"] - counts["claimed"],
            "claimed": counts["claimed"],
            "parked_dpjp": counts["parked"],
            "closed_total": closed_total,
            "events_24h": events_24h,
        },
        "safety": {
            "sla_high_pct": base.get("sla_compliance", {}).get("HIGH_pct"),
            "age_distribution": base.get("age_distribution", {}),
            "missed_reconciliations": base.get("missed_reconciliations", {}),
            "expired_claims": base.get("expired_claims", 0),
            "tier_source_ratio": base.get("tier_source_ratio", {}),
        },
    }


# ---------------------------------------------------------------------------
# Sinkron status encounter ↔ antrean
# ---------------------------------------------------------------------------

_FORWARD_PATH = ["MENUNGGU_BPMH", "BPMH_LENGKAP", "DALAM_ANALISIS", "MENUNGGU_TELAAH", "DRAFT_REVIEW"]


def advance_encounter(
    session: Session,
    encounter_id: str,
    target: str,
    actor_id: Optional[str] = None,
    actor_type: str = "system",
    claimed_by: Optional[str] = None,
) -> Optional[str]:
    """
    Majukan `Encounter.workflow_status` sepanjang jalur sah state machine (B-104) sampai `target`.
    Tidak pernah mundur atau melompati status terminal. Setiap langkah dicatat di status_history.
    """
    enc = session.query(Encounter).filter(Encounter.id == encounter_id).first()
    if not enc:
        return None
    if enc.workflow_status == "ESKALASI" and target == "DRAFT_REVIEW":
        enc.workflow_status = "DRAFT_REVIEW"       # jalur sah: ESKALASI → DRAFT_REVIEW
        enc.row_version = (enc.row_version or 0) + 1
        enc.updated_at = _now().isoformat()
        session.add(StatusHistory(
            id=str(uuid.uuid4()), encounter_id=enc.id, from_status="ESKALASI",
            to_status="DRAFT_REVIEW", changed_by=actor_id if actor_type == "human" else None,
            changed_by_type=actor_type, reason="DPJP merespons — telaah dilanjutkan",
            changed_at=enc.updated_at,
        ))
        if claimed_by:
            enc.claimed_by, enc.claimed_at = claimed_by, enc.updated_at
        return enc.workflow_status
    if enc.workflow_status not in _FORWARD_PATH or target not in _FORWARD_PATH:
        return enc.workflow_status
    cur = _FORWARD_PATH.index(enc.workflow_status)
    end = _FORWARD_PATH.index(target)
    now = _now().isoformat()
    for nxt in _FORWARD_PATH[cur + 1: end + 1]:
        session.add(StatusHistory(
            id=str(uuid.uuid4()), encounter_id=enc.id,
            from_status=enc.workflow_status, to_status=nxt,
            changed_by=actor_id if actor_type == "human" else None,
            changed_by_type=actor_type, reason="sinkron antrean", changed_at=now,
        ))
        enc.workflow_status = nxt
        enc.row_version = (enc.row_version or 0) + 1
    if claimed_by:
        enc.claimed_by = claimed_by
        enc.claimed_at = now
    enc.updated_at = now
    session.flush()
    return enc.workflow_status


def sync_after_review(session: Session, encounter_id: str, action: str) -> Optional[str]:
    """
    Setelah aksi telaah: APPROVE/EDIT/REJECT → CLOSED (selesai, bukan missed rec);
    ESCALATE → PARKED_DPJP (menunggu DPJP, tidak menghukum SLA apoteker);
    DRAFT_REVIEW → tetap diklaim.
    """
    entry = session.query(QueueEntry).filter(QueueEntry.encounter_id == encounter_id).first()
    if not entry:
        return None
    action = action.upper()
    now = _now().isoformat()
    if action in ("APPROVE", "EDIT", "REJECT"):
        entry.state = "CLOSED"
        kind = "remove"
    elif action == "ESCALATE":
        entry.state = "PARKED_DPJP"
        kind = "upsert"
    else:
        return entry.state
    entry.claimed_by = None
    entry.claim_expires_at = None
    entry.queue_version = (entry.queue_version or 0) + 1
    entry.updated_at = now
    _append_event(session, encounter_id, kind, {
        "reason": f"review_{action.lower()}", "ward": entry.ward,
        "queue_type": entry.queue_type, "state": entry.state,
    })
    return entry.state


def release_encounter_claim(session: Session, encounter_id: str) -> None:
    """Samakan klaim legacy `Encounter.claimed_by` saat klaim antrean dilepas."""
    enc = session.query(Encounter).filter(Encounter.id == encounter_id).first()
    if enc and enc.claimed_by:
        enc.claimed_by = None
        enc.claimed_at = None
        enc.row_version = (enc.row_version or 0) + 1
