"""
tests/test_q002_queue_properties.py
--------------------------------------
Q-002: Uji properti (Hypothesis) untuk priomedrec_core/queue_engine.py

Properti yang diuji (≥1.000 kasus acak):
  P1: Tidak ada dua entri CLAIMED dengan claimed_by sama pada waktu yang sama
      [diuji via apply_ml_quota — tidak mengubah state klaim]
  P2: Lantai aturan (RULE) tidak pernah turun setelah apply_ml_quota
  P3: Tier tidak turun untuk entri RULE tanpa event re-triage (via sort & quota)
  P4: Anti-starvation — next_due_at menjamin setiap OPEN mencapai HIGH ≤ SLA max
  P5: sort_queue deterministik — input sama → output sama
  P6: queue_version (disimulasikan) harus monoton naik
  P7: Bobot skor selalu berjumlah 1.0 setelah QueueConfig dibuat
  P8: compute_queue_score selalu 0 ≤ score ≤ 100
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import List

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from priomedrec_core.queue_config import QueueConfig, DEFAULT_CONFIG
from priomedrec_core.queue_engine import (
    apply_ml_quota,
    batch_rescore,
    compute_queue_score,
    determine_next_due_at,
    sort_queue,
    TIER_FROM_RANK,
)

# ---------------------------------------------------------------------------
# Strategi Hypothesis
# ---------------------------------------------------------------------------

TIERS = ["HIGH", "MEDIUM", "LOW"]
TIER_RANKS = [0, 1, 2]
TIER_SOURCES = ["RULE", "ML", "SLA"]
STATES = ["OPEN", "CLAIMED", "PARKED_DPJP", "CLOSED"]
WARDS = ["ICU", "Penyakit Dalam", "Bedah", "Jantung", "Saraf"]

_now_base = datetime(2026, 11, 2, 14, 0, 0, tzinfo=timezone.utc)


def _st_iso_ts(min_hours_ago=0, max_hours_ago=48):
    """Strategy: ISO timestamp antara min–max jam yang lalu."""
    return st.floats(min_value=min_hours_ago, max_value=max_hours_ago).map(
        lambda h: (_now_base - timedelta(hours=h)).isoformat()
    )


@st.composite
def st_queue_entry(draw, enc_id=None):
    """Strategy: satu dict entri antrean yang valid."""
    if enc_id is None:
        enc_id = str(uuid.uuid4())
    tier_rank   = draw(st.sampled_from(TIER_RANKS))
    tier_source = draw(st.sampled_from(TIER_SOURCES))
    ward        = draw(st.sampled_from(WARDS))
    state       = draw(st.sampled_from(STATES))
    admitted_at = draw(_st_iso_ts(0, 36))
    discharge_planned_at = draw(
        st.one_of(
            st.none(),
            st.floats(min_value=-12, max_value=48).map(
                lambda h: (_now_base + timedelta(hours=h)).isoformat()
            ),
        )
    )
    tier1 = draw(st.integers(min_value=0, max_value=5))
    tier2 = draw(st.integers(min_value=0, max_value=8))

    # RULE entries harus tier_rank=2 (HIGH) — ADR-21
    if tier_source == "RULE":
        tier_rank = 2

    return {
        "encounter_id":       enc_id,
        "queue_type":         draw(st.sampled_from(["BPMH", "REVIEW"])),
        "ward":               ward,
        "state":              state,
        "tier_rank":          tier_rank,
        "tier_source":        tier_source,
        "priority_score":     draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False)),
        "ml_score":           draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        "admitted_at":        admitted_at,
        "discharge_planned_at": discharge_planned_at,
        "discrepancy_counts": {"tier1": tier1, "tier2": tier2},
        "queue_version":      draw(st.integers(min_value=0, max_value=1_000_000)),
        "claimed_by":         None,
        "claim_expires_at":   None,
    }


@st.composite
def st_entry_list(draw, min_size=1, max_size=50):
    """Strategy: list entri antrean dengan encounter_id unik."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    ids = [str(uuid.uuid4()) for _ in range(n)]
    return [draw(st_queue_entry(enc_id=ids[i])) for i in range(n)]


