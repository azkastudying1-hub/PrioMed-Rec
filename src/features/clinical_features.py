"""
src/features/clinical_features.py
-----------------------------------
Demographic and clinical complexity features for the admission model.

Features:
  age                  — age at encounter_start (years, float)
  age_65_plus          — binary flag (age >= 65)
  gender_encoded       — 0 = F, 1 = M, -1 = unknown
  active_condition_count — count of active diagnoses for the patient
                           with onset_date <= encounter_start
  prior_encounter_count  — number of prior encounters for the patient
                           BEFORE this admission (leakage-safe)

Clinical safety note: allergy features are excluded (DQI-001 — patient_id
100% null in allergies.csv). They return 0 with a documented flag.
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Demographic features
# ---------------------------------------------------------------------------

def compute_age(birth_date: pd.Series, encounter_start: pd.Series) -> pd.Series:
    """Age in fractional years at encounter_start."""
    birth = pd.to_datetime(pd.Series(birth_date), utc=True)
    start = pd.to_datetime(pd.Series(encounter_start), utc=True)
    return ((start - birth).dt.days / 365.25).round(2)


def encode_gender(gender_series: pd.Series) -> pd.Series:
    """Encode gender: male→1, female→0, other→-1."""
    mapping = {"male": 1, "female": 0, "m": 1, "f": 0}
    return gender_series.str.lower().str.strip().map(mapping).fillna(-1).astype(int)


# ---------------------------------------------------------------------------
# Clinical complexity features
# ---------------------------------------------------------------------------

def compute_active_condition_count(
    cohort: pd.DataFrame,
    conditions: pd.DataFrame,
) -> pd.Series:
    """
    Count active conditions per encounter.

    Leakage-safe: only conditions with onset_date <= encounter_start AND
    clinical_status == 'active'.

    Uses a per-patient approach to avoid a full Cartesian join.

    Returns
    -------
    pd.Series indexed by encounter_id.
    """
    cond = conditions[conditions["clinical_status"].str.lower() == "active"].copy()
    cond["onset_date"] = pd.to_datetime(cond["onset_date"], utc=True)
    cohort_enc = cohort[["encounter_id", "patient_id", "encounter_start"]].copy()
    cohort_enc["encounter_start"] = pd.to_datetime(cohort_enc["encounter_start"], utc=True)

    # Filter conditions to patients in cohort only
    cohort_patients = cohort_enc["patient_id"].unique()
    cond = cond[cond["patient_id"].isin(cohort_patients)]

    # Sort both for merge_asof-style: group conditions by patient, then for each
    # encounter find how many conditions have onset <= encounter_start.
    # We use a cross-join within patient groups (bounded: cohort has 31K, active cond ~631K but
    # filtered to cohort patients only first).
    merged = cohort_enc.merge(
        cond[["patient_id", "onset_date"]],
        on="patient_id",
        how="left",
    )
    mask = merged["onset_date"] <= merged["encounter_start"]
    counts = (
        merged[mask]
        .groupby("encounter_id")
        .size()
        .rename("active_condition_count")
    )
    return counts.reindex(cohort_enc["encounter_id"], fill_value=0)


def compute_prior_encounter_count(
    cohort: pd.DataFrame,
    all_encounters: pd.DataFrame,
) -> pd.Series:
    """
    Count prior encounters for each patient BEFORE this admission.

    Leakage-safe: only encounters where encounter_start < this admission's
    encounter_start are counted.

    Returns
    -------
    pd.Series indexed by encounter_id.
    """
    enc = all_encounters[["patient_id", "encounter_start"]].copy()
    enc["encounter_start"] = pd.to_datetime(enc["encounter_start"], utc=True)

    cohort_enc = cohort[["encounter_id", "patient_id", "encounter_start"]].copy()
    cohort_enc["encounter_start"] = pd.to_datetime(cohort_enc["encounter_start"], utc=True)

    # Filter all_encounters to cohort patients only
    cohort_patients = cohort_enc["patient_id"].unique()
    enc = enc[enc["patient_id"].isin(cohort_patients)]

    merged = cohort_enc.merge(
        enc.rename(columns={"encounter_start": "prior_start"}),
        on="patient_id",
        how="left",
    )
    prior_mask = merged["prior_start"] < merged["encounter_start"]
    counts = (
        merged[prior_mask]
        .groupby("encounter_id")
        .size()
        .rename("prior_encounter_count")
    )
    return counts.reindex(cohort_enc["encounter_id"], fill_value=0)


# ---------------------------------------------------------------------------
# Main assembler
# ---------------------------------------------------------------------------

def compute_clinical_features(
    cohort: pd.DataFrame,
    conditions: pd.DataFrame,
    all_encounters: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build the clinical features DataFrame for all cohort encounters.

    Parameters
    ----------
    cohort:
        Admission cohort (from admission_cohort.py). Must contain:
        encounter_id, patient_id, encounter_start, birth_date, gender, age_65_plus
    conditions:
        Raw conditions DataFrame (from loaders.load_conditions()).
    all_encounters:
        Full encounters DataFrame (not just cohort) for prior_encounter_count.

    Returns
    -------
    pd.DataFrame indexed by encounter_id.
    """
    feats = cohort[["encounter_id"]].copy().set_index("encounter_id")

    # Age (re-compute from birth_date to be independent of pre-computed values)
    feats["age"] = compute_age(
        cohort["birth_date"].values,
        cohort["encounter_start"].values,
    ).values

    feats["age_65_plus"]    = (feats["age"] >= 65).astype(int)
    feats["gender_encoded"] = encode_gender(cohort["gender"]).values

    # Clinical complexity
    feats["active_condition_count"] = compute_active_condition_count(
        cohort, conditions
    ).values

    feats["prior_encounter_count"] = compute_prior_encounter_count(
        cohort, all_encounters
    ).values

    # Allergy features excluded (DQI-001: patient_id 100% null)
    # Set to 0 with documented data_unavailable flag in feature_dictionary.md
    feats["allergy_count"]    = 0
    feats["has_drug_allergy"] = 0

    return feats
