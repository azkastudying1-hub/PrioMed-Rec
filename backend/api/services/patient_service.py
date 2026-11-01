"""
api/services/patient_service.py
---------------------------------
Service layer for patient data retrieval and feature construction.
Bridges the API layer to src/data/patient_resolver.py.

Called by:
  - api/routes/patient.py   → GET /patient/{patient_id}
  - api/routes/analyze.py   → POST /analyze (patient_id-driven)
"""

from __future__ import annotations

from typing import Optional

from src.data.patient_resolver import (
    resolve_patient,
    get_patient_encounters,
    list_known_patients,
)


def get_patient_context(
    patient_id: str,
    encounter_id: Optional[str] = None,
) -> dict:
    """
    Resolve patient + encounter → structured context dict.

    Returns the full context including feature_vector, medication lists,
    and encounter metadata. Raises ValueError if not found.
    """
    return resolve_patient(patient_id, encounter_id)


def get_patient_encounters_summary(patient_id: str) -> dict:
    """
    Return a summary of all admission encounters for a patient.
    Used by GET /patient/{patient_id}.
    """
    encounters = get_patient_encounters(patient_id)
    if not encounters:
        raise ValueError(f"Patient '{patient_id}' not found.")

    latest = encounters[0] if encounters else None
    return {
        "patient_id":       patient_id,
        "encounter_count":  len(encounters),
        "encounters":       encounters,
        "latest_admission": latest,
    }


def list_sample_patients(limit: int = 20) -> list[str]:
    """Return sample patient_ids for demo/testing."""
    return list_known_patients(limit)
