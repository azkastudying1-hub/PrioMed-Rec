"""
api/services/prioritization_service.py
----------------------------------------
Business logic for the /prioritize endpoint.

Loads the trained model once at startup (lazy singleton), runs inference,
and attaches SHAP explanation. Returns a structured dict matching
PrioritizeResponse schema.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from src.models.predict import (
    load_model, load_thresholds, load_metadata, predict_single,
)
from src.explainability.shap_explainer import get_explanation
from src.features.feature_pipeline import FEATURE_COLUMNS


# ---------------------------------------------------------------------------
# Singleton loaders (loaded once, cached)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _model():
    return load_model()

@lru_cache(maxsize=1)
def _thresholds():
    return load_thresholds()

@lru_cache(maxsize=1)
def _metadata():
    return load_metadata()


# ---------------------------------------------------------------------------
# Service function
# ---------------------------------------------------------------------------

def prioritize(feature_dict: dict, encounter_id: str = "") -> dict:
    """
    Run prioritization for a single encounter.

    Parameters
    ----------
    feature_dict : dict mapping feature_name → value (validated by Pydantic)
    encounter_id : optional encounter identifier

    Returns
    -------
    dict matching PrioritizeResponse schema
    """
    model     = _model()
    thresholds = _thresholds()
    metadata  = _metadata()

    feature_cols = metadata.get("feature_columns", FEATURE_COLUMNS)

    # Prediction
    pred = predict_single(
        feature_dict=feature_dict,
        model=model,
        thresholds=thresholds,
        metadata=metadata,
    )

    risk_probability = pred["risk_probability"]
    priority         = pred["priority"]
    model_version    = pred["model_version"]

    # SHAP explanation
    feature_vector = np.array([feature_dict.get(c, 0) for c in feature_cols])
    explanation = get_explanation(
        model=model,
        feature_vector=feature_vector,
        feature_names=feature_cols,
        risk_probability=risk_probability,
        priority=priority,
        encounter_id=encounter_id,
        top_n=5,
    )

    threshold_version = thresholds.get("threshold_version", "thresholds-0.1.0")

    return {
        "risk_probability":  risk_probability,
        "priority":          priority,
        "model_version":     model_version,
        "threshold_version": threshold_version,
        "top_features":      explanation.get("top_features", []),
    }


def prioritize_batch(
    patient_ids: list[str] | None = None,
    limit: int = 50,
    priority_filter: str | None = None,
) -> dict:
    """
    Rank and prioritize a batch of patients/encounters.
    
    If patient_ids is None or empty, ranks top `limit` patients from the cohort dataset.
    Returns a dictionary matching BatchPrioritizeResponse schema.
    """
    import src.data.patient_resolver as pr
    pr._load_all()

    if not patient_ids:
        # Sample unique patient IDs up to limit
        p_ids = pr._cohort["patient_id"].drop_duplicates().head(limit).tolist()
    else:
        p_ids = patient_ids[:limit]

    results = []
    for pid in p_ids:
        try:
            ctx = pr.resolve_patient(pid)
            enc_meta = ctx["encounter_meta"]
            feat_dict = ctx["feature_vector"]

            prio = prioritize(feat_dict, encounter_id=ctx["encounter_id"])

            top_driver = "—"
            if prio.get("top_features"):
                inc_features = [f for f in prio["top_features"] if f.get("direction") == "increases_risk"]
                if inc_features:
                    top_driver = inc_features[0]["feature"].replace("_", " ").title()
                else:
                    top_driver = prio["top_features"][0]["feature"].replace("_", " ").title()

            results.append({
                "patient_id": pid,
                "encounter_id": ctx["encounter_id"],
                "discrepancy_likelihood": prio["risk_probability"],
                "review_priority": prio["priority"],
                "age": enc_meta.get("age"),
                "gender": enc_meta.get("gender"),
                "encounter_class": enc_meta.get("encounter_class"),
                "encounter_start": enc_meta.get("encounter_start"),
                "pre_admission_med_count": len(ctx.get("pre_admission_meds", [])),
                "admission_med_count": len(ctx.get("admission_meds", [])),
                "high_alert_count": feat_dict.get("high_alert_count", 0),
                "polypharmacy_flag": feat_dict.get("polypharmacy_flag", 0),
                "top_risk_driver": top_driver,
            })
        except Exception:
            continue

    # Sort descending by risk probability
    results.sort(key=lambda x: x["discrepancy_likelihood"], reverse=True)

    # Assign ranks
    for idx, item in enumerate(results, 1):
        item["rank"] = idx

    high_cnt = sum(1 for r in results if r["review_priority"] == "HIGH")
    med_cnt  = sum(1 for r in results if r["review_priority"] == "MEDIUM")
    low_cnt  = sum(1 for r in results if r["review_priority"] == "LOW")

    if priority_filter and priority_filter.upper() in ("HIGH", "MEDIUM", "LOW"):
        filtered_results = [r for r in results if r["review_priority"] == priority_filter.upper()]
    else:
        filtered_results = results

    return {
        "total_analyzed": len(results),
        "high_priority_count": high_cnt,
        "medium_priority_count": med_cnt,
        "low_priority_count": low_cnt,
        "ranked_patients": filtered_results,
    }

