"""
api/routes/patient.py
-----------------------
GET /patient/{patient_id}
GET /patients/sample

Returns structured patient/encounter context for a known patient.
Used by Streamlit and Langflow to resolve patient_id before calling /analyze.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class EncounterSummary(BaseModel):
    encounter_id:    str
    encounter_start: str
    encounter_end:   str
    encounter_class: str
    encounter_type:  str
    age:             Optional[float] = None
    gender:          str


class PatientResponse(BaseModel):
    patient_id:       str
    encounter_count:  int
    encounters:       List[EncounterSummary]
    latest_admission: Optional[EncounterSummary] = None


class SamplePatientsResponse(BaseModel):
    patient_ids: List[str]
    count:       int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/patient/{patient_id}",
    response_model=PatientResponse,
    tags=["patient"],
    summary="Get patient admission encounters",
)
def get_patient(patient_id: str) -> PatientResponse:
    """
    Return all admission encounters for a given patient_id.

    Used by Streamlit / Langflow to:
    1. Verify the patient exists in the dataset
    2. List available encounters for the patient
    3. Resolve the latest admission encounter_id before calling /analyze

    The patient_id format matches the Synthea dataset
    (e.g. UUID-style string from patients.csv).
    """
    try:
        from api.services.patient_service import get_patient_encounters_summary
        result = get_patient_encounters_summary(patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Patient lookup error: {exc}",
        ) from exc

    encounters = [EncounterSummary(**e) for e in result["encounters"]]
    latest = EncounterSummary(**result["latest_admission"]) if result["latest_admission"] else None

    return PatientResponse(
        patient_id=result["patient_id"],
        encounter_count=result["encounter_count"],
        encounters=encounters,
        latest_admission=latest,
    )


@router.get(
    "/patients/sample",
    response_model=SamplePatientsResponse,
    tags=["patient"],
    summary="Get sample patient IDs (for demo/testing)",
)
def get_sample_patients(limit: int = 10) -> SamplePatientsResponse:
    """
    Return a list of sample patient_ids from the dataset.
    Useful for demo and Streamlit autocomplete.
    """
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    try:
        from api.services.patient_service import list_sample_patients
        ids = list_sample_patients(limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Error: {exc}") from exc
    return SamplePatientsResponse(patient_ids=ids, count=len(ids))
