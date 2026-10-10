"""
src/data/loaders.py
-------------------
CSV loader utilities for PrioMed-Rec.

Each loader validates that all expected columns are present before returning
the DataFrame so that downstream code never silently works on incomplete data.
Column schema is kept in sync with docs/data_dictionary.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Expected column definitions (ground-truth from docs/data_dictionary.md)
# ---------------------------------------------------------------------------

SCHEMA: dict[str, List[str]] = {
    "patients": [
        "patient_id", "patient_name", "gender", "birth_date",
        "deceased_date", "marital_status",
    ],
    "encounters": [
        "encounter_id", "patient_id", "encounter_start", "encounter_end",
        "encounter_class", "encounter_class_display", "encounter_type",
        "encounter_type_code", "reason",
    ],
    "medications": [
        "medication_id", "medication_name", "medication_code",
        "medication_system",
    ],
    "medication_requests": [
        "medication_request_id", "patient_id", "encounter_id",
        "medication_name", "medication_code", "medication_system",
        "dose_value", "dose_unit", "frequency", "timing_text", "route",
        "status", "intent", "authored_on",
    ],
    "medication_administrations": [
        "medication_administration_id", "patient_id", "encounter_id",
        "medication_name", "medication_code", "effective_datetime",
        "dose_value", "dose_unit", "route", "status",
    ],
    "conditions": [
        "condition_id", "patient_id", "encounter_id", "condition_name",
        "condition_code", "onset_date", "clinical_status",
        "verification_status",
    ],
    "allergies": [
        "allergy_id", "patient_id", "allergy_name", "allergy_code",
        "clinical_status", "verification_status",
    ],
    "primedrec_master": [
        "encounter_id", "patient_id", "encounter_start_x", "birth_date_x",
        "age", "age_65_plus", "medication_count", "polypharmacy",
        "high_alert_medication", "encounter_start_y", "encounter_end",
        "encounter_class", "encounter_class_display", "encounter_type",
        "encounter_type_code", "reason", "gender", "birth_date_y",
        "deceased_date",
    ],
    "primedrec_risk_features": [
        "encounter_id", "patient_id", "encounter_start", "birth_date",
        "age", "age_65_plus", "medication_count", "polypharmacy",
        "high_alert_medication",
    ],
    "validation_report": [
        "expected_patients", "patient_rows", "unique_patients",
        "encounter_rows", "unique_encounters", "medication_request_rows",
        "medication_administration_rows", "condition_rows", "allergy_rows",
        "observation_rows", "parser_errors",
    ],
}


# ---------------------------------------------------------------------------
# Core loader
# ---------------------------------------------------------------------------

def load_csv(
    path: str | Path,
    expected_cols: Optional[List[str]] = None,
    **read_kwargs,
) -> pd.DataFrame:
    """Load a CSV and optionally validate column presence.

    Parameters
    ----------
    path:
        Absolute or relative path to the CSV file.
    expected_cols:
        If provided, raises ``KeyError`` listing any missing columns before
        the DataFrame is returned.  Pass ``None`` to skip validation.
    **read_kwargs:
        Extra keyword arguments forwarded to ``pandas.read_csv``.

    Returns
    -------
    pd.DataFrame
    """
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False, **read_kwargs)
    if expected_cols is not None:
        missing = [c for c in expected_cols if c not in df.columns]
        if missing:
            raise KeyError(
                f"[loaders] {Path(path).name}: missing expected columns: {missing}"
            )
    return df


# ---------------------------------------------------------------------------
# Named convenience loaders — each uses the verified schema above
# ---------------------------------------------------------------------------

def _raw(name: str, base_dir: str | Path = "data/raw/synthea") -> Path:
    return Path(base_dir) / f"{name}.csv"


def load_patients(base_dir="data/raw/synthea") -> pd.DataFrame:
    return load_csv(_raw("patients", base_dir), SCHEMA["patients"])


def load_encounters(base_dir="data/raw/synthea") -> pd.DataFrame:
    return load_csv(_raw("encounters", base_dir), SCHEMA["encounters"])


def load_medications(base_dir="data/raw/synthea") -> pd.DataFrame:
    return load_csv(_raw("medications", base_dir), SCHEMA["medications"])


def load_medication_requests(base_dir="data/raw/synthea") -> pd.DataFrame:
    return load_csv(_raw("medication_requests", base_dir), SCHEMA["medication_requests"])


def load_medication_administrations(base_dir="data/raw/synthea") -> pd.DataFrame:
    return load_csv(_raw("medication_administrations", base_dir), SCHEMA["medication_administrations"])


def load_conditions(base_dir="data/raw/synthea") -> pd.DataFrame:
    return load_csv(_raw("conditions", base_dir), SCHEMA["conditions"])


def load_allergies(base_dir="data/raw/synthea") -> pd.DataFrame:
    return load_csv(_raw("allergies", base_dir), SCHEMA["allergies"])


def load_primedrec_master(base_dir="data/raw/synthea") -> pd.DataFrame:
    return load_csv(_raw("primedrec_master", base_dir), SCHEMA["primedrec_master"])


def load_primedrec_risk_features(base_dir="data/raw/synthea") -> pd.DataFrame:
    return load_csv(_raw("primedrec_risk_features", base_dir), SCHEMA["primedrec_risk_features"])


def load_validation_report(base_dir="data/raw/synthea") -> pd.DataFrame:
    return load_csv(_raw("validation_report", base_dir), SCHEMA["validation_report"])
