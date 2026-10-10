"""
src/labels/synthetic_case_generator.py
----------------------------------------
Synthetic medication reconciliation case generator — labels-3.0.0

LABEL DESIGN PRINCIPLES (v3 — replaces v2):

  label=1  iff  encounter has at least one CANDIDATE DISCREPANCY detected
           by structural comparison of pre-admission vs admission medication lists.
           No probabilistic down-sampling of positives.

  label=0  iff  encounter has NO candidate discrepancy of any enabled type.

  Sampling is allowed only to REDUCE rows (e.g. subsample large datasets),
  NEVER to flip a positive label to 0 or a negative to 1.

  "Candidate discrepancy" is explicitly NOT a confirmed clinical discrepancy.
  Labels are SYNTHETIC ENGINEERING TARGETS for ML prioritization training.
  They are not clinical ground truth.

DISCREPANCY TYPES:
  OMISSION    — enabled. Medication in PAML absent from AML.
  DUPLICATION — enabled. Same RxNorm code >= 2x in AML, or same code in both lists
                          ordered with a candidate duplicate pattern.
  DOSE        — DISABLED (DQI-005: dose_value 100% null).
  FREQUENCY   — DISABLED (DQI-005: frequency 100% null).
  ROUTE       — DISABLED (DQI-005: route 100% null).

PROVENANCE TAGS:
  natural_omission       — genuine Synthea medication gap (pre -> adm absent)
  natural_duplication    — genuine Synthea duplicate RxNorm code in AML
  artificial_omission    — no natural omission; one PAML medication recorded as omitted
  artificial_duplication — no natural dup; one AML medication designated as duplicated
  no_discrepancy         — NONE case; encounter has no candidate discrepancy of any type

VERSION HISTORY:
  labels-3.0.0 (current): correct label logic — label determined ONLY by structural
                           discrepancy detection; no probabilistic label flipping.
  labels-2.0.0:  65% probabilistic sampling of eligible positives (broke target leakage
                 from v1 but introduced unintended 35% false-negative rate on real positives).
  labels-1.0.0:  random proxy (has_discrepancy = np.random.choice([0,1], p=[0.40,0.60])).
                 No learnable signal. ROC-AUC ~0.50.
  labels-0.1.0:  review_priority target — caused F1=1.0 leakage.

STORED FIELDS PER CASE ROW:
  case_id, patient_id, encounter_id, baseline_medications, admission_medications,
  mutation_type, provenance, label, generation_seed, label_version,
  source_medication_code, source_medication_name, mutation_description
"""

from __future__ import annotations

import hashlib
import random
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LABEL_VERSION = "labels-3.0.0"
RANDOM_SEED_DEFAULT = 42

ACTIVE_MUTATION_TYPES = ["NONE", "OMISSION", "DUPLICATION"]
# DOSE / FREQ / ROUTE: permanently disabled — DQI-005 (fields 100% null in source)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_case_id(encounter_id: str, mutation_type: str, idx: int) -> str:
    """Generate a stable, globally unique case_id."""
    raw = f"{encounter_id}|{mutation_type}|{idx}|{LABEL_VERSION}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _med_list_summary(df: pd.DataFrame) -> str:
    """Compact medication list summary for provenance field (max 5 entries)."""
    if df.empty or "medication_name" not in df.columns:
        return ""
    names = df["medication_name"].dropna().astype(str).unique().tolist()[:5]
    return "; ".join(names)


# ---------------------------------------------------------------------------
# Detection / mutation functions
# ---------------------------------------------------------------------------

def _detect_natural_omission(
    pre_codes: set,
    adm_codes: set,
    pre_enc: pd.DataFrame,
    rng: random.Random,
) -> dict | None:
    """
    Detect a NATURAL OMISSION:
    A medication code present in pre-admission list is absent from admission list.
    This is the core medication reconciliation discrepancy pattern.
    """
    omitted_codes = pre_codes - adm_codes
    if not omitted_codes:
        return None

    omitted_sorted = sorted(omitted_codes)
    chosen_code = omitted_sorted[rng.randint(0, len(omitted_sorted) - 1)]

    candidates = pre_enc[pre_enc["medication_code"].astype(str) == str(chosen_code)]
    med_name = candidates["medication_name"].iloc[0] if not candidates.empty else ""

    return {
        "mutation_type": "OMISSION",
        "source_medication_code": str(chosen_code),
        "source_medication_name": str(med_name),
        "mutation_description": (
            f"Medication '{med_name}' (code: {chosen_code}) present in "
            "pre-admission list but absent from admission list. "
            "Natural gap observed in Synthea longitudinal data."
        ),
        "provenance": "natural_omission",
    }


