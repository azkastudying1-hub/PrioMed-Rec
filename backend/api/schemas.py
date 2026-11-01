"""
api/schemas.py
---------------
Pydantic request / response schemas for all PrioMed-Rec endpoints.

Input validation rules (plan §762-§768):
  - age < 0          → 422 Unprocessable Entity
  - any count < 0    → 422 Unprocessable Entity
  - priority         → only LOW / MEDIUM / HIGH allowed in responses

Clinical safety:
  - All responses carry model_version and rule_version.
  - No autonomous clinical instruction appears in any response field.
  - verification_required is always True when discrepancy flags are present.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------

class PriorityEnum(str):
    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status:        str
    model_version: str
    rule_version:  str
    api_version:   str
    db_status:     Optional[str] = None
    uptime_seconds: Optional[float] = None


# ---------------------------------------------------------------------------
# POST /prioritize
# ---------------------------------------------------------------------------

class PrioritizeRequest(BaseModel):
    """
    Expert-mode prioritization request — supply SAFE_FEATURES only.

    FORBIDDEN features (label-adjacent, features-0.3.0):
    pre_admission_medication_count, admission_medication_count,
    total_medication_count, new_medication_count,
    discontinued_medication_count, potential_duplicate_candidates.

    These fields are accepted in the schema for backward-compatibility
    but MUST NOT be set to non-zero values. The service will reject them.
    Prefer POST /analyze with patient_id (simple mode).
    """
    # ── SAFE_FEATURES (10) — leakage-free ────────────────────────────────
    age:                    float = Field(..., ge=0, description="Patient age in years")
    age_65_plus:            int   = Field(0,  ge=0, le=1)
    gender_encoded:         int   = Field(0,  ge=0, le=1)
    polypharmacy_flag:      int   = Field(0,  ge=0, le=1)
    high_alert_flag:        int   = Field(0,  ge=0, le=1)
    high_alert_count:       int   = Field(0,  ge=0)
    active_condition_count: int   = Field(0,  ge=0)
    prior_encounter_count:  int   = Field(0,  ge=0)
    allergy_count:          int   = Field(0,  ge=0)
    has_drug_allergy:       int   = Field(0,  ge=0, le=1)

    # ── FORBIDDEN_FEATURES — accepted for backward-compat but rejected if non-zero ──
    pre_admission_medication_count: int = Field(
        0, ge=0,
        description="FORBIDDEN (features-0.3.0): label-adjacent. Must be 0. Prefer /analyze."
    )
    admission_medication_count: int = Field(
        0, ge=0,
        description="FORBIDDEN (features-0.3.0): label-adjacent. Must be 0. Prefer /analyze."
    )
    total_medication_count: int = Field(
        0, ge=0,
        description="FORBIDDEN (features-0.3.0): label-adjacent. Must be 0. Prefer /analyze."
    )
    new_medication_count: int = Field(
        0, ge=0,
        description="FORBIDDEN (features-0.3.0): label-adjacent. Must be 0. Prefer /analyze."
    )
    discontinued_medication_count: int = Field(
        0, ge=0,
        description="FORBIDDEN (features-0.3.0): mirrors OMISSION label logic — leakage. Must be 0."
    )
    potential_duplicate_candidates: int = Field(
        0, ge=0,
        description="FORBIDDEN (features-0.3.0): mirrors DUPLICATION label logic — leakage. Must be 0."
    )


class TopFeature(BaseModel):
    feature:    str
    value:      float
    shap_value: float
    direction:  str


class PrioritizeResponse(BaseModel):
    risk_probability:  float
    priority:          str
    model_version:     str
    threshold_version: str
    top_features:      List[TopFeature] = []


# ---------------------------------------------------------------------------
# POST /discrepancies
# ---------------------------------------------------------------------------

class MedicationItem(BaseModel):
    medication_code: Optional[str] = None
    medication_name: Optional[str] = None
    dose_value:      Optional[float] = None
    dose_unit:       Optional[str] = None
    route:           Optional[str] = None
    frequency:       Optional[str] = None
    status:          Optional[str] = None


class DiscrepancyRequest(BaseModel):
    patient_id:        str
    encounter_id:      str
    pre_admission_meds: List[MedicationItem] = []
    admission_meds:    List[MedicationItem] = []


class DiscrepancyFlag(BaseModel):
    flag_type:             str
    severity:              str
    medication_code:       Optional[str] = None
    medication_name:       Optional[str] = None
    evidence:              str
    verification_required: bool = True
    rule_id:               str


class DiscrepancyResponse(BaseModel):
    patient_id:   str
    encounter_id: str
    rule_version: str
    flags:        List[DiscrepancyFlag] = []


# ---------------------------------------------------------------------------
# POST /review
# ---------------------------------------------------------------------------

class ReviewRequest(BaseModel):
    case_id:        str
    pharmacist_id:  str
    ai_result:      dict
    action:         str = Field(..., description="APPROVE | REJECT | EDIT")
    pharmacist_note: Optional[str] = ""
    edited_result:  Optional[dict] = None
    # Optional version context — supplied by Streamlit/Langflow for full audit trail
    model_version:  Optional[str] = None
    rule_version:   Optional[str] = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"APPROVE", "REJECT", "EDIT"}
        if v.upper() not in allowed:
            raise ValueError(f"action must be one of {allowed}, got '{v}'")
        return v.upper()


class ReviewResponse(BaseModel):
    review_id:     str
    case_id:       str
    action:        str
    timestamp:     str
    pharmacist_id: str
    model_version: Optional[str] = None
    rule_version:  Optional[str] = None
    final_result:  dict


# ---------------------------------------------------------------------------
# POST /prioritize/batch (Cohort / Multi-patient ranking)
# ---------------------------------------------------------------------------

class RankedPatientItem(BaseModel):
    rank:                   int
    patient_id:             str
    encounter_id:           str
    discrepancy_likelihood: float
    review_priority:        str
    age:                    Optional[float] = None
    gender:                 Optional[str] = None
    encounter_class:        Optional[str] = None
    encounter_start:        Optional[str] = None
    pre_admission_med_count: int = 0
    admission_med_count:     int = 0
    high_alert_count:        int = 0
    polypharmacy_flag:       int = 0
    top_risk_driver:         str = "—"


class BatchPrioritizeRequest(BaseModel):
    patient_ids:     Optional[List[str]] = Field(None, description="List of patient IDs to rank. If empty, ranks cohort sample.")
    limit:           int = Field(50, ge=1, le=500, description="Max patients to return (1-500)")
    priority_filter: Optional[str] = Field(None, description="Optional filter: HIGH, MEDIUM, LOW, or ALL")


class BatchPrioritizeResponse(BaseModel):
    total_analyzed:        int
    high_priority_count:   int
    medium_priority_count: int
    low_priority_count:    int
    ranked_patients:       List[RankedPatientItem]

