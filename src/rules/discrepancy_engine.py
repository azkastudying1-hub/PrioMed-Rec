"""
src/rules/discrepancy_engine.py
---------------------------------
Deterministic, configuration-driven medication discrepancy detection engine.

Design principles (PROJECT_CONTEXT §13, §14):
  - Config-driven: all rule parameters come from configs/discrepancy_rules.json
  - Deterministic: same input → identical output every run
  - Transparent: every flag carries evidence + rule_id
  - Safe: UNRESOLVED_MEDICATION_MATCH is raised rather than silently skipping
  - verification_required: true on every flag (pharmacist must confirm)

Output contract matches PROJECT_CONTEXT §14.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.rules.medication_normalizer import (
    UNRESOLVED_FLAG,
    build_medication_index,
    normalize_medication,
)

DEFAULT_CONFIG_PATH = "configs/discrepancy_rules.json"


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_rule_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    with open(config_path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Individual rule functions
# ---------------------------------------------------------------------------

def _flag(
    flag_type: str,
    medication_code: str,
    medication_name: str,
    rule_version: str,
    pre_detail: dict | None,
    adm_detail: dict | None,
    evidence: str,
) -> dict:
    """Construct a standardised flag dict (PROJECT_CONTEXT §14 contract)."""
    return {
        "flag_type": flag_type,
        "severity": "REVIEW",
        "medication_code": medication_code,
        "medication_name": medication_name,
        "pre_admission_detail": pre_detail,
        "admission_detail": adm_detail,
        "evidence": evidence,
        "verification_required": True,
        "rule_id": f"{flag_type.lower()}.{rule_version}",
    }


def check_omission(
    pre_meds: pd.DataFrame,
    adm_meds: pd.DataFrame,
    rule_cfg: dict,
    rule_version: str,
) -> list[dict]:
    """
    POTENTIAL_OMISSION: medication present in pre-admission list but
    absent from the admission list (by norm_key).

    Respects `require_active_status` config.
    """
    if not rule_cfg.get("enabled", True):
        return []

    flags = []
    pre = pre_meds.copy()
    adm = adm_meds.copy()

    if rule_cfg.get("require_active_status", True):
        pre = pre[~pre.get("status", pd.Series(dtype=str)).isin(["completed", "stopped"])]

    # Build identity keys
    pre = build_medication_index(pre)
    adm = build_medication_index(adm)

    adm_keys = set(adm["norm_key"].unique())

    for _, row in pre.iterrows():
        key = row["norm_key"]
        if key == UNRESOLVED_FLAG:
            flags.append(_flag(
                "UNRESOLVED_MEDICATION_MATCH",
                row.get("medication_code", ""),
                row.get("medication_name", ""),
                rule_version,
                {"status": row.get("status", "")},
                None,
                "Pre-admission medication could not be normalised safely.",
            ))
            continue
        if key not in adm_keys:
            flags.append(_flag(
                "POTENTIAL_OMISSION",
                row.get("medication_code", ""),
                row.get("medication_name", ""),
                rule_version,
                {"dose_value": row.get("dose_value"), "route": row.get("route"),
                 "frequency": row.get("frequency"), "status": row.get("status")},
                None,
                "Medication present in pre-admission list but absent from admission list.",
            ))
    return flags


def check_duplication(
    adm_meds: pd.DataFrame,
    rule_cfg: dict,
    rule_version: str,
) -> list[dict]:
    """
    POTENTIAL_DUPLICATION: same medication appears more than once in
    the admission list (by norm_key).
    """
    if not rule_cfg.get("enabled", True):
        return []

    adm = build_medication_index(adm_meds)
    flags = []

    counts = adm.groupby("norm_key").size()
    dup_keys = set(counts[counts > 1].index)

    for key in dup_keys:
        if key == UNRESOLVED_FLAG:
            continue
        rows = adm[adm["norm_key"] == key]
        row = rows.iloc[0]
        flags.append(_flag(
            "POTENTIAL_DUPLICATION",
            row.get("medication_code", ""),
            row.get("medication_name", ""),
            rule_version,
            None,
            {"occurrence_count": int(counts[key])},
            f"Medication appears {int(counts[key])} times in admission list.",
        ))
    return flags


def check_dose_mismatch(
    pre_meds: pd.DataFrame,
    adm_meds: pd.DataFrame,
    rule_cfg: dict,
    rule_version: str,
) -> list[dict]:
    """
    POTENTIAL_DOSE_MISMATCH: same medication in both lists but different
    dose_value. Disabled if data is unavailable (DQI-005).
    """
    if not rule_cfg.get("enabled", True):
        return []  # Disabled — dose_value 100% null (DQI-005)

    pre = build_medication_index(pre_meds)
    adm = build_medication_index(adm_meds)
    tolerance = rule_cfg.get("tolerance_pct", 0) / 100.0
    flags = []

    adm_by_key = {row["norm_key"]: row for _, row in adm.iterrows()
                  if row["norm_key"] != UNRESOLVED_FLAG}

    for _, row in pre.iterrows():
        key = row["norm_key"]
        if key == UNRESOLVED_FLAG or key not in adm_by_key:
            continue
        pre_dose = row.get("dose_value")
        adm_dose = adm_by_key[key].get("dose_value")
        if pd.isna(pre_dose) or pd.isna(adm_dose):
            continue
        try:
            pre_val, adm_val = float(pre_dose), float(adm_dose)
        except (ValueError, TypeError):
            continue
        if adm_val == 0:
            continue
        diff_pct = abs(pre_val - adm_val) / adm_val
        if diff_pct > tolerance:
            flags.append(_flag(
                "POTENTIAL_DOSE_MISMATCH",
                row.get("medication_code", ""),
                row.get("medication_name", ""),
                rule_version,
                {"dose_value": pre_val},
                {"dose_value": adm_val},
                f"Dose changed from {pre_val} to {adm_val} ({diff_pct*100:.1f}% difference).",
            ))
    return flags


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_all_rules(
    patient_id: str,
    encounter_id: str,
    pre_meds: pd.DataFrame,
    adm_meds: pd.DataFrame,
    config_path: str = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    """
    Run all enabled rules and return the full discrepancy output contract.

    Parameters
    ----------
    patient_id, encounter_id : identifiers
    pre_meds  : pre-admission medications for this encounter
    adm_meds  : admission medications for this encounter
    config_path : path to discrepancy_rules.json

    Returns
    -------
    dict matching PROJECT_CONTEXT §14 output contract.
    """
    cfg = load_rule_config(config_path)
    rule_version = cfg.get("rule_version", "rules-0.1.0")
    rules = cfg.get("rules", {})

    flags = []
    flags += check_omission(pre_meds, adm_meds, rules.get("omission", {}), rule_version)
    flags += check_duplication(adm_meds, rules.get("duplication", {}), rule_version)
    flags += check_dose_mismatch(pre_meds, adm_meds, rules.get("dose_mismatch", {}), rule_version)
    # frequency_mismatch and route_mismatch disabled (DQI-005)

    return {
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "rule_version": rule_version,
        "flags": flags,
    }
