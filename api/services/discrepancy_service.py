"""
api/services/discrepancy_service.py
-------------------------------------
Business logic for the /discrepancies endpoint.

Converts MedicationItem Pydantic objects into DataFrames, runs the rule engine,
and returns structured flags.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from src.rules.discrepancy_engine import run_all_rules


# ---------------------------------------------------------------------------
# Service function
# ---------------------------------------------------------------------------

def detect_discrepancies(
    patient_id: str,
    encounter_id: str,
    pre_admission_meds: List[dict],
    admission_meds: List[dict],
    config_path: str = "configs/discrepancy_rules.json",
) -> dict:
    """
    Run the rule engine for one encounter.

    Parameters
    ----------
    patient_id        : patient identifier
    encounter_id      : encounter identifier
    pre_admission_meds: list of medication dicts (from Pydantic .model_dump())
    admission_meds    : list of medication dicts
    config_path       : path to discrepancy_rules.json

    Returns
    -------
    dict matching DiscrepancyResponse schema
    """
    # Build DataFrames
    _pre_cols = ["medication_code", "medication_name", "dose_value",
                 "dose_unit", "route", "frequency", "status"]
    _adm_cols = ["medication_code", "medication_name", "dose_value",
                 "dose_unit", "route", "frequency", "status"]

    pre_df = pd.DataFrame(pre_admission_meds, columns=_pre_cols) \
        if pre_admission_meds \
        else pd.DataFrame(columns=_pre_cols)

    adm_df = pd.DataFrame(admission_meds, columns=_adm_cols) \
        if admission_meds \
        else pd.DataFrame(columns=_adm_cols)

    # Add required columns for rule engine
    pre_df["admission_encounter_id"] = encounter_id
    adm_df["encounter_id"]           = encounter_id

    # Run rule engine
    result = run_all_rules(patient_id, encounter_id, pre_df, adm_df, config_path)

    # Extract rule_version
    import json
    try:
        with open(config_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        rule_version = cfg.get("rule_version", "rules-0.1.0")
    except Exception:  # noqa: BLE001
        rule_version = "rules-0.1.0"

    # Normalise flags to match DiscrepancyFlag schema
    flags = []
    for flag in result.get("flags", []):
        flags.append({
            "flag_type":             flag.get("flag_type", "UNKNOWN"),
            "severity":              flag.get("severity", "REVIEW"),
            "medication_code":       flag.get("medication_code"),
            "medication_name":       flag.get("medication_name"),
            "evidence":              flag.get("evidence", ""),
            "verification_required": True,
            "rule_id":               flag.get("rule_id", ""),
        })

    return {
        "patient_id":   patient_id,
        "encounter_id": encounter_id,
        "rule_version": rule_version,
        "flags":        flags,
    }
