"""Pydantic contracts for deterministic PrioMed-Rec orchestration."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Medication(BaseModel):
    medication_code: str | None = None
    medication_name: str = ""
    dose_value: float | None = None
    dose_unit: str | None = None
    route: str | None = None
    frequency: str | None = None
    status: str | None = None


class AnalysisInput(BaseModel):
    """Validated, synthetic-only input for the deterministic analysis path."""

    patient_id: str = "SYNTHETIC-UNKNOWN"
    encounter_id: str = ""
    features: dict[str, Any] = Field(default_factory=dict)
    pre_admission_meds: list[Medication] = Field(default_factory=list)
    admission_meds: list[Medication] = Field(default_factory=list)
    allergies: list[dict[str, Any]] = Field(default_factory=list)
    sla_hours_elapsed: float | None = None
    sla_config: dict[str, Any] | None = None
    current_tier: str | None = None


class AnalysisResult(BaseModel):
    patient_id: str
    encounter_id: str
    phase_a: dict[str, Any]
    phase_b: dict[str, Any]
    priority: dict[str, Any]
    versions: dict[str, str]
    safety_notice: str = "Dukungan keputusan saja — wajib diverifikasi apoteker."
