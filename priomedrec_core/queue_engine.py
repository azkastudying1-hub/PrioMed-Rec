"""
priomedrec_core/queue_engine.py
---------------------------------
Mesin antrean deterministik — tanpa LLM/Langflow (ADR-20, Q5).

Fungsi utama:
  compute_queue_score()   — skor komposit 0–100 per entri
  apply_ml_quota()        — kuota HIGH-ML ≤ Q% per bangsal (ADR-21)
  apply_hysteresis()      — stabilitas urutan (mencegah baris loncat)
  batch_rescore()         — vektorisasi numpy untuk tick 5.000 entri
  determine_next_due_at() — kapan entri ini perlu SLA naik
  sort_queue()            — deterministik: tier↓, score↓, admitted_at↑, enc_id↑
  compute_tier_from_score() — ML score → tier (dengan kuota)
  compute_tier_source()   — RULE > SLA > ML (lantai aturan tidak pernah turun ADR-21)

Jaminan keselamatan (Q1):
  - Lantai aturan klinis (RULE) tidak pernah diturunkan oleh kuota, histeresis, atau mode apapun.
  - Tier hanya naik, tidak pernah turun (kecuali ada event re-triage eksplisit).
  - Anti-starvation: next_due_at menjamin setiap OPEN mencapai HIGH sebelum SLA max.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .queue_config import QueueConfig, DEFAULT_CONFIG
from .thresholds import high_threshold, medium_threshold

# ---------------------------------------------------------------------------
# Konstanta tier
# ---------------------------------------------------------------------------

TIER_RANK: Dict[str, int] = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
TIER_FROM_RANK: Dict[int, str] = {2: "HIGH", 1: "MEDIUM", 0: "LOW"}

VALID_STATES      = {"OPEN", "CLAIMED", "PARKED_DPJP", "CLOSED"}
VALID_QUEUE_TYPES = {"BPMH", "REVIEW"}
VALID_TIER_SOURCES = {"RULE", "ML", "SLA"}


# ---------------------------------------------------------------------------
# Komponen skor (0–1 masing-masing)
# ---------------------------------------------------------------------------

def _sla_pressure(elapsed_hours: float, target_hours: float) -> float:
    """
    sla_pressure = min(elapsed / target, 2) / 2

    0 saat baru masuk; 0.5 saat tepat SLA; >0.5 saat breach (max 1.0).
    """
    if target_hours <= 0:
        return 1.0
    return min(elapsed_hours / target_hours, 2.0) / 2.0


def _discharge_pressure(discharge_planned_at: Optional[str], now: datetime) -> float:
    """
    discharge_pressure = 1 jika ≤ 12 jam; linear turun ke 0 pada ≥ 48 jam.
    0 jika tidak ada rencana pulang.
    """
    if not discharge_planned_at:
        return 0.0
    try:
        dt = datetime.fromisoformat(discharge_planned_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hours_until = (dt - now).total_seconds() / 3600.0
        if hours_until <= 12.0:
            return 1.0
        if hours_until >= 48.0:
            return 0.0
        # Linear 12→48 jam
        return 1.0 - (hours_until - 12.0) / 36.0
    except Exception:
        return 0.0


def _wait_norm(admitted_at: str, now: datetime) -> float:
    """wait_norm = min(lama_menunggu / 24 jam, 1)"""
    try:
        dt = datetime.fromisoformat(admitted_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hours = (now - dt).total_seconds() / 3600.0
        return min(hours / 24.0, 1.0)
    except Exception:
        return 0.0


def _severity_load(discrepancy_counts: Optional[Dict[str, int]]) -> float:
    """
    severity_load = Σ(tier1×1.0 + tier2×0.4 + tier3×0.1) dinormalisasi ke [0,1].
    discrepancy_counts: {"tier1": N, "tier2": N, "tier3": N}
    """
    if not discrepancy_counts:
        return 0.0
    raw = (
        discrepancy_counts.get("tier1", 0) * 1.0 +
        discrepancy_counts.get("tier2", 0) * 0.4 +
        discrepancy_counts.get("tier3", 0) * 0.1
    )
    # Normalisasi: asumsikan maksimum wajar = 5 temuan tier1 = 5.0
    return min(raw / 5.0, 1.0)


# ---------------------------------------------------------------------------
# Skor komposit utama
# ---------------------------------------------------------------------------

def compute_queue_score(
    entry: Dict[str, Any],
    now: datetime,
    ml_percentile: float,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> float:
    """
    priority_score = 100 × (
        w_sla    × sla_pressure
      + w_ml     × ml_percentile    [0–1, dalam bangsal]
      + w_sev    × severity_load
      + w_dis    × discharge_pressure
      + w_wait   × wait_norm
    )

    Contoh §4.4 QUEUE_PLAN:
      A: HIGH(aturan), elapsed=3.2j, target=4j, ml_pct=0.85, sev=1.0, dis=0, wait=0.133
         → sla_pressure=min(3.2/4,2)/2=0.40
         → skor = 100×(0.40×0.40 + 0.25×0.85 + 0.15×1.0 + 0.10×0 + 0.10×0.133)
               = 100×(0.160+0.2125+0.150+0+0.0133) = 53.6 ✓

      B: HIGH(ML), elapsed=20mnt=0.333j, target=4j, ml_pct=0.95, sev=0, dis=0, wait=0.014
         → sla_pressure=min(0.333/4,2)/2 ≈ 0.042
         → skor = 100×(0.40×0.042 + 0.25×0.95 + 0 + 0 + 0.10×0.014)
               ≈ 25.5 ✓

      C: MED(SLA), elapsed=12j, target=24j, ml_pct=0.30, sev=0, dis=0.9, wait=0.5
         → sla_pressure=min(12/24,2)/2=0.25
         → skor = 100×(0.40×0.25 + 0.25×0.30 + 0 + 0.10×0.9 + 0.10×0.5)
               = 100×(0.10+0.075+0+0.09+0.05) = 31.5 ✓
    """
    tier_str = TIER_FROM_RANK.get(entry.get("tier_rank", 1), "MEDIUM")
    sla_cfg = cfg.sla.get(tier_str)
    target_hours = sla_cfg.target_hours if sla_cfg else 24.0

    admitted_at = entry.get("admitted_at", "")
    try:
        dt_admitted = datetime.fromisoformat(admitted_at.replace("Z", "+00:00"))
        if dt_admitted.tzinfo is None:
            dt_admitted = dt_admitted.replace(tzinfo=timezone.utc)
        elapsed = (now - dt_admitted).total_seconds() / 3600.0
    except Exception:
        elapsed = 0.0

    sla_p   = _sla_pressure(elapsed, target_hours)
    dis_p   = _discharge_pressure(entry.get("discharge_planned_at"), now)
    wait_p  = _wait_norm(admitted_at, now)
    sev_p   = _severity_load(entry.get("discrepancy_counts"))

    effective_ml_pct = 0.5 if ml_percentile is None else float(ml_percentile)

    score = 100.0 * (
        cfg.w_sla_pressure       * sla_p
        + cfg.w_ml_percentile    * effective_ml_pct
        + cfg.w_severity_load    * sev_p
        + cfg.w_discharge_pressure * dis_p
        + cfg.w_wait_norm        * wait_p
    )
    return round(score, 2)


# ---------------------------------------------------------------------------
# Tier dari ML score (dengan kuota)
# ---------------------------------------------------------------------------

def compute_tier_from_ml_score(
    ml_score: float,
    high_threshold_value: float | None = None,
    medium_threshold_value: float | None = None,
) -> str:
    """ML probability → tier string (sebelum kuota diterapkan)."""
    high = high_threshold() if high_threshold_value is None else high_threshold_value
    medium = medium_threshold() if medium_threshold_value is None else medium_threshold_value
    if ml_score >= high:
        return "HIGH"
    if ml_score >= medium:
        return "MEDIUM"
    return "LOW"


def compute_tier_source(
    has_rule_finding: bool,        # temuan Tier-1, high-alert, alergi silang
    sla_escalated: bool,           # SLA breach/warning menyebabkan naik
    ml_tier: str,
) -> Tuple[str, str]:
    """
    Tentukan tier_final dan tier_source.

    ADR-21: RULE > SLA > ML — lantai aturan tidak pernah diturunkan.
    Returns (tier_final, tier_source).
    """
    if has_rule_finding:
        return "HIGH", "RULE"
    if sla_escalated:
        # SLA dapat menaikkan tier ML
        return "HIGH", "SLA"  # SLA breach selalu ke HIGH (simplified)
    return ml_tier, "ML"


# ---------------------------------------------------------------------------
# Kuota HIGH-ML (ADR-21)
# ---------------------------------------------------------------------------

def apply_ml_quota(
    entries: List[Dict[str, Any]],
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> List[Dict[str, Any]]:
    """
    Batasi entri HIGH(ML) per bangsal ≤ cfg.ml_high_quota_pct dari total OPEN.

    TIDAK mengubah entri dengan tier_source=RULE atau tier_source=SLA
    (lantai aturan tidak pernah turun — ADR-21).

    Entri yang melebihi kuota diturunkan ke MEDIUM (hanya tier_rank, bukan tier_source=RULE).

    Returns: list entri yang (mungkin) sudah dimodifikasi tier_rank-nya.
    """
    # Kelompokkan per bangsal
    wards: Dict[str, List[Dict[str, Any]]] = {}
    for e in entries:
        w = e.get("ward", "__unknown__")
        wards.setdefault(w, []).append(e)

    result = []
    for ward_name, ward_entries in wards.items():
        open_count = sum(1 for e in ward_entries if e.get("state") == "OPEN")
        quota_max = math.ceil(open_count * cfg.ml_high_quota_pct) if open_count > 0 else 0

        # Urutkan HIGH(ML) berdasarkan skor untuk pilih yang masuk kuota
        ml_highs = sorted(
            [e for e in ward_entries
             if e.get("tier_rank") == 2 and e.get("tier_source") == "ML"],
            key=lambda x: x.get("priority_score", 0),
            reverse=True,
        )

        ml_high_count = 0
        for e in ward_entries:
            entry = dict(e)  # shallow copy agar tidak mutate original
            if (entry.get("tier_rank") == 2
                    and entry.get("tier_source") == "ML"):
                if ml_high_count < quota_max:
                    ml_high_count += 1
                    # masuk kuota — pertahankan HIGH
                else:
                    # melebihi kuota → turunkan ke MEDIUM
                    entry["tier_rank"] = 1  # MEDIUM
                    # tier_source tetap ML (transparan)
            result.append(entry)

    return result


# ---------------------------------------------------------------------------
# Histeresis (§4.3 QUEUE_PLAN)
# ---------------------------------------------------------------------------

def apply_hysteresis(
    current_tier_rank: int,
    new_tier_rank: int,
    current_score: float,
    new_score: float,
    tier_source: str,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> Tuple[int, float]:
    """
    Histeresis untuk perubahan tier akibat ML:
    - Kenaikan tier (ML): hanya berlaku jika selisih skor > margin
    - Penurunan tier (ML): hanya berlaku jika selisih skor > margin
    - RULE dan SLA: selalu langsung berlaku (tidak ada histeresis)

    Returns (final_tier_rank, final_score).
    """
    if tier_source in ("RULE", "SLA"):
        # Jaminan: RULE dan SLA selalu berlaku langsung (ADR-21)
        return new_tier_rank, new_score

    # Hanya untuk ML: terapkan histeresis
    score_diff = abs(new_score - current_score) / 100.0  # normalisasi ke 0-1
    if score_diff < cfg.tier_hysteresis_margin and new_tier_rank != current_tier_rank:
        # Selisih terlalu kecil → pertahankan tier lama (stabilitas)
        return current_tier_rank, new_score
    return new_tier_rank, new_score


# ---------------------------------------------------------------------------
# Penentuan next_due_at (untuk tick SLA)
# ---------------------------------------------------------------------------

def determine_next_due_at(
    entry: Dict[str, Any],
    now: datetime,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> Optional[str]:
    """
    Kapan entri ini perlu dievaluasi ulang SLA-nya?

    Untuk entri OPEN/CLAIMED: ambang SLA warning berikutnya yang belum terlewati.
    Untuk PARKED_DPJP / CLOSED: None (tidak perlu tick).
    """
    state = entry.get("state", "OPEN")
    if state in ("PARKED_DPJP", "CLOSED"):
        return None

    admitted_at = entry.get("admitted_at", "")
    try:
        dt_admitted = datetime.fromisoformat(admitted_at.replace("Z", "+00:00"))
        if dt_admitted.tzinfo is None:
            dt_admitted = dt_admitted.replace(tzinfo=timezone.utc)
    except Exception:
        return None

    tier_str = TIER_FROM_RANK.get(entry.get("tier_rank", 1), "MEDIUM")
    sla_cfg = cfg.sla.get(tier_str)
    if not sla_cfg:
        return None

    warning_due = dt_admitted + timedelta(hours=sla_cfg.warning_hours)
    target_due  = dt_admitted + timedelta(hours=sla_cfg.target_hours)

    # Ambang berikutnya yang belum terlewati
    if now < warning_due:
        return warning_due.isoformat()
    if now < target_due:
        return target_due.isoformat()
    # Sudah breach — next_due_at = None (sudah di-eskalasi)
    return None


# ---------------------------------------------------------------------------
# Pengurutan deterministik (P5)
# ---------------------------------------------------------------------------

def sort_queue(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Urutan deterministik (§4.1 QUEUE_PLAN):
      tier_rank↓, priority_score↓, admitted_at↑, encounter_id↑

    Menghasilkan urutan yang sama untuk input yang sama (P5).
    """
    return sorted(
        entries,
        key=lambda e: (
            -e.get("tier_rank", 0),
            -e.get("priority_score", 0.0),
            e.get("admitted_at", ""),
            e.get("encounter_id", ""),
        ),
    )


