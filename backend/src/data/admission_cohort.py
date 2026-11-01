"""
src/data/admission_cohort.py
-----------------------------
Builds the admission cohort from encounters.csv.

Cohort definition (documented in docs/label_definition.md):
  - encounter_class IN ('IMP', 'EMER', 'HH')
  - IMP  = Inpatient (primary admission class)
  - EMER = Emergency (may require medication reconciliation on admission)
  - HH   = Home Health (included as monitored admission-like context)
  - AMB  (Ambulatory) and VR (Virtual) are EXCLUDED

Column normalisation applied here (per DECISION_LOG DQI-002, DQI-003):
  - encounter_start_x  → encounter_start  (canonical)
  - birth_date_x       → birth_date       (canonical)
  - encounter_start_y, birth_date_y, encounter_class_display → dropped
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.loaders import load_encounters, load_primedrec_master

# ---------------------------------------------------------------------------
# Cohort definition constants
# ---------------------------------------------------------------------------

ADMISSION_CLASSES: set[str] = {"IMP", "EMER", "HH"}

# Columns to rename (DQI-002)
_RENAME_COLS: dict[str, str] = {
    "encounter_start_x": "encounter_start",
    "birth_date_x":      "birth_date",
}

# Columns to drop after normalisation (DQI-002, DQI-003)
_DROP_COLS: list[str] = [
    "encounter_start_y",
    "birth_date_y",
    "encounter_class_display",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_admission_cohort(
    base_dir: str = "data/raw/synthea",
    admission_classes: set[str] | None = None,
) -> pd.DataFrame:
    """
    Filter encounters to admission-class rows and return a clean DataFrame.

    Parameters
    ----------
    base_dir:
        Directory containing the raw Synthea CSV files.
    admission_classes:
        Override the default ADMISSION_CLASSES set. Use for testing.

    Returns
    -------
    pd.DataFrame
        One row per admission encounter with canonical columns.
    """
    if admission_classes is None:
        admission_classes = ADMISSION_CLASSES

    # Use primedrec_master as base (already 1 row per encounter with key cols)
    master = load_primedrec_master(base_dir)

    # Normalise duplicate columns (DQI-002)
    master = master.rename(columns=_RENAME_COLS)
    drop_existing = [c for c in _DROP_COLS if c in master.columns]
    master = master.drop(columns=drop_existing)

    # Parse datetime columns (timezone-aware)
    for col in ("encounter_start", "encounter_end"):
        if col in master.columns:
            master[col] = pd.to_datetime(master[col], utc=True)

    master["birth_date"] = pd.to_datetime(master["birth_date"], utc=True)

    # Filter to admission classes
    cohort = master[master["encounter_class"].isin(admission_classes)].copy()
    cohort = cohort.reset_index(drop=True)

    return cohort


def save_admission_cohort(
    cohort: pd.DataFrame,
    out_path: str = "data/interim/admission_cohort.csv",
) -> None:
    """Persist the cohort DataFrame to CSV."""
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    cohort.to_csv(out_path, index=False)
    print(f"Admission cohort saved: {out_path} ({len(cohort):,} rows)")
