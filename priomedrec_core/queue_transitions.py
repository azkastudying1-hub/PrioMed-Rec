"""
priomedrec_core/queue_transitions.py
---------------------------------------
Logika transisi antrean — deterministik, tanpa LLM/Langflow (ADR-20, Q5).

Transisi yang didukung:
  admit()      — encounter baru masuk → Antrean A (BPMH)
  bpmh_submit()— BPMH selesai → pindah A→B (Telaah); hitung ulang skor
  discharge()  — pasien pulang → tutup entri; catat missed_reconciliation jika belum SELESAI
  cancel()     — batal admisi → tutup entri
  transfer()   — pindah bangsal → re-triage; lepas klaim jika beda bangsal
  park_dpjp()  — menunggu DPJP → state=PARKED_DPJP (timer sendiri)
  unpark_dpjp()— DPJP merespons → kembali ke OPEN
  expire_claim() — lease habis → kembali ke OPEN dengan usia menunggu tetap

Jaminan (Q1, ADR-21):
  - Semua fungsi TIDAK memanggil LLM/Langflow.
  - RULE floor tidak turun saat re-triage (compute_tier_source dipanggil ulang).
  - Setiap transisi menghasilkan QueueEvent row (idempoten via event_id).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from .queue_config import QueueConfig, DEFAULT_CONFIG
from .queue_engine import (
    compute_queue_score,
    compute_tier_source,
    compute_tier_from_ml_score,
    compute_ml_percentiles,
    determine_next_due_at,
    TIER_RANK,
    TIER_FROM_RANK,
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Helpers internal
# ---------------------------------------------------------------------------

def _make_queue_event(encounter_id: str, kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Buat dict queue_event (belum disimpan ke DB)."""
    return {
        "encounter_id": encounter_id,
        "kind":         kind,
        "payload_json": json.dumps(payload, ensure_ascii=False),
        "at":           _now_utc(),
    }


