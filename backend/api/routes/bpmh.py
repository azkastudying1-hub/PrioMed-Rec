from __future__ import annotations

"""
api/routes/bpmh.py
-------------------
POST /bpmh/{patient_id}  — save BPMH form (medication list + dispositions)
GET  /bpmh/{patient_id}  — retrieve saved BPMH for a patient

BPMH = Best Possible Medication History (riwayat obat terbaik sebelum admisi).
This endpoint completes Tahap 2 of the two-stage workflow:
  Tahap 1 (Triase, ML scoring) → Tahap 2 (Rekonsiliasi, after BPMH)

Clinical safety:
  - Saving BPMH changes patient status to BPMH_TERISI (ready for analysis)
  - Dispositions are stored verbatim — system never infers or changes them
  - No ML or rule engine runs here; /analyze must be called separately after BPMH
"""


import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

# In-memory fallback store (used when DB is unavailable)
_bpmh_store: dict[str, dict] = {}

# Import database helpers — graceful fallback to in-memory if DB not available
try:
    from api.database import save_bpmh as _db_save_bpmh, get_bpmh as _db_get_bpmh
    _USE_DB = True
except Exception:  # noqa: BLE001
    _USE_DB = False
    _db_save_bpmh = None  # type: ignore[assignment]
    _db_get_bpmh = None   # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BPMHMedItem(BaseModel):
    """One medication entry in the BPMH form."""
    medication_name:    str   = Field(..., description="Drug name (free text, will be normalized)")
    dose:               Optional[str] = None
    unit:               Optional[str] = None
    frequency:          Optional[str] = None
    route:              Optional[str] = None
    source:             Optional[str] = Field(None, description="Pasien / Keluarga / Resep / Apotek")
    last_taken:         Optional[str] = None
    disposition:        Optional[str] = Field(
        None,
        description="DILANJUTKAN | DITUNDA | DIGANTI | DIHENTIKAN — required when a decision is made"
    )
    disposition_reason: Optional[str] = None
    indication_note:    Optional[str] = Field(
        None,
        description="Filled by pharmacist — NOT used by system to assess clinical appropriateness"
    )


class BPMHRequest(BaseModel):
    patient_id:   str
    encounter_id: str
    pharmacist_id: Optional[str] = Field(None, description="Pharmacist identifier for audit trail")
    source_notes: Optional[str] = Field(None, description="e.g. 'wawancara keluarga + kemasan fisik'")
    medications:  List[BPMHMedItem] = Field(..., min_length=1)


class BPMHResponse(BaseModel):
    patient_id:      str
    encounter_id:    str
    status:          str   = Field(description="BPMH_TERISI after successful save")
    medication_count: int
    saved_at:        str
    pharmacist_id:   Optional[str] = None
    message:         str


class BPMHGetResponse(BaseModel):
    patient_id:      str
    encounter_id:    str
    status:          str
    medication_count: int
    saved_at:        Optional[str]
    medications:     List[BPMHMedItem]
    source_notes:    Optional[str]
    pharmacist_id:   Optional[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/bpmh/{patient_id}",
    response_model=BPMHResponse,
    tags=["bpmh"],
    summary="Save BPMH form for a patient (Tahap 2)",
)
def save_bpmh(patient_id: str, request: BPMHRequest) -> BPMHResponse:
    """
    Save the Best Possible Medication History for a patient.

    This endpoint marks the transition from Tahap 1 (triase, ML scoring only)
    to Tahap 2 (rekonsiliasi, after BPMH collected). After saving BPMH, call
    POST /analyze with patient_id to run the rule engine and generate SBAR.

    Medications with a documented disposition are stored as-is.
    The system NEVER infers or changes dispositions — pharmacist judgement only.
    """
    if request.patient_id != patient_id:
        raise HTTPException(
            status_code=422,
            detail=f"patient_id in URL ({patient_id}) must match body ({request.patient_id})"
        )

    if not request.medications:
        raise HTTPException(status_code=422, detail="At least one medication is required.")

    saved_at = datetime.now(timezone.utc).isoformat()

    record = {
        "patient_id":      patient_id,
        "encounter_id":    request.encounter_id,
        "status":          "BPMH_TERISI",
        "medication_count": len(request.medications),
        "saved_at":        saved_at,
        "pharmacist_id":   request.pharmacist_id,
        "source_notes":    request.source_notes,
        "medications":     [m.model_dump() for m in request.medications],
    }
    if _USE_DB:
        try:
            _db_save_bpmh(
                patient_id=patient_id,
                encounter_id=request.encounter_id,
                pharmacist_id=request.pharmacist_id,
                source_notes=request.source_notes,
                medications=[m.model_dump() for m in request.medications],
                saved_at=saved_at,
            )
        except Exception as db_exc:
            print(f"[bpmh] DB save warning: {db_exc}")

    _bpmh_store[patient_id] = record

    return BPMHResponse(
        patient_id=patient_id,
        encounter_id=request.encounter_id,
        status="BPMH_TERISI",
        medication_count=len(request.medications),
        saved_at=saved_at,
        pharmacist_id=request.pharmacist_id,
        message=(
            f"BPMH saved: {len(request.medications)} medication(s). "
            "Call POST /analyze with patient_id to run rule engine analysis."
        ),
    )


@router.get(
    "/bpmh/{patient_id}",
    response_model=BPMHGetResponse,
    tags=["bpmh"],
    summary="Retrieve saved BPMH for a patient",
)
def get_bpmh(patient_id: str) -> BPMHGetResponse:
    """
    Retrieve the last saved BPMH for a patient.
    Returns 404 if no BPMH has been saved yet.
    """
    if _USE_DB:
        try:
            db_record = _db_get_bpmh(patient_id)
            if db_record:
                return BPMHGetResponse(
                    patient_id=db_record["patient_id"],
                    encounter_id=db_record["encounter_id"],
                    status="BPMH_TERISI",
                    medication_count=len(db_record["medications"]),
                    saved_at=db_record.get("saved_at"),
                    medications=[BPMHMedItem(**m) for m in db_record["medications"]],
                    source_notes=db_record.get("source_notes"),
                    pharmacist_id=db_record.get("pharmacist_id"),
                )
        except Exception as db_exc:
            print(f"[bpmh] DB read warning: {db_exc}")
    record = _bpmh_store.get(patient_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No BPMH found for patient_id '{patient_id}'. Use POST /bpmh/{patient_id} to save."
        )

    return BPMHGetResponse(
        patient_id=record["patient_id"],
        encounter_id=record["encounter_id"],
        status=record["status"],
        medication_count=record["medication_count"],
        saved_at=record.get("saved_at"),
        medications=[BPMHMedItem(**m) for m in record["medications"]],
        source_notes=record.get("source_notes"),
        pharmacist_id=record.get("pharmacist_id"),
    )