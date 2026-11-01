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

Disposition-aware omission (Project Foundation v2 §6.3):
  Rule engine receives a `dispositions` dict keyed by medication_code.
  A home medication is NEVER flagged for omission if it has a documented
  disposition (DILANJUTKAN / DITUNDA / DIGANTI / DIHENTIKAN).
  Only undocumented omissions — absent from admission list AND no recorded
  disposition — become POTENTIAL_UNDOCUMENTED_OMISSION candidates.
  If a same-class substitute is found in the admission list, the flag type
  is downgraded to POSSIBLE_SUBSTITUTION instead.

  See tests/test_rules_disposition.py for the full behavioural specification.

Output contract matches PROJECT_CONTEXT §14.
"""

from __future__ import annotations

import json
import math
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
# Helpers
# ---------------------------------------------------------------------------

def _safe_str(value: Any) -> str:
    """Coerce a value (including None/NaN) to a stripped string."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def _has_disposition(value: Any) -> bool:
    """Return True only for a non-empty, non-NaN string."""
    return bool(_safe_str(value))


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
    dispositions: dict[str, str] | None = None,
    drug_class_map: dict[str, str] | None = None,
) -> list[dict]:
    """
    Disposition-aware omission check (Project Foundation v2 §6.3).

    For each medication in the pre-admission list:
      1. If the medication has a documented disposition → skip (no flag).
      2. If identity is unresolvable (null code AND null name) → UNRESOLVED_MEDICATION_MATCH.
      3. If medication is already present in the admission list → skip (no flag).
      4. If a same-class therapeutic substitute exists in the admission list →
         POSSIBLE_SUBSTITUTION.
      5. Otherwise → POTENTIAL_UNDOCUMENTED_OMISSION.

    Parameters
    ----------
    pre_meds       : pre-admission medication DataFrame
    adm_meds       : admission medication DataFrame
    rule_cfg       : the "omission" sub-config from discrepancy_rules.json
    rule_version   : version string from config
    dispositions   : optional dict mapping medication_code → disposition string.
                     Also checked against the DataFrame's own "disposition" column.
    drug_class_map : optional dict mapping medication_code or normalised name
                     → therapeutic class string (for POSSIBLE_SUBSTITUTION logic).

    Legacy behaviour (dispositions=None, drug_class_map=None):
      Falls back to the old POTENTIAL_OMISSION flag type so existing tests and
      callers that do not pass dispositions continue to work unchanged.
    """
    if not rule_cfg.get("enabled", True):
        return []

    dispositions = dispositions or {}
    drug_class_map = drug_class_map or {}

    flags: list[dict] = []
    pre = pre_meds.copy()
    adm = adm_meds.copy()

    if rule_cfg.get("require_active_status", True):
        status_col = pre.get("status") if isinstance(pre, pd.DataFrame) else None
        if status_col is not None:
            pre = pre[~pre["status"].isin(["completed", "stopped"])]

    # Build identity keys for the admission list (for presence check)
    adm_indexed = build_medication_index(adm) if not adm.empty else adm
    adm_codes: set[str] = set()
    adm_norm_names: set[str] = set()
    if not adm_indexed.empty:
        adm_codes = set(adm_indexed["norm_key"].dropna().astype(str).tolist())
        if "medication_code" in adm_indexed.columns:
            adm_codes |= set(
                adm_indexed["medication_code"].dropna().astype(str).str.strip().tolist()
            )
        if "medication_name_normalized" in adm_indexed.columns:
            adm_norm_names = set(
                adm_indexed["medication_name_normalized"].dropna().astype(str).str.strip().tolist()
            )

    # Build admission therapeutic classes for substitution check
    adm_classes: set[str] = set()
    if drug_class_map:
        for k in adm_codes | adm_norm_names:
            cls = drug_class_map.get(k)
            if cls:
                adm_classes.add(cls)

    # Disposition-aware mode: uses new flag types
    disposition_mode = bool(
        dispositions or
        ("disposition" in pre.columns and pre["disposition"].notna().any())
    )

    pre_indexed = build_medication_index(pre) if not pre.empty else pre

    for _, row in (pre_indexed.iterrows() if not pre_indexed.empty else []):
        # --- Disposition check (column-level and dict-level) ---
        col_disposition = row.get("disposition") if "disposition" in row.index else None
        code_str = _safe_str(row.get("medication_code", ""))
        dict_disposition = dispositions.get(code_str) if code_str else None
        effective_disposition = col_disposition if _has_disposition(col_disposition) else dict_disposition

        if _has_disposition(effective_disposition):
            # Has documented disposition — never flag (§6.3 principle 1)
            continue

        # --- Identity resolution ---
        norm_key = row.get("norm_key", UNRESOLVED_FLAG)
        med_name_norm = _safe_str(
            row.get("medication_name_normalized", "") or row.get("medication_name", "")
        ).lower()
        display_name = _safe_str(row.get("medication_name", "")) or med_name_norm

        if norm_key == UNRESOLVED_FLAG and not code_str and not med_name_norm:
            flags.append(_flag(
                "UNRESOLVED_MEDICATION_MATCH",
                code_str,
                display_name,
                rule_version,
                {"status": _safe_str(row.get("status", ""))},
                None,
                "Pre-admission medication could not be normalised safely.",
            ))
            continue

        # --- Presence check (already in admission list) ---
        identity_key = code_str if code_str else med_name_norm
        if (
            norm_key != UNRESOLVED_FLAG and norm_key in adm_codes
            or code_str in adm_codes
            or med_name_norm in adm_norm_names
        ):
            continue

        if not disposition_mode:
            # Legacy path — old callers without disposition support
            flags.append(_flag(
                "POTENTIAL_OMISSION",
                code_str,
                display_name,
                rule_version,
                {"dose_value": row.get("dose_value"), "route": row.get("route"),
                 "frequency": row.get("frequency"), "status": row.get("status")},
                None,
                "Medication present in pre-admission list but absent from admission list.",
            ))
            continue

        # --- Therapeutic class substitution check ---
        home_class = drug_class_map.get(identity_key) or drug_class_map.get(med_name_norm)
        if home_class and home_class in adm_classes:
            flags.append(_flag(
                "POSSIBLE_SUBSTITUTION",
                code_str,
                display_name,
                rule_version,
                {"dose_value": row.get("dose_value"), "route": row.get("route"),
                 "status": row.get("status")},
                None,
                (
                    f"Home medication absent from admission list but a same-class "
                    f"({home_class}) substitute may be present. Pharmacist verification required."
                ),
            ))
        else:
            flags.append(_flag(
                "POTENTIAL_UNDOCUMENTED_OMISSION",
                code_str,
                display_name,
                rule_version,
                {"dose_value": row.get("dose_value"), "route": row.get("route"),
                 "frequency": row.get("frequency"), "status": row.get("status")},
                None,
                (
                    "Medication present in pre-admission list but absent from "
                    "admission list with no documented disposition."
                ),
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
    dispositions: dict[str, str] | None = None,
    drug_class_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Run all enabled rules and return the full discrepancy output contract.

    Parameters
    ----------
    patient_id, encounter_id : identifiers
    pre_meds      : pre-admission medications for this encounter
    adm_meds      : admission medications for this encounter
    config_path   : path to discrepancy_rules.json
    dispositions  : optional dict {medication_code: disposition_string}.
                    Enables disposition-aware omission logic (§6.3).
                    When provided, POTENTIAL_UNDOCUMENTED_OMISSION and
                    POSSIBLE_SUBSTITUTION are used instead of POTENTIAL_OMISSION.
    drug_class_map: optional dict {medication_code_or_name: class_string}.
                    Used for POSSIBLE_SUBSTITUTION detection.

    Returns
    -------
    dict matching PROJECT_CONTEXT §14 output contract.
    """
    # Auto-load drug_class_map from configs/ if not provided
    if drug_class_map is None:
        try:
            import json as _json
            from pathlib import Path as _Path
            _map_path = _Path(__file__).parent.parent.parent / "configs" / "drug_class_map.json"
            if _map_path.exists():
                with open(_map_path, encoding="utf-8") as _fh:
                    drug_class_map = _json.load(_fh)
        except Exception as _exc:
            print(f"[discrepancy_engine] Warning: could not load drug_class_map.json: {_exc}")
            drug_class_map = {}

    cfg = load_rule_config(config_path)
    rule_version = cfg.get("rule_version", "rules-0.1.0")
    rules = cfg.get("rules", {})

    flags = []
    flags += check_omission(
        pre_meds, adm_meds,
        rules.get("omission", {}), rule_version,
        dispositions=dispositions,
        drug_class_map=drug_class_map,
    )
    flags += check_duplication(adm_meds, rules.get("duplication", {}), rule_version)
    flags += check_dose_mismatch(pre_meds, adm_meds, rules.get("dose_mismatch", {}), rule_version)
    # frequency_mismatch and route_mismatch disabled (DQI-005)

    return {
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "rule_version": rule_version,
        "flags": flags,
    }
