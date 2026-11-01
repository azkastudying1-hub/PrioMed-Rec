"""
src/data/validator.py
---------------------
Data Quality Index (DQI) checks for PrioMed-Rec.

Provides:
- null_rate_report()     — null percentage per column per DataFrame
- referential_integrity_check() — FK cross-checks between tables
- encoding_check()       — detect BOM / non-UTF-8 issues
- run_full_audit()       — orchestrates all checks and returns a JSON-ready dict

Decisions from docs/DECISION_LOG.md:
  DQI-001: allergies rows with null patient_id → logged, not dropped here;
            upstream pipeline filters them via load_allergies().
  DQI-002: primedrec_master duplicate columns (encounter_start_x/y,
            birth_date_x/y) → canonical columns defined in data_dictionary.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

import pandas as pd

from src.data.loaders import (
    load_patients,
    load_encounters,
    load_medications,
    load_medication_requests,
    load_medication_administrations,
    load_conditions,
    load_allergies,
    load_primedrec_master,
    load_primedrec_risk_features,
    load_validation_report,
)


# ---------------------------------------------------------------------------
# Null-rate report
# ---------------------------------------------------------------------------

def null_rate_report(df: pd.DataFrame, table_name: str) -> Dict[str, Any]:
    """Return null-rate (0–1) per column for *df*."""
    total = len(df)
    report: dict[str, float] = {}
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        report[col] = {
            "null_count": null_count,
            "null_rate": round(null_count / total, 6) if total > 0 else 0.0,
        }
    return {"table": table_name, "row_count": total, "columns": report}


# ---------------------------------------------------------------------------
# Referential integrity
# ---------------------------------------------------------------------------

def referential_integrity_check(
    child_df: pd.DataFrame,
    parent_df: pd.DataFrame,
    fk_col: str,
    pk_col: str,
    child_name: str,
    parent_name: str,
) -> Dict[str, Any]:
    """Check that every non-null FK in *child_df* exists in *parent_df*."""
    child_vals = child_df[fk_col].dropna()
    parent_vals = set(parent_df[pk_col].dropna().unique())
    orphan_mask = ~child_vals.isin(parent_vals)
    orphan_count = int(orphan_mask.sum())
    orphan_examples = child_vals[orphan_mask].head(5).tolist()
    return {
        "check": f"{child_name}.{fk_col} → {parent_name}.{pk_col}",
        "orphan_count": orphan_count,
        "orphan_rate": round(orphan_count / max(len(child_vals), 1), 6),
        "orphan_examples": orphan_examples,
        "passed": orphan_count == 0,
    }


# ---------------------------------------------------------------------------
# Encoding check
# ---------------------------------------------------------------------------

def encoding_check(path: str | Path) -> Dict[str, Any]:
    """Detect BOM marker or read-error in the raw file bytes."""
    path = Path(path)
    try:
        raw = path.read_bytes()[:4]
        has_bom = raw.startswith(b"\xef\xbb\xbf")
        return {"file": path.name, "has_bom": has_bom, "readable": True}
    except Exception as exc:  # noqa: BLE001
        return {"file": path.name, "has_bom": False, "readable": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Duplicate-column check (specific to primedrec_master)
# ---------------------------------------------------------------------------

def duplicate_column_check(df: pd.DataFrame, table_name: str) -> Dict[str, Any]:
    """Flag columns that appear to be merge-duplicates (suffix _x / _y)."""
    dup_pairs = []
    seen_bases: set[str] = set()
    for col in df.columns:
        if col.endswith("_x"):
            base = col[:-2]
            y_col = base + "_y"
            if y_col in df.columns and base not in seen_bases:
                dup_pairs.append({"base": base, "col_x": col, "col_y": y_col})
                seen_bases.add(base)
    return {"table": table_name, "duplicate_pairs": dup_pairs, "pair_count": len(dup_pairs)}


# ---------------------------------------------------------------------------
# Full audit orchestrator
# ---------------------------------------------------------------------------

def run_full_audit(base_dir: str = "data/raw/synthea") -> Dict[str, Any]:
    """
    Load all CSV tables, run DQI checks, and return a JSON-serialisable dict.
    The result is also the canonical content of data/interim/dqi_report.json.
    """
    print("Loading tables…")
    patients     = load_patients(base_dir)
    encounters   = load_encounters(base_dir)
    medications  = load_medications(base_dir)
    med_req      = load_medication_requests(base_dir)
    med_admin    = load_medication_administrations(base_dir)
    conditions   = load_conditions(base_dir)
    allergies    = load_allergies(base_dir)
    master       = load_primedrec_master(base_dir)
    risk_feat    = load_primedrec_risk_features(base_dir)
    val_report   = load_validation_report(base_dir)

    print("Running null-rate checks…")
    null_reports = [
        null_rate_report(patients,   "patients"),
        null_rate_report(encounters, "encounters"),
        null_rate_report(medications,"medications"),
        null_rate_report(med_req,    "medication_requests"),
        null_rate_report(med_admin,  "medication_administrations"),
        null_rate_report(conditions, "conditions"),
        null_rate_report(allergies,  "allergies"),
        null_rate_report(master,     "primedrec_master"),
        null_rate_report(risk_feat,  "primedrec_risk_features"),
    ]

    print("Running referential integrity checks…")
    ri_checks = [
        referential_integrity_check(
            encounters, patients, "patient_id", "patient_id",
            "encounters", "patients"
        ),
        referential_integrity_check(
            med_req, patients, "patient_id", "patient_id",
            "medication_requests", "patients"
        ),
        referential_integrity_check(
            med_req, encounters, "encounter_id", "encounter_id",
            "medication_requests", "encounters"
        ),
        referential_integrity_check(
            med_admin, patients, "patient_id", "patient_id",
            "medication_administrations", "patients"
        ),
        referential_integrity_check(
            conditions, patients, "patient_id", "patient_id",
            "conditions", "patients"
        ),
        referential_integrity_check(
            allergies, patients, "patient_id", "patient_id",
            "allergies", "patients"
        ),
    ]

    print("Running encoding checks…")
    enc_checks = [
        encoding_check(Path(base_dir) / f)
        for f in [
            "patients.csv", "encounters.csv", "medications.csv",
            "medication_requests.csv", "medication_administrations.csv",
            "conditions.csv", "allergies.csv",
            "primedrec_master.csv", "primedrec_risk_features.csv",
            "validation_report.csv",
        ]
    ]

    print("Running duplicate-column checks…")
    dup_checks = [duplicate_column_check(master, "primedrec_master")]

    # Validation report row counts
    val_row = val_report.iloc[0].to_dict()

    report = {
        "priomed_rec_version": "0.1.0",
        "audit_source": str(Path(base_dir).resolve()),
        "row_counts": {
            "patients":                    len(patients),
            "encounters":                  len(encounters),
            "medications":                 len(medications),
            "medication_requests":         len(med_req),
            "medication_administrations":  len(med_admin),
            "conditions":                  len(conditions),
            "allergies":                   len(allergies),
            "primedrec_master":            len(master),
            "primedrec_risk_features":     len(risk_feat),
        },
        "validation_report_row": {k: int(v) if pd.notna(v) else None for k, v in val_row.items()},
        "null_rate_reports":     null_reports,
        "referential_integrity": ri_checks,
        "encoding_checks":       enc_checks,
        "duplicate_column_checks": dup_checks,
    }
    return report


def save_dqi_report(report: Dict[str, Any], out_path: str = "data/interim/dqi_report.json") -> None:
    """Persist *report* to *out_path* as pretty-printed JSON."""
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"DQI report saved: {out_path}")