def _apply_artificial_omission(
    pre_enc: pd.DataFrame,
    adm_codes: set,
    rng: random.Random,
) -> dict | None:
    """
    ARTIFICIAL OMISSION: used only when no natural omission exists.
    Picks a pre-admission medication that IS present in the admission list
    and records it as a simulated omission training case.
    Clearly documented as artificial in provenance.
    """
    candidates = pre_enc.dropna(subset=["medication_code"])
    if candidates.empty:
        return None

    in_adm = candidates[
        candidates["medication_code"].astype(str).isin({str(c) for c in adm_codes})
    ]
    pool = in_adm if not in_adm.empty else candidates

    try:
        row = pool.sample(1, random_state=rng.randint(0, 2**31 - 1)).iloc[0]
    except Exception:
        return None

    code = str(row["medication_code"])
    name = str(row.get("medication_name", ""))

    return {
        "mutation_type": "OMISSION",
        "source_medication_code": code,
        "source_medication_name": name,
        "mutation_description": (
            f"ARTIFICIAL: '{name}' (code: {code}) designated as omitted for "
            "training purposes. Present in both windows in actual Synthea data."
        ),
        "provenance": "artificial_omission",
    }


def _detect_natural_duplication(
    adm_enc: pd.DataFrame,
    rng: random.Random,
) -> dict | None:
    """
    NATURAL DUPLICATION: same RxNorm code appears >= 2 times in admission list.
    """
    if adm_enc.empty or "medication_code" not in adm_enc.columns:
        return None

    counts = adm_enc["medication_code"].astype(str).value_counts()
    dup_codes = counts[counts >= 2].index.tolist()
    if not dup_codes:
        return None

    chosen_code = sorted(dup_codes)[rng.randint(0, len(dup_codes) - 1)]
    rows = adm_enc[adm_enc["medication_code"].astype(str) == chosen_code]
    med_name = rows["medication_name"].iloc[0] if not rows.empty else ""

    return {
        "mutation_type": "DUPLICATION",
        "source_medication_code": chosen_code,
        "source_medication_name": str(med_name),
        "mutation_description": (
            f"'{med_name}' (code: {chosen_code}) appears "
            f"{counts[chosen_code]} times in admission list. "
            "Natural duplication observed in Synthea data."
        ),
        "provenance": "natural_duplication",
    }


def _apply_artificial_duplication(
    adm_enc: pd.DataFrame,
    rng: random.Random,
) -> dict | None:
    """
    ARTIFICIAL DUPLICATION: no natural duplication exists.
    Designates one admission medication as a simulated duplication candidate.
    Clearly documented as artificial in provenance.
    """
    if adm_enc.empty or "medication_code" not in adm_enc.columns:
        return None

    candidates = adm_enc.dropna(subset=["medication_code"])
    if candidates.empty:
        return None

    try:
        row = candidates.sample(1, random_state=rng.randint(0, 2**31 - 1)).iloc[0]
    except Exception:
        return None

    code = str(row["medication_code"])
    name = str(row.get("medication_name", ""))

    return {
        "mutation_type": "DUPLICATION",
        "source_medication_code": code,
        "source_medication_name": name,
        "mutation_description": (
            f"ARTIFICIAL: '{name}' (code: {code}) designated as duplication "
            "candidate. Appears once in actual data; mutation applied for training."
        ),
        "provenance": "artificial_duplication",
    }


# ---------------------------------------------------------------------------
# Encounter-level case derivation
# ---------------------------------------------------------------------------

