"""
src/features/medication_features.py
-------------------------------------
Medication burden features for the admission prioritization model.

All features are computed PER ADMISSION ENCOUNTER from:
  - pre_admission_meds  : active medications BEFORE encounter_start
  - admission_meds      : medications ordered DURING the encounter window

No post-discharge data is used.  See docs/feature_dictionary.md for full
definitions and docs/label_definition.md for leakage policy.

Feature list (see docs/feature_dictionary.md for details):
  pre_admission_medication_count
  admission_medication_count
  total_medication_count
  new_medication_count
  discontinued_medication_count
  polypharmacy_flag          (threshold: total_medication_count >= 5)
  high_alert_flag
  high_alert_count
  potential_duplicate_candidates
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Set

import pandas as pd

# ---------------------------------------------------------------------------
# Polypharmacy threshold (project-defined; see docs/feature_dictionary.md)
# ---------------------------------------------------------------------------
POLYPHARMACY_THRESHOLD: int = 5


# ---------------------------------------------------------------------------
# High-alert medication helper
# ---------------------------------------------------------------------------

def _load_high_alert_keywords(
    config_path: str = "configs/high_alert_medications.json",
) -> Set[str]:
    """
    Load keyword list from high_alert_medications.json.
    Returns a set of lowercase keywords for substring matching.
    """
    with open(config_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    keywords: set[str] = set()
    for entry in cfg.get("medications", []):
        for kw in entry.get("rxnorm_keywords", []):
            keywords.add(kw.lower().strip())
    return keywords


def _is_high_alert(med_name: str, keywords: Set[str]) -> bool:
    """Return True if any keyword appears in the lowercased med_name."""
    name_lc = med_name.lower()
    return any(kw in name_lc for kw in keywords)


# ---------------------------------------------------------------------------
# Per-encounter feature computation
# ---------------------------------------------------------------------------

def compute_medication_features(
    cohort: pd.DataFrame,
    pre_meds: pd.DataFrame,
    adm_meds: pd.DataFrame,
    high_alert_config: str = "configs/high_alert_medications.json",
) -> pd.DataFrame:
    """
    Compute all medication burden features for each admission encounter.
    Fully vectorised — no Python loop over encounters.

    Parameters
    ----------
    cohort:
        DataFrame from admission_cohort.py. Must contain: encounter_id
    pre_meds:
        From medication_timeline.build_pre_admission_meds().
        Must contain: admission_encounter_id, medication_code, medication_name_normalized
    adm_meds:
        From medication_timeline.build_admission_meds().
        Must contain: encounter_id, medication_code, medication_name_normalized
    high_alert_config:
        Path to configs/high_alert_medications.json.

    Returns
    -------
    pd.DataFrame  indexed by encounter_id, one column per feature.
    """
    high_alert_kws = _load_high_alert_keywords(high_alert_config)
    enc_ids = cohort["encounter_id"]

    # ------------------------------------------------------------------ #
    # 1. Pre-admission medication counts (distinct codes per encounter)
    # ------------------------------------------------------------------ #
    pre_clean = pre_meds[["admission_encounter_id", "medication_code"]].dropna(
        subset=["medication_code"]
    ).drop_duplicates()

    pre_counts = (
        pre_clean.groupby("admission_encounter_id")["medication_code"]
        .nunique()
        .rename("pre_admission_medication_count")
    )

    # ------------------------------------------------------------------ #
    # 2. Admission medication counts (distinct codes per encounter)
    # ------------------------------------------------------------------ #
    adm_clean = adm_meds[["encounter_id", "medication_code"]].dropna(
        subset=["medication_code"]
    ).drop_duplicates()

    adm_counts = (
        adm_clean.groupby("encounter_id")["medication_code"]
        .nunique()
        .rename("admission_medication_count")
    )

    # ------------------------------------------------------------------ #
    # 3. New / discontinued / total (set arithmetic via merge)
    # ------------------------------------------------------------------ #
    pre_set = pre_clean.rename(columns={"admission_encounter_id": "encounter_id"})
    pre_set["in_pre"] = True
    adm_set = adm_clean.copy()
    adm_set["in_adm"] = True

    combined = pre_set.merge(adm_set, on=["encounter_id", "medication_code"], how="outer")
    combined["in_pre"] = combined["in_pre"].fillna(False).astype(bool)
    combined["in_adm"] = combined["in_adm"].fillna(False).astype(bool)

    # new: in adm, NOT in pre
    new_df = combined[combined["in_adm"] & (combined["in_pre"] == False)]  # noqa: E712
    new_counts = new_df.groupby("encounter_id").size().rename("new_medication_count")

    # discontinued: in pre, NOT in adm
    disc_df = combined[combined["in_pre"] & (combined["in_adm"] == False)]  # noqa: E712
    disc_counts = disc_df.groupby("encounter_id").size().rename("discontinued_medication_count")

    # total (union)
    total_counts = combined.groupby("encounter_id")["medication_code"].nunique().rename("total_medication_count")

    # ------------------------------------------------------------------ #
    # 4. High-alert flag & count
    # ------------------------------------------------------------------ #
    # Combine pre and adm med names per encounter
    _pre_name_cols = ["admission_encounter_id", "medication_name_normalized"]
    _adm_name_cols = ["encounter_id", "medication_name_normalized"]

    pre_names = (
        pre_meds[_pre_name_cols].dropna().drop_duplicates()
        if set(_pre_name_cols).issubset(pre_meds.columns) else
        pd.DataFrame(columns=["encounter_id", "medication_name_normalized"])
    )
    if "admission_encounter_id" in pre_names.columns:
        pre_names = pre_names.rename(columns={"admission_encounter_id": "encounter_id"})

    adm_names = (
        adm_meds[_adm_name_cols].dropna().drop_duplicates()
        if set(_adm_name_cols).issubset(adm_meds.columns) else
        pd.DataFrame(columns=["encounter_id", "medication_name_normalized"])
    )

    all_names = pd.concat([pre_names, adm_names], ignore_index=True).drop_duplicates()

    if all_names.empty or "encounter_id" not in all_names.columns:
        ha_counts = pd.Series(dtype=int, name="high_alert_count")
    else:
        # Mark each name as high-alert
        all_names["is_ha"] = all_names["medication_name_normalized"].apply(
            lambda n: _is_high_alert(str(n), high_alert_kws)
        )
        ha_df = all_names[all_names["is_ha"]]
        ha_counts = ha_df.groupby("encounter_id").size().rename("high_alert_count")

    # ------------------------------------------------------------------ #
    # 5. Potential duplicate candidates (same code >1 time in adm list)
    # ------------------------------------------------------------------ #
    if set(["encounter_id", "medication_code"]).issubset(adm_meds.columns):
        adm_raw = adm_meds[["encounter_id", "medication_code"]].dropna(subset=["medication_code"])
        code_freq = adm_raw.groupby(["encounter_id", "medication_code"]).size().reset_index(name="freq")
        dup_df    = code_freq[code_freq["freq"] > 1]
        dup_counts = dup_df.groupby("encounter_id").size().rename("potential_duplicate_candidates")
    else:
        dup_counts = pd.Series(dtype=int, name="potential_duplicate_candidates")

    # ------------------------------------------------------------------ #
    # 6. Assemble final DataFrame, reindex to full cohort
    # ------------------------------------------------------------------ #
    feat = pd.DataFrame({"encounter_id": enc_ids}).set_index("encounter_id")
    feat = feat.join(pre_counts.rename_axis("encounter_id"), how="left")
    feat = feat.join(adm_counts.rename_axis("encounter_id"), how="left")
    feat = feat.join(total_counts.rename_axis("encounter_id"), how="left")
    feat = feat.join(new_counts.rename_axis("encounter_id"), how="left")
    feat = feat.join(disc_counts.rename_axis("encounter_id"), how="left")
    feat = feat.join(ha_counts.rename_axis("encounter_id"), how="left")
    feat = feat.join(dup_counts.rename_axis("encounter_id"), how="left")
    feat = feat.fillna(0).astype(int)

    feat["polypharmacy_flag"] = (feat["total_medication_count"] >= POLYPHARMACY_THRESHOLD).astype(int)
    feat["high_alert_flag"]   = (feat["high_alert_count"] > 0).astype(int)

    return feat
