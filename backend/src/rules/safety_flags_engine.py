"""
src/rules/safety_flags_engine.py
----------------------------------
Deterministic safety-flag engine for Stage 2 (post-BPMH) medication review.

Checks each medication in the BPMH admission list against three evidence-based
safety registries loaded from data/drug_risk_lookup.csv:

  1. ISMP High-Alert Medications (Acute Care, 2024)
  2. FDA Narrow Therapeutic Index (NTI) drugs
  3. AGS Beers Criteria 2023 — Potentially Inappropriate Medications (PIM) in adults ≥ 65 y

Architecture contract (Project Foundation v2 §4):
  - This module is STAGE 2 ONLY. It must never be called before BPMH is submitted.
  - It produces flags (deterministic), NOT scores.
  - Every flag carries source, version, and status — visible in UI (principle 5).
  - Module never gives therapy instructions or claims confirmed medication errors.
  - LLM receives flag output as a structured dict; LLM must not alter or extend flags.

Output contract: each flag dict contains
  {
    "flag_type":   ISMP_HIGH_ALERT | NTI_DRUG | BEERS_PIM,
    "drug_name":   str,
    "category":    str,
    "route":       str,
    "source":      str,
    "source_version": str,
    "status":      str,  # always "CANDIDATE" — never "CONFIRMED_ERROR"
    "verification_required": True,
  }
  BEERS_PIM flags also include:
    "beers_note":  str  (brief non-prescriptive note from Beers Criteria)
    "age_threshold": int  (65 — the threshold used)
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

DEFAULT_LOOKUP_PATH = "data/drug_risk_lookup.csv"

SOURCE_VERSION_MAP = {
    "ISMP_2024": {
        "source": "ISMP High-Alert Medications List",
        "source_version": "2024",
        "source_url": "https://www.ismp.org/recommendations/high-alert-medications-acute-list",
    },
    "FDA_NTI": {
        "source": "FDA Narrow Therapeutic Index",
        "source_version": "2024",
        "source_url": "https://www.fda.gov/drugs/drug-approvals-and-databases/narrow-therapeutic-index-drugs",
    },
    "AGS_BEERS_2023": {
        "source": "AGS Beers Criteria",
        "source_version": "2023",
        "source_url": "https://doi.org/10.1111/jgs.18372",
    },
}

BEERS_CATEGORY_NOTES: dict[str, str] = {
    "alprazolam":          "Benzodiazepine — increased fall/cognitive impairment risk in older adults",
    "amitriptyline":       "Tricyclic antidepressant — anticholinergic; avoid in older adults",
    "benztropine":         "Anticholinergic — cognitive impairment risk in older adults",
    "carisoprodol":        "Muscle relaxant — sedation and dependence risk in older adults",
    "chlorpheniramine":    "Anticholinergic antihistamine — sedation risk in older adults",
    "clonazepam":          "Benzodiazepine — increased fall/cognitive impairment risk in older adults",
    "cyclobenzaprine":     "Muscle relaxant — anticholinergic and sedating in older adults",
    "diazepam":            "Benzodiazepine — increased fall/cognitive impairment risk in older adults",
    "diclofenac":          "NSAID — GI bleeding and CV risk; use with caution in older adults",
    "digoxin":             "Avoid doses >0.125 mg/day; narrow therapeutic index",
    "diphenhydramine":     "Anticholinergic antihistamine — confusion, dry mouth, fall risk in older adults",
    "eszopiclone":         "Non-benzo hypnotic — fall/cognitive impairment risk similar to BZD",
    "glipizide":           "Sulfonylurea — prolonged hypoglycemia risk in older adults",
    "glyburide":           "Sulfonylurea — prolonged hypoglycemia risk in older adults",
    "hydroxyzine":         "Anticholinergic — cognitive impairment and sedation in older adults",
    "ibuprofen":           "NSAID — GI bleeding, fluid retention, renal impairment in older adults",
    "indomethacin":        "NSAID — highest GI toxicity risk among NSAIDs in older adults",
    "ketorolac":           "NSAID — high GI bleeding risk; avoid in older adults",
    "lorazepam":           "Benzodiazepine — increased fall/cognitive impairment risk in older adults",
    "methocarbamol":       "Muscle relaxant — sedation and cognitive impairment in older adults",
    "naproxen":            "NSAID — GI bleeding and renal impairment risk in older adults",
    "nitrofurantoin":      "Avoid if CrCl <30 mL/min; pulmonary/hepatic toxicity risk",
    "oxybutynin":          "Anticholinergic — cognitive impairment, urinary retention risk",
    "paroxetine":          "Anticholinergic SSRI — avoid in older adults; prefer sertraline",
    "pioglitazone":        "Thiazolidinedione — fluid retention; avoid in heart failure",
    "sliding scale insulin": "Sliding-scale insulin — hypoglycemia risk without adequate control",
    "zaleplon":            "Non-benzo hypnotic — fall/cognitive impairment risk in older adults",
    "zolpidem":            "Non-benzo hypnotic — fall/cognitive impairment risk in older adults",
}

_BEERS_AGE_THRESHOLD = 65


# ---------------------------------------------------------------------------
# Lookup table loader (cached after first call)
# ---------------------------------------------------------------------------

_lookup_cache: dict[str, dict] | None = None


def _load_lookup(lookup_path: str = DEFAULT_LOOKUP_PATH) -> dict[str, dict]:
    """
    Load drug_risk_lookup.csv into a dict keyed by normalised drug name.
    Result is cached for the lifetime of the process.
    """
    global _lookup_cache
    if _lookup_cache is not None:
        return _lookup_cache

    path = Path(lookup_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Drug risk lookup CSV not found at '{lookup_path}'. "
            "Ensure data/drug_risk_lookup.csv is present."
        )

    lookup: dict[str, dict] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row.get("drug_name", "").strip().lower()
            if not name:
                continue
            lookup[name] = {
                "high_alert": int(row.get("high_alert", 0) or 0),
                "nti":        int(row.get("nti", 0) or 0),
                "beers_pim":  int(row.get("beers_pim", 0) or 0),
                "category":   row.get("category", "").strip(),
                "route":      row.get("route", "").strip(),
                "source":     row.get("source", "ISMP_2024+FDA_NTI+AGS_BEERS_2023").strip(),
            }

    _lookup_cache = lookup
    return lookup


def _clear_lookup_cache() -> None:
    """Reset the module-level cache. Used in tests to reload a custom CSV."""
    global _lookup_cache
    _lookup_cache = None


# ---------------------------------------------------------------------------
# Individual flag constructors
# ---------------------------------------------------------------------------

def _build_high_alert_flag(drug_name: str, row: dict) -> dict:
    return {
        "flag_type": "ISMP_HIGH_ALERT",
        "drug_name": drug_name,
        "category": row["category"],
        "route": row["route"],
        **SOURCE_VERSION_MAP["ISMP_2024"],
        "status": "CANDIDATE",
        "verification_required": True,
    }


def _build_nti_flag(drug_name: str, row: dict) -> dict:
    return {
        "flag_type": "NTI_DRUG",
        "drug_name": drug_name,
        "category": row["category"],
        "route": row["route"],
        **SOURCE_VERSION_MAP["FDA_NTI"],
        "status": "CANDIDATE",
        "verification_required": True,
    }


def _build_beers_flag(drug_name: str, row: dict) -> dict:
    note = BEERS_CATEGORY_NOTES.get(
        drug_name,
        "Potentially inappropriate medication (PIM) in adults ≥65 years (AGS Beers 2023)",
    )
    return {
        "flag_type": "BEERS_PIM",
        "drug_name": drug_name,
        "category": row["category"],
        "route": row["route"],
        "beers_note": note,
        "age_threshold": _BEERS_AGE_THRESHOLD,
        **SOURCE_VERSION_MAP["AGS_BEERS_2023"],
        "status": "CANDIDATE",
        "verification_required": True,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_single_drug(
    drug_name: str,
    patient_age: int | None = None,
    lookup_path: str = DEFAULT_LOOKUP_PATH,
) -> list[dict]:
    """
    Check one drug name against all three safety registries.

    Parameters
    ----------
    drug_name    : medication name (matched case-insensitively against lookup)
    patient_age  : patient age in years; Beers PIM flags only emitted if age ≥ 65.
                   Pass None to suppress Beers check entirely.
    lookup_path  : path to drug_risk_lookup.csv

    Returns
    -------
    List of flag dicts (may be empty). Never raises on lookup miss.
    """
    lookup = _load_lookup(lookup_path)
    norm = drug_name.strip().lower()
    row = lookup.get(norm)
    if row is None:
        return []

    flags: list[dict] = []

    if row["high_alert"]:
        flags.append(_build_high_alert_flag(norm, row))

    if row["nti"]:
        flags.append(_build_nti_flag(norm, row))

    if row["beers_pim"] and patient_age is not None and patient_age >= _BEERS_AGE_THRESHOLD:
        flags.append(_build_beers_flag(norm, row))

    return flags


def check_medication_list(
    drug_names: list[str],
    patient_age: int | None = None,
    lookup_path: str = DEFAULT_LOOKUP_PATH,
) -> dict[str, Any]:
    """
    Check a list of medication names and return aggregated safety flags.

    Parameters
    ----------
    drug_names   : list of medication name strings (as entered in BPMH)
    patient_age  : used for Beers PIM age gate (≥65)
    lookup_path  : path to drug_risk_lookup.csv

    Returns
    -------
    {
        "flags":              list[dict],   # all flags, per-drug
        "high_alert_count":   int,
        "nti_count":          int,
        "beers_pim_count":    int,
        "total_flag_count":   int,
        "lookup_version":     str,
        "source_versions":    dict,
    }
    """
    all_flags: list[dict] = []

    for name in drug_names:
        if not name or not name.strip():
            continue
        all_flags.extend(check_single_drug(name, patient_age, lookup_path))

    high_alert_count = sum(1 for f in all_flags if f["flag_type"] == "ISMP_HIGH_ALERT")
    nti_count        = sum(1 for f in all_flags if f["flag_type"] == "NTI_DRUG")
    beers_count      = sum(1 for f in all_flags if f["flag_type"] == "BEERS_PIM")

    return {
        "flags":            all_flags,
        "high_alert_count": high_alert_count,
        "nti_count":        nti_count,
        "beers_pim_count":  beers_count,
        "total_flag_count": len(all_flags),
        "lookup_version":   "drug_risk_lookup-v1.0",
        "source_versions":  SOURCE_VERSION_MAP,
    }


def check_admission_medications(
    admission_meds: list[dict],
    patient_age: int | None = None,
    lookup_path: str = DEFAULT_LOOKUP_PATH,
) -> dict[str, Any]:
    """
    Convenience wrapper: accepts a list of medication dicts (as stored in BPMH)
    and extracts `medication_name` for the lookup.

    Parameters
    ----------
    admission_meds : list of dicts, each with at least `medication_name` key
    patient_age    : used for Beers PIM age gate
    lookup_path    : path to drug_risk_lookup.csv

    Returns
    -------
    Same shape as check_medication_list().
    """
    names = [
        m.get("medication_name", "") or m.get("drug_name", "")
        for m in admission_meds
        if isinstance(m, dict)
    ]
    return check_medication_list(names, patient_age, lookup_path)