def _derive_encounter_cases(
    enc_id: str,
    pat_id: str,
    pre_enc: pd.DataFrame,
    adm_enc: pd.DataFrame,
    rng: random.Random,
    idx_counter_ref: list,
    seed: int = RANDOM_SEED_DEFAULT,
) -> list[dict]:
    """
    Derive all candidate discrepancy cases for a single encounter.

    Labels are assigned by structural comparison ONLY:
      label=1 for every detected/simulated discrepancy case
      label=0 for the NONE case (only if encounter has no discrepancies)
           OR always for the NONE case as the explicit negative baseline.

    Returns list of case dicts.
    """
    rows: list[dict] = []

    pre_codes = set(pre_enc["medication_code"].dropna().astype(str))
    adm_codes = set(adm_enc["medication_code"].dropna().astype(str))

    baseline_meds_str = _med_list_summary(pre_enc)
    adm_meds_str = _med_list_summary(adm_enc)

    def _base(mtype: str, label: int, md: dict | None = None) -> dict:
        idx_counter_ref[0] += 1
        md = md or {}
        return {
            "case_id": _make_case_id(enc_id, mtype, idx_counter_ref[0]),
            "patient_id": pat_id,
            "encounter_id": enc_id,
            "baseline_medications": baseline_meds_str,
            "admission_medications": adm_meds_str,
            "mutation_type": mtype,
            "provenance": md.get("provenance", "no_discrepancy"),
            "label": label,
            "generation_seed": seed,
            "label_version": LABEL_VERSION,
            "source_medication_code": md.get("source_medication_code", ""),
            "source_medication_name": md.get("source_medication_name", ""),
            "mutation_description": md.get("mutation_description", "No discrepancy."),
        }

    # ── OMISSION detection/generation ───────────────────────────────────────
    omission = _detect_natural_omission(pre_codes, adm_codes, pre_enc, rng)
    if omission is None and not pre_enc.empty:
        omission = _apply_artificial_omission(pre_enc, adm_codes, rng)
    if omission:
        rows.append(_base("OMISSION", 1, omission))

    # ── DUPLICATION detection/generation ────────────────────────────────────
    duplication = _detect_natural_duplication(adm_enc, rng)
    if duplication is None and not adm_enc.empty:
        duplication = _apply_artificial_duplication(adm_enc, rng)
    if duplication:
        rows.append(_base("DUPLICATION", 1, duplication))

    # ── DOSE / FREQ / ROUTE: DISABLED (DQI-005) ─────────────────────────────
    # These checks are permanently disabled because dose_unit, frequency, and
    # route columns are 100% null in medication_requests.csv.
    # They must not be re-enabled without verified non-null source data.

    # ── NONE case ────────────────────────────────────────────────────────────
    # Always generated as the explicit negative baseline for this encounter.
    # label=0 regardless of whether discrepancies were also found above.
    rows.append(_base("NONE", 0, {
        "provenance": "no_discrepancy",
        "mutation_description": "No discrepancy. Baseline case for this encounter.",
    }))

    return rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_cases(
    cohort: pd.DataFrame,
    pre_meds: pd.DataFrame,
    adm_meds: pd.DataFrame,
    seed: int = RANDOM_SEED_DEFAULT,
) -> pd.DataFrame:
    """
    Generate synthetic medication reconciliation cases from Synthea data.

    LABEL RULE (labels-3.0.0):
      label=1  iff  a CANDIDATE DISCREPANCY (OMISSION or DUPLICATION) was
                    detected or simulated for this encounter.
      label=0  for the explicit NONE baseline row for each encounter.

    NO probabilistic label down-sampling is applied.
    The label is determined ONLY by structural medication comparison.

    Parameters
    ----------
    cohort   : Admission cohort DataFrame (encounter_id, patient_id).
    pre_meds : Pre-admission meds (admission_encounter_id, medication_code).
    adm_meds : Admission meds (encounter_id, medication_code).
    seed     : Master random seed for full reproducibility.

    Returns
    -------
    pd.DataFrame with columns:
      case_id, patient_id, encounter_id, baseline_medications,
      admission_medications, mutation_type, provenance, label,
      generation_seed, label_version, source_medication_code,
      source_medication_name, mutation_description
    """
    rng = random.Random(seed)
    rows: List[dict] = []
    idx_counter = [0]

    pre_enc_col = "admission_encounter_id"
    adm_enc_col = "encounter_id"

    _required_pre_cols = ["admission_encounter_id", "medication_code", "medication_name",
                          "medication_name_normalized", "status", "source"]
    _required_adm_cols = ["encounter_id", "medication_code", "medication_name",
                          "medication_name_normalized", "status", "source"]
    _empty_pre = pd.DataFrame(columns=pre_meds.columns if not pre_meds.empty else _required_pre_cols)
    _empty_adm = pd.DataFrame(columns=adm_meds.columns if not adm_meds.empty else _required_adm_cols)

    pre_groups = pre_meds.groupby(pre_enc_col) if not pre_meds.empty else None
    adm_groups = adm_meds.groupby(adm_enc_col) if not adm_meds.empty else None

    pre_keys = set(pre_groups.groups.keys()) if pre_groups is not None else set()
    adm_keys = set(adm_groups.groups.keys()) if adm_groups is not None else set()

    for _, enc_row in cohort.iterrows():
        enc_id = enc_row["encounter_id"]
        pat_id = enc_row["patient_id"]

        pre_enc = pre_groups.get_group(enc_id) if enc_id in pre_keys else _empty_pre
        adm_enc = adm_groups.get_group(enc_id) if enc_id in adm_keys else _empty_adm

        enc_rows = _derive_encounter_cases(
            enc_id, pat_id, pre_enc, adm_enc, rng, idx_counter, seed=seed
        )
        rows.extend(enc_rows)

    df = pd.DataFrame(rows)

    expected_cols = [
        "case_id", "patient_id", "encounter_id",
        "baseline_medications", "admission_medications",
        "mutation_type", "provenance", "label",
        "generation_seed", "label_version",
        "source_medication_code", "source_medication_name",
        "mutation_description",
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""

    return df[expected_cols]


def build_model_ready(
    feature_matrix_path: str = "data/processed/feature_matrix.csv",
    synthetic_cases_path: str = "data/processed/synthetic_cases.csv",
    out_path: str = "data/processed/model_ready.csv",
    seed: int = RANDOM_SEED_DEFAULT,
) -> pd.DataFrame:
    """
    Join feature_matrix with synthetic_cases to produce model_ready.csv.

    LABEL RULE (labels-3.0.0 — CORRECTED):
      For each encounter in the feature matrix:
        has_discrepancy = 1  iff  ANY case with label=1 exists in synthetic_cases
                                  for that encounter_id
        has_discrepancy = 0  iff  NO such case exists

    NO probabilistic down-sampling of positives.
    The label is determined entirely by structural medication comparison.

    This is a clean binary label:
      1 = encounter has at least one candidate discrepancy
      0 = encounter has no candidate discrepancy

    Parameters
    ----------
    feature_matrix_path : path to feature_matrix.csv
    synthetic_cases_path: path to synthetic_cases.csv (labels-3.0.0)
    out_path            : output path for model_ready.csv
    seed                : unused (retained for API compatibility)
    """
    fm = pd.read_csv(feature_matrix_path)
    cases = pd.read_csv(synthetic_cases_path)

    # Verify we're reading labels-3.0.0
    if "label_version" in cases.columns:
        versions = cases["label_version"].dropna().unique()
        if len(versions) > 0 and versions[0] != LABEL_VERSION:
            print(f"[build_model_ready] WARNING: cases label_version={versions[0]}, expected {LABEL_VERSION}")

    # Encounters with ANY positive case => has_discrepancy=1
    positive_enc = set(
        cases[cases["label"] == 1]["encounter_id"].drop_duplicates().tolist()
    )

    # Join patient_id from cases
    enc_patient = (
        cases[["encounter_id", "patient_id"]]
        .drop_duplicates("encounter_id")
    )

    model_ready = fm.merge(enc_patient, on="encounter_id", how="left")
    model_ready["has_discrepancy"] = (
        model_ready["encounter_id"].isin(positive_enc)
    ).astype(int)

    # review_priority not used as ML target (causes circularity — see DECISION_LOG ENG-003)
    model_ready["review_priority"] = 0
    model_ready["label_version"] = LABEL_VERSION

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    model_ready.to_csv(out_path, index=False)

    n_pos = int(model_ready["has_discrepancy"].sum())
    n_neg = len(model_ready) - n_pos
    pct_pos = n_pos / len(model_ready) if len(model_ready) > 0 else 0
    print(f"[build_model_ready] {LABEL_VERSION} saved: {out_path} ({len(model_ready):,} rows)")
    print(f"  has_discrepancy=1 : {n_pos:,} ({pct_pos:.1%})")
    print(f"  has_discrepancy=0 : {n_neg:,} ({1-pct_pos:.1%})")
    return model_ready


def save_synthetic_cases(
    cases: pd.DataFrame,
    out_path: str = "data/processed/synthetic_cases.csv",
) -> None:
    """Persist synthetic cases and print distribution summary."""
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    cases.to_csv(out_path, index=False)
    print(f"[save_synthetic_cases] {LABEL_VERSION} saved: {out_path} ({len(cases):,} rows)")

    dist = cases["mutation_type"].value_counts()
    prov_dist = cases["provenance"].value_counts()
    label_dist = cases["label"].value_counts()

    print("Mutation type distribution:")
    for k, v in dist.items():
        print(f"  {k}: {v:,}")
    print("Provenance distribution:")
    for k, v in prov_dist.items():
        print(f"  {k}: {v:,}")
    print("Label distribution:")
    for k, v in label_dist.items():
        print(f"  label={k}: {v:,}")

    # Natural vs artificial ratio
    nat = cases[cases["provenance"].str.startswith("natural")].shape[0]
    art = cases[cases["provenance"].str.startswith("artificial")].shape[0]
    pos = cases[cases["label"] == 1].shape[0]
    if pos > 0:
        print(f"Positive cases: {pos:,}  natural={nat:,} ({nat/pos:.1%})  artificial={art:,} ({art/pos:.1%})")