def _compute_sla_due_at(
    admitted_at: str,
    tier_str: str,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> Optional[str]:
    sla_cfg = cfg.sla.get(tier_str)
    if not sla_cfg:
        return None
    try:
        dt = datetime.fromisoformat(admitted_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (dt + timedelta(hours=sla_cfg.target_hours)).isoformat()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# ADMIT — encounter baru masuk Antrean A
# ---------------------------------------------------------------------------

def admit(
    encounter_id: str,
    ward: str,
    admitted_at: str,
    ml_score: Optional[float] = None,
    has_rule_finding: bool = False,
    discrepancy_counts: Optional[Dict[str, int]] = None,
    now: Optional[datetime] = None,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Buat entri Antrean A (BPMH) untuk encounter baru.

    Returns (queue_entry_dict, queue_event_dict).
    Idempoten: caller harus memakai INSERT OR IGNORE pada encounter_id.
    """
    _now = now or datetime.now(timezone.utc)

    # Tier dari ML score
    ml_tier = compute_tier_from_ml_score(ml_score) if ml_score is not None else "MEDIUM"
    tier_str, tier_source = compute_tier_source(
        has_rule_finding=has_rule_finding,
        sla_escalated=False,
        ml_tier=ml_tier,
    )
    tier_rank = TIER_RANK[tier_str]

    # Skor awal (hanya Fase A — ml_percentile belum diketahui → 0.5)
    entry_dict: Dict[str, Any] = {
        "encounter_id":         encounter_id,
        "queue_type":           "BPMH",
        "ward":                 ward,
        "state":                "OPEN",
        "tier_rank":            tier_rank,
        "tier_source":          tier_source,
        "ml_score":             ml_score,
        "admitted_at":          admitted_at,
        "discrepancy_counts":   discrepancy_counts or {},
        "discharge_planned_at": None,
        "claimed_by":           None,
        "claim_expires_at":     None,
        "queue_version":        1,
        "updated_at":           _now.isoformat(),
        "depth_level":          2,
    }
    entry_dict["priority_score"] = compute_queue_score(entry_dict, _now, 0.5, cfg)
    entry_dict["sla_due_at"]     = _compute_sla_due_at(admitted_at, tier_str, cfg)
    entry_dict["next_due_at"]    = determine_next_due_at(entry_dict, _now, cfg)

    event = _make_queue_event(encounter_id, "upsert", {
        "action": "admit",
        "queue_type": "BPMH",
        "tier_rank": tier_rank,
        "tier_source": tier_source,
    })
    return entry_dict, event


# ---------------------------------------------------------------------------
# BPMH_SUBMIT — pindah Antrean A → B
# ---------------------------------------------------------------------------

def bpmh_submit(
    existing_entry: Dict[str, Any],
    has_rule_finding: bool = False,
    is_high_alert: bool = False,
    discrepancy_counts: Optional[Dict[str, int]] = None,
    ml_score: Optional[float] = None,
    now: Optional[datetime] = None,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Pindahkan entri dari Antrean A (BPMH) ke Antrean B (REVIEW).
    Hitung ulang tier dan skor berdasarkan temuan Fase B.

    ADR-21: jika ada temuan RULE (high-alert, tier-1, alergi), tier minimal HIGH.
    """
    _now = now or datetime.now(timezone.utc)
    enc_id = existing_entry["encounter_id"]

    ml_tier = compute_tier_from_ml_score(ml_score) if ml_score is not None else \
              TIER_FROM_RANK.get(existing_entry.get("tier_rank", 1), "MEDIUM")

    tier_str, tier_source = compute_tier_source(
        has_rule_finding=has_rule_finding or is_high_alert,
        sla_escalated=False,
        ml_tier=ml_tier,
    )
    tier_rank = TIER_RANK[tier_str]

    # Jaminan: tier_rank hanya boleh naik dari nilai sebelumnya (ADR-21)
    prev_rank = existing_entry.get("tier_rank", 0)
    tier_rank = max(tier_rank, prev_rank)
    if tier_rank == 2 and tier_source == "ML" and prev_rank == 2 and existing_entry.get("tier_source") == "RULE":
        tier_source = "RULE"  # pertahankan RULE jika sebelumnya RULE

    entry = dict(existing_entry)
    entry.update({
        "queue_type":         "REVIEW",
        "state":              "OPEN",
        "tier_rank":          tier_rank,
        "tier_source":        tier_source,
        "ml_score":           ml_score if ml_score is not None else existing_entry.get("ml_score"),
        "discrepancy_counts": discrepancy_counts or {},
        "queue_version":      existing_entry.get("queue_version", 0) + 1,
        "updated_at":         _now.isoformat(),
        "claimed_by":         None,
        "claim_expires_at":   None,
    })
    entry["priority_score"] = compute_queue_score(entry, _now, entry.get("ml_percentile") or 0.5, cfg)
    entry["sla_due_at"]     = _compute_sla_due_at(entry["admitted_at"], TIER_FROM_RANK[tier_rank], cfg)
    entry["next_due_at"]    = determine_next_due_at(entry, _now, cfg)

    event = _make_queue_event(enc_id, "upsert", {
        "action": "bpmh_submit",
        "queue_type": "REVIEW",
        "tier_rank": tier_rank,
        "tier_source": tier_source,
        "has_rule_finding": has_rule_finding,
    })
    return entry, event


# ---------------------------------------------------------------------------
# DISCHARGE — pasien pulang
# ---------------------------------------------------------------------------

TERMINAL_STATUSES = {"SELESAI_APPROVE", "SELESAI_EDIT"}


def discharge(
    existing_entry: Dict[str, Any],
    workflow_status: str,
    reason: str = "DISCHARGE_BEFORE_REVIEW",
    now: Optional[datetime] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Tutup entri saat pasien pulang.

    Q7: Jika belum SELESAI, buat missed_reconciliation dict.
    Returns (updated_entry, queue_event, missed_rec_or_None).
    """
    _now = now or datetime.now(timezone.utc)
    enc_id = existing_entry["encounter_id"]
    discharged_at = _now.isoformat()

    entry = dict(existing_entry)
    entry.update({
        "state":         "CLOSED",
        "queue_version": existing_entry.get("queue_version", 0) + 1,
        "updated_at":    discharged_at,
        "claimed_by":    None,
        "claim_expires_at": None,
    })

    event = _make_queue_event(enc_id, "remove", {"action": "discharge", "reason": reason})

    missed = None
    if workflow_status not in TERMINAL_STATUSES:
        missed = {
            "encounter_id": enc_id,
            "discharged_at": discharged_at,
            "last_state":    workflow_status,
            "last_tier":     TIER_FROM_RANK.get(existing_entry.get("tier_rank", 1), "MEDIUM"),
            "reason":        reason,
        }

    return entry, event, missed


# ---------------------------------------------------------------------------
# CANCEL — batal admisi
# ---------------------------------------------------------------------------

def cancel(
    existing_entry: Dict[str, Any],
    reason: str = "CANCEL_ADMISSION",
    now: Optional[datetime] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Tutup entri karena batal admisi atau duplikasi."""
    _now = now or datetime.now(timezone.utc)
    enc_id = existing_entry["encounter_id"]

    entry = dict(existing_entry)
    entry.update({
        "state":         "CLOSED",
        "queue_version": existing_entry.get("queue_version", 0) + 1,
        "updated_at":    _now.isoformat(),
        "claimed_by":    None,
        "claim_expires_at": None,
    })
    event = _make_queue_event(enc_id, "remove", {"action": "cancel", "reason": reason})
    return entry, event


# ---------------------------------------------------------------------------
# TRANSFER — pindah bangsal
# ---------------------------------------------------------------------------

def transfer(
    existing_entry: Dict[str, Any],
    new_ward: str,
    claiming_user_id: Optional[str] = None,
    has_rule_finding: bool = False,
    ml_score: Optional[float] = None,
    now: Optional[datetime] = None,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Pindahkan entri ke bangsal baru.
    Lepas klaim jika apoteker bertanggung jawab berbeda bangsal.
    Re-triage tier (ADR-21: lantai RULE tetap jika ada temuan klinis).
    """
    _now = now or datetime.now(timezone.utc)
    enc_id = existing_entry["encounter_id"]

    prev_ward = existing_entry.get("ward", "")
    ward_changed = (prev_ward != new_ward)

    ml_tier = compute_tier_from_ml_score(ml_score) if ml_score is not None else \
              TIER_FROM_RANK.get(existing_entry.get("tier_rank", 1), "MEDIUM")
    tier_str, tier_source = compute_tier_source(
        has_rule_finding=has_rule_finding,
        sla_escalated=False,
        ml_tier=ml_tier,
    )
    tier_rank = max(TIER_RANK[tier_str], existing_entry.get("tier_rank", 0))

    entry = dict(existing_entry)
    entry.update({
        "ward":          new_ward,
        "tier_rank":     tier_rank,
        "tier_source":   tier_source,
        "state":         "OPEN",                # lepas klaim saat transfer bangsal
        "claimed_by":    None,
        "claim_expires_at": None,
        "queue_version": existing_entry.get("queue_version", 0) + 1,
        "updated_at":    _now.isoformat(),
    })
    entry["priority_score"] = compute_queue_score(entry, _now, entry.get("ml_percentile") or 0.5, cfg)
    entry["next_due_at"]    = determine_next_due_at(entry, _now, cfg)

    event = _make_queue_event(enc_id, "upsert", {
        "action": "transfer",
        "from_ward": prev_ward,
        "to_ward": new_ward,
        "claim_released": ward_changed,
    })
    return entry, event


# ---------------------------------------------------------------------------
# PARK / UNPARK DPJP
# ---------------------------------------------------------------------------

def park_dpjp(
    existing_entry: Dict[str, Any],
    now: Optional[datetime] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Parkir entri saat menunggu DPJP (timer sendiri, tidak hukum SLA apoteker)."""
    _now = now or datetime.now(timezone.utc)
    entry = dict(existing_entry)
    entry.update({
        "state":         "PARKED_DPJP",
        "claimed_by":    None,
        "claim_expires_at": None,
        "queue_version": existing_entry.get("queue_version", 0) + 1,
        "updated_at":    _now.isoformat(),
    })
    event = _make_queue_event(existing_entry["encounter_id"], "upsert", {"action": "park_dpjp"})
    return entry, event


def unpark_dpjp(
    existing_entry: Dict[str, Any],
    now: Optional[datetime] = None,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Kembalikan entri PARKED_DPJP ke OPEN setelah DPJP merespons."""
    _now = now or datetime.now(timezone.utc)
    entry = dict(existing_entry)
    entry.update({
        "state":         "OPEN",
        "queue_version": existing_entry.get("queue_version", 0) + 1,
        "updated_at":    _now.isoformat(),
    })
    entry["next_due_at"] = determine_next_due_at(entry, _now, cfg)
    event = _make_queue_event(existing_entry["encounter_id"], "upsert", {"action": "unpark_dpjp"})
    return entry, event


# ---------------------------------------------------------------------------
# EXPIRE CLAIM — lease habis
# ---------------------------------------------------------------------------

def expire_claim(
    existing_entry: Dict[str, Any],
    now: Optional[datetime] = None,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Kembalikan entri ke OPEN saat lease kedaluwarsa.
    Usia menunggu dipertahankan (admitted_at tidak berubah).
    """
    _now = now or datetime.now(timezone.utc)
    entry = dict(existing_entry)
    entry.update({
        "state":          "OPEN",
        "claimed_by":     None,
        "claim_expires_at": None,
        "queue_version":  existing_entry.get("queue_version", 0) + 1,
        "updated_at":     _now.isoformat(),
    })
    # next_due_at diperbarui — usia menunggu tetap dari admitted_at asli
    entry["next_due_at"] = determine_next_due_at(entry, _now, cfg)

    event = _make_queue_event(existing_entry["encounter_id"], "expire", {
        "action": "claim_expired",
        "was_claimed_by": existing_entry.get("claimed_by"),
    })
    return entry, event


# ---------------------------------------------------------------------------
# LAB CRITICAL — eskalasi langsung hasil lab kritis (Q-010)
# ---------------------------------------------------------------------------

def lab_critical(
    existing_entry: Dict[str, Any],
    lab_type: str,
    lab_value: Optional[str] = None,
    now: Optional[datetime] = None,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Eskalasi prioritas saat nilai laboratorium kritis diterima (e.g. K > 6.0, INR > 5.0).
    Lantai aturan RULE diterapkan: tier_rank = 2 (HIGH), tier_source = "RULE".
    """
    _now = now or datetime.now(timezone.utc)
    enc_id = existing_entry["encounter_id"]
    entry = dict(existing_entry)

    entry.update({
        "tier_rank":     2,
        "tier_source":   "RULE",
        "queue_version": existing_entry.get("queue_version", 0) + 1,
        "updated_at":    _now.isoformat(),
    })
    entry["priority_score"] = max(float(existing_entry.get("priority_score", 0.0)), 85.0)
    entry["next_due_at"]    = determine_next_due_at(entry, _now, cfg)

    event = _make_queue_event(enc_id, "promote", {
        "action": "lab_critical",
        "lab_type": lab_type,
        "lab_value": lab_value,
        "new_tier": "HIGH",
        "tier_source": "RULE",
    })
    return entry, event


# ---------------------------------------------------------------------------
# ORDER CHANGE — re-evaluasi saat ada perubahan order obat (Q-010)
# ---------------------------------------------------------------------------

def order_change(
    existing_entry: Dict[str, Any],
    order_details: Optional[Dict[str, Any]] = None,
    has_rule_finding: bool = False,
    now: Optional[datetime] = None,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Pembaruan entri saat ada perubahan order obat dokter (debounce di service).
    Jika order memicu temuan aturan baru, tier_rank dinaikkan ke HIGH(RULE).
    """
    _now = now or datetime.now(timezone.utc)
    enc_id = existing_entry["encounter_id"]
    entry = dict(existing_entry)

    tier_rank = existing_entry.get("tier_rank", 1)
    tier_source = existing_entry.get("tier_source", "ML")
    if has_rule_finding:
        tier_rank = 2
        tier_source = "RULE"

    entry.update({
        "tier_rank":     tier_rank,
        "tier_source":   tier_source,
        "queue_version": existing_entry.get("queue_version", 0) + 1,
        "updated_at":    _now.isoformat(),
    })
    entry["priority_score"] = compute_queue_score(entry, _now, entry.get("ml_percentile") or 0.5, cfg)
    entry["next_due_at"]    = determine_next_due_at(entry, _now, cfg)

    event = _make_queue_event(enc_id, "upsert", {
        "action": "order_change",
        "order_details": order_details or {},
        "tier_rank": tier_rank,
        "tier_source": tier_source,
    })
    return entry, event