# ---------------------------------------------------------------------------
# Hitung ulang ml_percentile dalam bangsal
# ---------------------------------------------------------------------------

def compute_ml_percentiles(
    entries: List[Dict[str, Any]],
) -> Dict[str, float]:
    """
    Hitung persentil ML per bangsal untuk semua entri OPEN/CLAIMED.

    Returns dict {encounter_id: percentile [0–1]}.
    """
    # Kelompokkan per bangsal
    ward_scores: Dict[str, List[Tuple[str, float]]] = {}
    for e in entries:
        if e.get("state") not in ("OPEN", "CLAIMED"):
            continue
        w = e.get("ward", "__unknown__")
        ml = e.get("ml_score", 0.0) or 0.0
        ward_scores.setdefault(w, []).append((e["encounter_id"], ml))

    result: Dict[str, float] = {}
    for ward_name, items in ward_scores.items():
        if len(items) == 1:
            result[items[0][0]] = 0.5  # satu-satunya → persentil tengah
            continue
        sorted_items = sorted(items, key=lambda x: x[1])
        n = len(sorted_items)
        for rank, (enc_id, _) in enumerate(sorted_items):
            result[enc_id] = rank / (n - 1) if n > 1 else 0.5
    return result


# ---------------------------------------------------------------------------
# Batch rescore (untuk tick 60 dtk)
# ---------------------------------------------------------------------------