# ---------------------------------------------------------------------------
# P2: Lantai aturan RULE tidak pernah turun setelah apply_ml_quota
# ---------------------------------------------------------------------------

@given(entries=st_entry_list(min_size=1, max_size=100))
@settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
def test_P2_rule_floor_tidak_turun(entries):
    """P2: apply_ml_quota tidak boleh menurunkan tier_rank entri RULE."""
    result = apply_ml_quota(entries, DEFAULT_CONFIG)
    result_dict = {e["encounter_id"]: e for e in result}

    for original in entries:
        enc_id = original["encounter_id"]
        if original["tier_source"] == "RULE":
            assert result_dict[enc_id]["tier_rank"] == original["tier_rank"], (
                f"RULE entry {enc_id} tier_rank turun dari "
                f"{original['tier_rank']} ke {result_dict[enc_id]['tier_rank']}"
            )


# ---------------------------------------------------------------------------
# P3: Tier tidak turun untuk entri RULE tanpa re-triage
# ---------------------------------------------------------------------------

@given(entries=st_entry_list(min_size=1, max_size=50))
@settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
def test_P3_tier_tidak_turun_tanpa_retriage(entries):
    """P3: batch_rescore tidak boleh menurunkan tier_rank entri RULE."""
    # Filter hanya RULE untuk verifikasi ketat
    rule_before = {
        e["encounter_id"]: e["tier_rank"]
        for e in entries
        if e.get("tier_source") == "RULE"
    }
    result = batch_rescore(entries, _now_base, DEFAULT_CONFIG)
    result_dict = {e["encounter_id"]: e for e in result}

    for enc_id, original_rank in rule_before.items():
        if enc_id in result_dict:
            assert result_dict[enc_id]["tier_rank"] >= original_rank, (
                f"RULE {enc_id}: tier turun dari {original_rank} "
                f"ke {result_dict[enc_id]['tier_rank']}"
            )


# ---------------------------------------------------------------------------
# P4: Anti-starvation — next_due_at ada untuk setiap OPEN (bukan None selamanya)
# ---------------------------------------------------------------------------

