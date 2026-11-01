"""
api/routes/discrepancy.py
---------------------------
POST /discrepancies — medication discrepancy detection (rule engine).

Input  : DiscrepancyRequest (patient_id, encounter_id, pre/admission meds)
Output : DiscrepancyResponse (rule_version, flags[])

Clinical safety:
  - verification_required is always True in every flag.
  - Rule engine failure returns 503, never "no discrepancies found" silently.
  - Pharmacist must review all flags.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import DiscrepancyRequest, DiscrepancyResponse

router = APIRouter()


@router.post("/discrepancies", response_model=DiscrepancyResponse, tags=["discrepancy"])
def detect_discrepancies(request: DiscrepancyRequest) -> DiscrepancyResponse:
    """
    Run the medication discrepancy detection rule engine for one encounter.

    Returns a list of structured flags (POTENTIAL_OMISSION, POTENTIAL_DUPLICATION,
    POTENTIAL_DOSE_MISMATCH, UNRESOLVED_MEDICATION_MATCH).
    Each flag carries verification_required=True.
    """
    try:
        from api.services.discrepancy_service import detect_discrepancies as _detect
        result = _detect(
            patient_id=request.patient_id,
            encounter_id=request.encounter_id,
            pre_admission_meds=[m.model_dump() for m in request.pre_admission_meds],
            admission_meds=[m.model_dump() for m in request.admission_meds],
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Rule config not found: {exc}. Cannot run discrepancy detection.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"Discrepancy service error: {exc}",
        ) from exc

    return DiscrepancyResponse(**result)
