"""
src/data/patient_resolver.py
-----------------------------
Resolves a patient_id (and optional encounter_id) into a structured
admission context dict that the API layer can use directly.

This is the key component that allows POST /analyze to accept only a
patient_id — feature vector construction is done here, not by the caller.

Data sources (from processed/interim):
  - data/processed/model_ready.csv      → features + patient_id
  - data/interim/admission_cohort.csv   → encounter metadata
  - data/interim/pre_admission_meds.csv → pre-admission medication list
  - data/interim/admission_meds.csv     → admission medication list

All files are loaded lazily (on first call) and cached in module-level
variables so repeated API calls don't reload CSVs on every request.
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Module-level cache (lazy-loaded on first call)
# ---------------------------------------------------------------------------
_model_ready: pd.DataFrame | None = None
_cohort: pd.DataFrame | None = None
_pre_meds: pd.DataFrame | None = None
_adm_meds: pd.DataFrame | None = None

_DATA_DIR = Path("data")
_MODEL_READY_PATH  = _DATA_DIR / "processed" / "model_ready.csv"
_COHORT_PATH       = _DATA_DIR / "interim"   / "admission_cohort.csv"
_PRE_MEDS_PATH     = _DATA_DIR / "interim"   / "pre_admission_meds.csv"
_ADM_MEDS_PATH     = _DATA_DIR / "interim"   / "admission_meds.csv"


def _load_all() -> None:
    global _model_ready, _cohort, _pre_meds, _adm_meds
    if _model_ready is None:
        _model_ready = pd.read_csv(_MODEL_READY_PATH)
    if _cohort is None:
        _cohort = pd.read_csv(_COHORT_PATH)
    if _pre_meds is None:
        _pre_meds = pd.read_csv(_PRE_MEDS_PATH)
    if _adm_meds is None:
        _adm_meds = pd.read_csv(_ADM_MEDS_PATH)


# ---------------------------------------------------------------------------
# Feature columns (must match model training order)
# ---------------------------------------------------------------------------
FEATURE_COLUMNS = [
    "age", "age_65_plus", "gender_encoded",
    "pre_admission_medication_count", "admission_medication_count",
    "total_medication_count", "new_medication_count",
    "discontinued_medication_count", "polypharmacy_flag",
    "high_alert_flag", "high_alert_count", "potential_duplicate_candidates",
    "active_condition_count", "prior_encounter_count",
    "allergy_count", "has_drug_allergy",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_patient_encounters(patient_id: str) -> list[dict]:
    """
    Return all admission encounters for a given patient_id.
    Each item contains: encounter_id, encounter_start, encounter_class,
    encounter_type, age, gender.
    """
    _load_all()
    rows = _cohort[_cohort["patient_id"] == patient_id]
    if rows.empty:
        return []
    result = []
    for _, r in rows.iterrows():
        result.append({
            "encounter_id":    r["encounter_id"],
            "encounter_start": str(r.get("encounter_start", "")),
            "encounter_end":   str(r.get("encounter_end", "")),
            "encounter_class": str(r.get("encounter_class", "")),
            "encounter_type":  str(r.get("encounter_type", "")),
            "age":             float(r.get("age", 0)) if pd.notna(r.get("age")) else None,
            "gender":          str(r.get("gender", "")),
        })
    # Sort by encounter_start descending (most recent first)
    result.sort(key=lambda x: x["encounter_start"], reverse=True)
    return result


def resolve_patient(
    patient_id: str,
    encounter_id: Optional[str] = None,
) -> dict:
    """
    Resolve a patient into a full admission context dict.

    If encounter_id is None, uses the most recent admission encounter
    for the patient.

    Returns
    -------
    dict with keys:
        patient_id, encounter_id, encounter_meta (dict),
        feature_vector (dict of 16 features),
        pre_admission_meds (list of dicts),
        admission_meds (list of dicts),
        found (bool)

    Raises
    ------
    ValueError if patient_id is not found in the dataset.
    """
    _load_all()

    # Find patient encounters
    pat_cohort = _cohort[_cohort["patient_id"] == patient_id]
    if pat_cohort.empty:
        raise ValueError(f"Patient '{patient_id}' not found in admission cohort.")

    # Select encounter
    if encounter_id:
        enc_rows = pat_cohort[pat_cohort["encounter_id"] == encounter_id]
        if enc_rows.empty:
            raise ValueError(
                f"Encounter '{encounter_id}' not found for patient '{patient_id}'."
            )
        enc_row = enc_rows.iloc[0]
    else:
        # Most recent admission
        pat_cohort_sorted = pat_cohort.sort_values("encounter_start", ascending=False)
        enc_row = pat_cohort_sorted.iloc[0]

    enc_id = enc_row["encounter_id"]

    # Build encounter metadata
    encounter_meta = {
        "encounter_id":    enc_id,
        "encounter_start": str(enc_row.get("encounter_start", "")),
        "encounter_end":   str(enc_row.get("encounter_end", "")),
        "encounter_class": str(enc_row.get("encounter_class", "")),
        "encounter_type":  str(enc_row.get("encounter_type", "")),
        "age":             float(enc_row["age"]) if pd.notna(enc_row.get("age")) else None,
        "gender":          str(enc_row.get("gender", "")),
        "reason":          str(enc_row.get("reason", "")),
    }

    # Pull feature vector from model_ready (already computed)
    feat_rows = _model_ready[_model_ready["encounter_id"] == enc_id]
    if feat_rows.empty:
        # Encounter exists in cohort but not in feature_matrix (e.g. no meds)
        # Return zero-vector; model will produce a low-confidence result
        feature_vector = {col: 0 for col in FEATURE_COLUMNS}
    else:
        feat_row = feat_rows.iloc[0]
        feature_vector = {
            col: (
                int(feat_row[col])
                if str(feat_row[col]).replace(".", "").isdigit()
                   and "." not in str(feat_row[col])
                else float(feat_row[col]) if pd.notna(feat_row.get(col)) else 0
            )
            for col in FEATURE_COLUMNS
            if col in feat_row.index
        }

    # Pre-admission medications
    pre_enc = _pre_meds[_pre_meds["admission_encounter_id"] == enc_id]
    pre_meds_list = _meds_to_list(pre_enc)

    # Admission medications
    adm_enc = _adm_meds[_adm_meds["encounter_id"] == enc_id]
    adm_meds_list = _meds_to_list(adm_enc)

    return {
        "patient_id":        patient_id,
        "encounter_id":      enc_id,
        "encounter_meta":    encounter_meta,
        "feature_vector":    feature_vector,
        "pre_admission_meds": pre_meds_list,
        "admission_meds":    adm_meds_list,
        "found":             True,
    }


def _meds_to_list(df: pd.DataFrame) -> list[dict]:
    """Convert a medications DataFrame slice to a list of dicts for the API."""
    if df.empty:
        return []
    result = []
    for _, row in df.iterrows():
        result.append({
            "medication_code": str(row.get("medication_code", "")) if pd.notna(row.get("medication_code")) else "",
            "medication_name": str(row.get("medication_name", "")) if pd.notna(row.get("medication_name")) else "",
        })
    return result


def list_known_patients(limit: int = 20) -> list[str]:
    """Return a sample of patient_ids present in the cohort (for testing/demo)."""
    _load_all()
    return _cohort["patient_id"].drop_duplicates().head(limit).tolist()