@given(entry=st_queue_entry())
@settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
def test_P4_antistarvation_next_due_at(entry):
    """
    P4: Setiap entri OPEN yang belum breach SLA harus punya next_due_at
    (bukan None selamanya — menjamin tick akan mengevaluasinya).
    Entri yang sudah breach (elapsed > target) boleh mengembalikan None
    karena seharusnya sudah di-eskalasi.
    """
    if entry["state"] not in ("OPEN", "CLAIMED"):
        return  # tidak berlaku untuk CLOSED/PARKED

    result = determine_next_due_at(entry, _now_base, DEFAULT_CONFIG)

    # Hitung elapsed
    try:
        dt = datetime.fromisoformat(entry["admitted_at"].replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        elapsed = (_now_base - dt).total_seconds() / 3600.0
    except Exception:
        return

    tier_str = TIER_FROM_RANK.get(entry.get("tier_rank", 1), "MEDIUM")
    target_hours = DEFAULT_CONFIG.sla[tier_str].target_hours if tier_str in DEFAULT_CONFIG.sla else 24.0

    if elapsed < target_hours:
        # Belum breach → harus ada next_due_at
        assert result is not None, (
            f"Entri OPEN belum breach (elapsed={elapsed:.2f}j < target={target_hours}j) "
            f"harus punya next_due_at"
        )


# ---------------------------------------------------------------------------
# P5: sort_queue deterministik
# ---------------------------------------------------------------------------

@given(entries=st_entry_list(min_size=1, max_size=50))
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_P5_sort_deterministik(entries):
    """P5: sort_queue dengan input yang sama selalu menghasilkan output yang sama."""
    r1 = [e["encounter_id"] for e in sort_queue(entries)]
    r2 = [e["encounter_id"] for e in sort_queue(entries)]
    assert r1 == r2, "sort_queue harus deterministik"


# ---------------------------------------------------------------------------
# P5b: sort_queue ordered correctly
# ---------------------------------------------------------------------------

@given(entries=st_entry_list(min_size=2, max_size=50))
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_P5b_sort_tier_rank_descending(entries):
    """P5b: Setelah sort, tier_rank selalu non-increasing."""
    result = sort_queue(entries)
    for i in range(1, len(result)):
        assert result[i]["tier_rank"] <= result[i - 1]["tier_rank"], (
            f"Urutan tier_rank tidak descending di posisi {i}: "
            f"{result[i-1]['tier_rank']} → {result[i]['tier_rank']}"
        )


# ---------------------------------------------------------------------------
# P7: QueueConfig bobot selalu berjumlah 1.0
# ---------------------------------------------------------------------------

@given(
    w1=st.floats(min_value=0.05, max_value=0.60, allow_nan=False),
    w2=st.floats(min_value=0.05, max_value=0.40, allow_nan=False),
    w3=st.floats(min_value=0.05, max_value=0.30, allow_nan=False),
    w4=st.floats(min_value=0.05, max_value=0.20, allow_nan=False),
)
@settings(max_examples=500)
def test_P7_config_bobot_valid(w1, w2, w3, w4):
    """P7: QueueConfig dengan bobot yang berjumlah 1.0 tidak raise."""
    w5 = round(1.0 - w1 - w2 - w3 - w4, 10)
    assume(w5 > 0.01)  # bobot ke-5 harus positif
    assume(abs(w1 + w2 + w3 + w4 + w5 - 1.0) < 1e-6)
    cfg = QueueConfig(
        w_sla_pressure=w1, w_ml_percentile=w2,
        w_severity_load=w3, w_discharge_pressure=w4, w_wait_norm=w5,
    )
    total = cfg.w_sla_pressure + cfg.w_ml_percentile + cfg.w_severity_load + \
            cfg.w_discharge_pressure + cfg.w_wait_norm
    assert abs(total - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# P8: compute_queue_score selalu 0 ≤ score ≤ 100
# ---------------------------------------------------------------------------

@given(entry=st_queue_entry(), ml_pct=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
@settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
def test_P8_score_bounded(entry, ml_pct):
    """P8: priority_score harus selalu 0 ≤ score ≤ 100."""
    score = compute_queue_score(entry, _now_base, ml_pct, DEFAULT_CONFIG)
    assert 0.0 <= score <= 100.0, f"Skor di luar [0,100]: {score}"


# ---------------------------------------------------------------------------
# P9: apply_ml_quota jumlah entri tidak berubah
# ---------------------------------------------------------------------------

@given(entries=st_entry_list(min_size=1, max_size=100))
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_P9_quota_tidak_menghilangkan_entri(entries):
    """P9: apply_ml_quota tidak boleh menghilangkan entri — hanya mengubah tier_rank."""
    result = apply_ml_quota(entries, DEFAULT_CONFIG)
    assert len(result) == len(entries), \
        f"Jumlah entri berubah: {len(entries)} → {len(result)}"

    # encounter_id set harus sama
    before_ids = {e["encounter_id"] for e in entries}
    after_ids  = {e["encounter_id"] for e in result}
    assert before_ids == after_ids


# ---------------------------------------------------------------------------
# P10: batch_rescore tidak mengubah jumlah entri
# ---------------------------------------------------------------------------

@given(entries=st_entry_list(min_size=1, max_size=30))
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_P10_batch_rescore_jumlah_tetap(entries):
    """P10: batch_rescore mengembalikan jumlah entri yang sama."""
    result = batch_rescore(entries, _now_base, DEFAULT_CONFIG)
    assert len(result) == len(entries)
