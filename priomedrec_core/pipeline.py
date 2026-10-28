"""Deterministic orchestration used both locally and by PMR components."""
from __future__ import annotations

from typing import Any

from .contracts import AnalysisInput, AnalysisResult
from .priority import compute_priority


def _model_phase(features: dict[str, Any], encounter_id: str) -> dict[str, Any]:
    # Heavy ML/SHAP imports are lazy so circuit-breaker checks stay responsive.
    from src.explainability.shap_explainer import get_explanation
    from src.features.feature_pipeline import FEATURE_COLUMNS
    from src.models.predict import load_metadata, load_model, load_thresholds, predict_single
    model, thresholds, metadata = load_model(), load_thresholds(), load_metadata()
    prediction = predict_single(features, model, thresholds, metadata)
    columns = metadata.get("feature_columns", FEATURE_COLUMNS)
    import numpy as np
    explanation = get_explanation(model, np.array([features.get(c, 0) for c in columns]), columns,
                                  prediction["risk_probability"], prediction["priority"], encounter_id, top_n=5)
    return {"probability": prediction["risk_probability"], "tier_ml": prediction["priority"],
            "top_features": explanation.get("top_features", []), "model_version": prediction["model_version"],
            "threshold_version": thresholds.get("threshold_version", "unknown")}


def run_phase_a(payload: AnalysisInput | dict[str, Any]) -> dict[str, Any]:
    data = payload if isinstance(payload, AnalysisInput) else AnalysisInput.model_validate(payload)
    return _model_phase(data.features, data.encounter_id)


def run_phase_b(payload: AnalysisInput | dict[str, Any]) -> dict[str, Any]:
    """Run existing deterministic discrepancy engine without an HTTP/API dependency."""
    data = payload if isinstance(payload, AnalysisInput) else AnalysisInput.model_validate(payload)
    from src.rules.discrepancy_engine import run_all_rules
    import pandas as pd
    cols = ["medication_code", "medication_name", "dose_value", "dose_unit", "route", "frequency", "status"]
    pre = pd.DataFrame([m.model_dump() for m in data.pre_admission_meds], columns=cols)
    adm = pd.DataFrame([m.model_dump() for m in data.admission_meds], columns=cols)
    pre["admission_encounter_id"], adm["encounter_id"] = data.encounter_id, data.encounter_id
    raw = run_all_rules(data.patient_id, data.encounter_id, pre, adm)
    flags = [{**flag, "verification_required": True} for flag in raw.get("flags", [])]
    return {"findings": flags, "rule_version": raw.get("rule_version", "unknown"), "allergy_conflicts": [], "interactions": [], "safety_flags": []}


def run_full(payload: AnalysisInput | dict[str, Any]) -> AnalysisResult:
    data = payload if isinstance(payload, AnalysisInput) else AnalysisInput.model_validate(payload)
    phase_a, phase_b = run_phase_a(data), run_phase_b(data)
    priority = compute_priority(phase_a["probability"], phase_b["findings"], data.sla_hours_elapsed, data.sla_config, data.current_tier)
    return AnalysisResult(patient_id=data.patient_id, encounter_id=data.encounter_id, phase_a=phase_a, phase_b=phase_b,
                          priority=priority, versions={"model": phase_a["model_version"], "rules": phase_b["rule_version"]})