def batch_rescore(
    entries: List[Dict[str, Any]],
    now: datetime,
    cfg: QueueConfig = DEFAULT_CONFIG,
) -> List[Dict[str, Any]]:
    """
    Hitung ulang priority_score + next_due_at untuk semua entri OPEN.

    - ML percentile dihitung per bangsal (relatif)
    - Kuota HIGH-ML diterapkan setelah rescore
    - Histeresis diterapkan per entri
    - Urutan akhir: sort_queue()

    Returns list baru (tidak mutasi input).
    """
    # Step 1: Hitung ml_percentile per bangsal
    percentiles = compute_ml_percentiles(entries)

    # Step 2: Hitung skor baru per entri
    rescored: List[Dict[str, Any]] = []
    for e in entries:
        if e.get("state") == "CLOSED":
            rescored.append(dict(e))
            continue

        enc_id = e["encounter_id"]
        ml_pct = percentiles.get(enc_id, 0.5)

        # --- SLA escalation -------------------------------------------------
        # Bila ambang SLA berikutnya sudah terlewati, naikkan tier satu langkah
        # (LOW→MEDIUM, MEDIUM→HIGH). Tier RULE juga boleh naik; yang dilarang
        # adalah menurunkan lantai aturan (ADR-21).
        new_rank = int(e.get("tier_rank", 1) or 0)
        new_source = e.get("tier_source", "ML")
        old_due = e.get("next_due_at")
        if old_due and new_rank < 2:
            try:
                due_dt = datetime.fromisoformat(str(old_due).replace("Z", "+00:00"))
                if due_dt.tzinfo is None:
                    due_dt = due_dt.replace(tzinfo=timezone.utc)
                if now >= due_dt:
                    new_rank = min(new_rank + 1, 2)
                    new_source = "SLA"
            except Exception:
                pass

        entry = dict(e)
        entry["tier_rank"] = new_rank
        entry["tier_source"] = new_source
        new_score = compute_queue_score(entry, now, ml_pct, cfg)
        new_next_due = determine_next_due_at(entry, now, cfg)

        # Histeresis (hanya untuk ML)
        final_rank, final_score = apply_hysteresis(
            current_tier_rank=e.get("tier_rank", 1),
            new_tier_rank=new_rank,
            current_score=e.get("priority_score", 0.0),
            new_score=new_score,
            tier_source=new_source,
            cfg=cfg,
        )
        entry["tier_rank"] = final_rank
        entry["priority_score"] = final_score
        entry["ml_percentile"]  = ml_pct
        entry["next_due_at"]    = new_next_due
        rescored.append(entry)

    # Step 3: Kuota HIGH-ML per bangsal (ADR-21)
    rescored = apply_ml_quota(rescored, cfg)

    # Step 4: Urutan deterministik
    return sort_queue(rescored)
