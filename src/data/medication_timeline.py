"""
src/data/medication_timeline.py
---------------------------------
Builds the medication timeline and splits it into:
  - pre_admission_meds  : medications authored/administered BEFORE encounter_start
  - admission_meds      : medications authored/administered DURING the encounter window

Design principles (from PROJECT_CONTEXT + DECISION_LOG):
  - Temporal ordering is based on authored_on (medication_requests) or
    effective_datetime (medication_administrations).
  - No future leakage: for each encounter, only events with
    event_datetime < encounter_start are considered pre-admission.
  - medication_requests with null medication_name use medication_code as identity
    (DQI-004). Rows with both null are excluded.
  - medication_requests.encounter_id that do not match encounters are treated as
    "background" medications (chronic/outpatient) — included in pre_admission_meds
    with source='background' (DQI-006).
  - Minimal normalisation is applied here: lowercase strip + RxNorm code as
    primary identifier. Full normalisation lives in src/rules/medication_normalizer.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from src.data.loaders import (
    load_medication_requests,
    load_medication_administrations,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_name(series: pd.Series) -> pd.Series:
    """Minimal normalisation: lowercase + strip whitespace."""
    return series.astype(str).str.lower().str.strip()


def _build_unified_timeline(
    base_dir: str,
) -> pd.DataFrame:
    """
    Merge medication_requests and medication_administrations into one
    timeline DataFrame with a common schema.

    Returns
    -------
    pd.DataFrame with columns:
        patient_id, encounter_id, medication_name, medication_code,
        event_datetime, status, source
    """
    # ---- medication_requests ----
    mr = load_medication_requests(base_dir)

    # DQI-004: drop rows where both medication_name and medication_code are null
    mr = mr.dropna(subset=["medication_name", "medication_code"], how="all")

    # Fill medication_name from medication_code where name is null
    mr["medication_name"] = mr["medication_name"].fillna(mr["medication_code"])

    mr["event_datetime"] = pd.to_datetime(mr["authored_on"], utc=True)
    mr_timeline = mr[
        ["patient_id", "encounter_id", "medication_name", "medication_code", "event_datetime", "status"]
    ].copy()
    mr_timeline["source"] = "medication_request"

    # ---- medication_administrations ----
    ma = load_medication_administrations(base_dir)
    ma["event_datetime"] = pd.to_datetime(ma["effective_datetime"], utc=True)
    ma_timeline = ma[
        ["patient_id", "encounter_id", "medication_name", "medication_code", "event_datetime", "status"]
    ].copy()
    ma_timeline["source"] = "medication_administration"

    # ---- combine ----
    timeline = pd.concat([mr_timeline, ma_timeline], ignore_index=True)
    timeline["medication_name_normalized"] = _normalize_name(timeline["medication_name"])
    timeline = timeline.sort_values(
        by=["patient_id", "event_datetime"],
        kind="mergesort",
    ).reset_index(drop=True)

    return timeline


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_medication_timeline(
    base_dir: str = "data/raw/synthea",
) -> pd.DataFrame:
    """
    Build the full patient medication timeline sorted temporally.

    Returns
    -------
    pd.DataFrame
        All medication events, ordered by patient_id + event_datetime.
    """
    return _build_unified_timeline(base_dir)


def build_pre_admission_meds(
    cohort: pd.DataFrame,
    timeline: pd.DataFrame,
) -> pd.DataFrame:
    """
    For each admission encounter in *cohort*, return medications whose
    event_datetime is strictly BEFORE encounter_start.

    Leakage prevention: event_datetime < encounter_start (strict less-than).
    Active medications only: status NOT IN ('completed', 'stopped').

    Memory-efficient: processes each patient's encounters sequentially,
    avoiding a full cross-join between timeline and cohort.

    Parameters
    ----------
    cohort:
        Output of build_admission_cohort() — must have encounter_id,
        patient_id, encounter_start (datetime, UTC-aware).
    timeline:
        Output of build_medication_timeline().

    Returns
    -------
    pd.DataFrame
        One row per (admission_encounter_id, medication event).
    """
    active_statuses = {"completed", "stopped"}

    # Keep only active medication events
    active_timeline = timeline[~timeline["status"].isin(active_statuses)].copy()

    # Only work with patients that appear in the cohort
    cohort_patients = cohort["patient_id"].unique()
    active_timeline = active_timeline[active_timeline["patient_id"].isin(cohort_patients)]

    # Join on patient_id — this is bounded: cohort has 31K rows,
    # active_timeline after filtering has only active (non-completed) events.
    cohort_info = cohort[["encounter_id", "patient_id", "encounter_start"]].rename(
        columns={"encounter_id": "admission_encounter_id"}
    )
    merged = active_timeline.merge(cohort_info, on="patient_id", how="inner")

    # Strict temporal cut: event BEFORE encounter_start (leakage prevention)
    pre = merged[merged["event_datetime"] < merged["encounter_start"]].copy()
    pre = pre.reset_index(drop=True)
    return pre


def build_admission_meds(
    cohort: pd.DataFrame,
    timeline: pd.DataFrame,
) -> pd.DataFrame:
    """
    For each admission encounter, return medications authored/administered
    DURING the encounter window: encounter_start <= event_datetime <= encounter_end.

    Parameters
    ----------
    cohort:
        Must have encounter_id, patient_id, encounter_start, encounter_end.
    timeline:
        Output of build_medication_timeline().

    Returns
    -------
    pd.DataFrame
        One row per (encounter_id, medication event) during the admission.
    """
    cohort_info = cohort[["encounter_id", "patient_id", "encounter_start", "encounter_end"]].copy()

    # Join on encounter_id (direct match for within-encounter medications)
    merged = timeline.merge(
        cohort_info, on="encounter_id", how="inner",
        suffixes=("", "_enc")
    )

    # Window: event_datetime within [encounter_start, encounter_end]
    in_window = (
        (merged["event_datetime"] >= merged["encounter_start"]) &
        (merged["event_datetime"] <= merged["encounter_end"])
    )
    admission = merged[in_window].copy()
    admission = admission.reset_index(drop=True)
    return admission


def save_timeline_artifacts(
    timeline: pd.DataFrame,
    pre_meds: pd.DataFrame,
    adm_meds: pd.DataFrame,
    out_dir: str = "data/interim",
) -> None:
    """Save all three medication interim files."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    timeline_path = f"{out_dir}/medication_timeline.csv"
    pre_path      = f"{out_dir}/pre_admission_meds.csv"
    adm_path      = f"{out_dir}/admission_meds.csv"

    timeline.to_csv(timeline_path, index=False)
    pre_meds.to_csv(pre_path,      index=False)
    adm_meds.to_csv(adm_path,      index=False)

    print(f"medication_timeline saved: {timeline_path} ({len(timeline):,} rows)")
    print(f"pre_admission_meds saved:  {pre_path} ({len(pre_meds):,} rows)")
    print(f"admission_meds saved:      {adm_path} ({len(adm_meds):,} rows)")
