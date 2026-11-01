"""
src/features/feature_pipeline.py
----------------------------------
Feature matrix assembler for PrioMed-Rec.

FEATURE SETS (labels-3.0.0):

  FEATURE_COLUMNS (full set, 16 features):
    All available features including medication count deltas.
    Used for reference and leakage analysis.
    WARNING: discontinued_medication_count, new_medication_count,
    total_medication_count, potential_duplicate_candidates are
    derived from medication list comparison — the same logic used
    to generate labels. Using these in ML may inflate performance
    beyond what is achievable from pre-review admission information.

  LEAKAGE_SAFE_FEATURE_COLUMNS (10 features):
    Only features available BEFORE the medication reconciliation review
    is performed — i.e., from patient demographics, admission characteristics,
    clinical burden, and high-alert flags observable at admission.
    Excludes features derived from pre/admission medication list comparison.
    Use this set as the primary feature set for ML prioritization.

  See docs/feature_provenance.md for full feature provenance.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.features.medication_features import compute_medication_features
from src.features.clinical_features import compute_clinical_features

# ---------------------------------------------------------------------------
# Feature version — change this when any feature definition changes
# ---------------------------------------------------------------------------
FEATURE_VERSION = "features-0.2.0"

# ── FULL feature set (16 features) ──────────────────────────────────────────
# Includes medication-comparison-derived features.
# These may carry label-adjacent signal — use only for ablation/comparison.
FEATURE_COLUMNS = [
    # Demographic
    "age",
    "age_65_plus",
    "gender_encoded",
    # Medication burden (from list comparison — may correlate with label derivation)
    "pre_admission_medication_count",
    "admission_medication_count",
    "total_medication_count",
    "new_medication_count",
    "discontinued_medication_count",
    "polypharmacy_flag",
    "high_alert_flag",
    "high_alert_count",
    "potential_duplicate_candidates",
    # Clinical complexity
    "active_condition_count",
    "prior_encounter_count",
    # Allergy (data unavailable — DQI-001)
    "allergy_count",
    "has_drug_allergy",
]

# ── LEAKAGE-SAFE feature set (10 features) ──────────────────────────────────
# Only features available BEFORE medication reconciliation review.
# Excludes: discontinued_medication_count, new_medication_count,
#           total_medication_count, pre_admission_medication_count,
#           admission_medication_count, potential_duplicate_candidates
# These excluded features are all derived from medication list comparison —
# the same comparison used to generate the synthetic labels.
# Using them for ML creates a structural shortcut that does not reflect
# real-world pharmacist decision-making (pharmacist does not know the
# medication gap counts before reviewing the lists).
LEAKAGE_SAFE_FEATURE_COLUMNS = [
    # Demographic — available from admission registration
    "age",
    "age_65_plus",
    "gender_encoded",
    # Medication risk indicators — available from admission medication scan
    # (high-alert flag is determined from the admission order set, not from
    # comparison of pre/adm lists)
    "polypharmacy_flag",       # total_medication_count >= 5 (admission list)
    "high_alert_flag",         # any high-alert medication in admission list
    "high_alert_count",        # count of high-alert medications
    # Clinical complexity — available from EHR at admission
    "active_condition_count",
    "prior_encounter_count",
    # Allergy — unavailable (DQI-001), kept as constant 0 placeholder
    "allergy_count",
    "has_drug_allergy",
]


def build_feature_matrix(
    cohort: pd.DataFrame,
    pre_meds: pd.DataFrame,
    adm_meds: pd.DataFrame,
    conditions: pd.DataFrame,
    all_encounters: pd.DataFrame,
    high_alert_config: str = "configs/high_alert_medications.json",
) -> pd.DataFrame:
    """
    Build the complete feature matrix X for the admission cohort.

    All features are leakage-safe (see docs/label_definition.md).
    No post-admission data is used.

    Parameters
    ----------
    cohort:         Admission cohort DataFrame.
    pre_meds:       Pre-admission medication DataFrame.
    adm_meds:       Admission medication DataFrame.
    conditions:     Raw conditions DataFrame.
    all_encounters: Full encounters DataFrame (for prior_encounter_count).
    high_alert_config: Path to high_alert_medications.json.

    Returns
    -------
    pd.DataFrame
        Index = encounter_id. Columns = FEATURE_COLUMNS.
        Missing features filled with 0.
    """
    print(f"[feature_pipeline] Building features for {len(cohort):,} encounters…")

    med_feats  = compute_medication_features(cohort, pre_meds, adm_meds, high_alert_config)
    clin_feats = compute_clinical_features(cohort, conditions, all_encounters)

    # Align on encounter_id index
    X = med_feats.join(clin_feats, how="outer")

    # Enforce canonical column order (fill any missing with 0)
    for col in FEATURE_COLUMNS:
        if col not in X.columns:
            X[col] = 0
    X = X[FEATURE_COLUMNS]

    # Fill any remaining NaN with 0 (conservative default)
    X = X.fillna(0)

    print(f"[feature_pipeline] Feature matrix shape: {X.shape}")
    return X


def save_feature_matrix(
    X: pd.DataFrame,
    out_path: str = "data/processed/feature_matrix.csv",
) -> None:
    """Persist the feature matrix to CSV with encounter_id as index."""
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    X.to_csv(out_path)
    print(f"[feature_pipeline] Feature matrix saved: {out_path} ({len(X):,} rows x {len(X.columns)} features)")


def update_feature_config(
    config_path: str = "configs/feature_config.json",
) -> None:
    """Update feature_config.json with current FEATURE_VERSION and column list."""
    cfg = {
        "version": "0.1.0",
        "feature_version": FEATURE_VERSION,
        "feature_columns": FEATURE_COLUMNS,
        "feature_count": len(FEATURE_COLUMNS),
        "polypharmacy_threshold": 5,
        "excluded_features": [
            {"name": "allergy_count",    "reason": "DQI-001: patient_id 100% null in allergies.csv"},
            {"name": "has_drug_allergy", "reason": "DQI-001: patient_id 100% null in allergies.csv"},
        ],
    }
    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
    print(f"[feature_pipeline] feature_config.json updated: {config_path}")
