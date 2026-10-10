"""
tests/test_labels.py
---------------------
Unit tests for Sub-Task 5: synthetic case generation (v2 — longitudinal labels).

Run: pytest tests/test_labels.py -v
"""

import pytest
import pandas as pd
from src.labels.synthetic_case_generator import (
    generate_cases,
    RANDOM_SEED_DEFAULT,
    ACTIVE_MUTATION_TYPES,
    LABEL_VERSION,
)


# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------

def _make_cohort(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame({
        "encounter_id": [f"ENC-{i:03}" for i in range(n)],
        "patient_id":   [f"PAT-{i:03}" for i in range(n)],
    })


def _make_pre_meds() -> pd.DataFrame:
    return pd.DataFrame({
        "admission_encounter_id": ["ENC-000", "ENC-000", "ENC-001"],
        "medication_code":        ["R001",    "R002",    "R010"],
        "medication_name":        ["MedA",    "MedB",    "MedX"],
        "medication_name_normalized": ["meda","medb",   "medx"],
        "dose_value":             [10.0,      5.0,       None],
        "status":                 ["active",  "active",  "active"],
        "source":                 ["medication_request"] * 3,
    })


def _make_adm_meds() -> pd.DataFrame:
    return pd.DataFrame({
        "encounter_id":           ["ENC-000", "ENC-001"],
        "medication_code":        ["R003",    "R010"],
        "medication_name":        ["MedC",    "MedX"],
        "medication_name_normalized": ["medc","medx"],
        "dose_value":             [20.0,       None],
        "status":                 ["active",  "active"],
        "source":                 ["medication_administration"] * 2,
    })


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

def test_reproducibility_same_seed():
    """Generating twice with the same seed must produce identical results."""
    cohort   = _make_cohort()
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    cases1 = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    cases2 = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    assert cases1.equals(cases2), "Cases must be identical for the same seed"


def test_different_seeds_store_different_seed_value():
    """Each run stores the seed passed in; different seeds -> different stored values."""
    cohort   = _make_cohort(1)
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    cases1 = generate_cases(cohort, pre_meds, adm_meds, seed=1)
    cases2 = generate_cases(cohort, pre_meds, adm_meds, seed=999)
    # labels-3.0.0 uses 'generation_seed' (was 'random_seed' in v2)
    assert (cases1["generation_seed"] == 1).all()
    assert (cases2["generation_seed"] == 999).all()
    assert not (cases1["generation_seed"] == cases2["generation_seed"]).all()


# ---------------------------------------------------------------------------
# case_id uniqueness
# ---------------------------------------------------------------------------

def test_case_id_unique():
    """All case_id values must be unique."""
    cohort   = _make_cohort()
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    assert cases["case_id"].is_unique, "case_id must be unique per case"


# ---------------------------------------------------------------------------
# NONE cases always generated
# ---------------------------------------------------------------------------

def test_none_case_always_present():
    """Every encounter must have at least one NONE case (label=0)."""
    cohort   = _make_cohort(3)
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    for enc_id in cohort["encounter_id"]:
        enc_cases = cases[cases["encounter_id"] == enc_id]
        none_cases = enc_cases[enc_cases["mutation_type"] == "NONE"]
        assert len(none_cases) >= 1, f"No NONE case for encounter {enc_id}"


def test_none_cases_have_label_zero():
    """NONE mutation type must always have label=0."""
    cohort   = _make_cohort()
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    none_cases = cases[cases["mutation_type"] == "NONE"]
    assert (none_cases["label"] == 0).all(), "NONE cases must have label=0"


# ---------------------------------------------------------------------------
# Mutation cases have label=1
# ---------------------------------------------------------------------------

def test_mutation_cases_have_label_one():
    """All non-NONE mutation types must have label=1."""
    cohort   = _make_cohort()
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    mutation_cases = cases[cases["mutation_type"] != "NONE"]
    if not mutation_cases.empty:
        assert (mutation_cases["label"] == 1).all(), "Mutation cases must have label=1"


# ---------------------------------------------------------------------------
# OMISSION traceability
# ---------------------------------------------------------------------------

def test_omission_has_source_medication():
    """Every OMISSION case must reference a source_medication_code."""
    cohort   = _make_cohort()
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    omissions = cases[cases["mutation_type"] == "OMISSION"]
    if not omissions.empty:
        assert omissions["source_medication_code"].notna().all()
        assert (omissions["source_medication_code"] != "").all()


def test_omission_provenance_valid():
    """OMISSION cases must have a valid provenance value (labels-3.0.0 short tags)."""
    cohort   = _make_cohort()
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    omissions = cases[cases["mutation_type"] == "OMISSION"]
    # labels-3.0.0 uses short provenance tags
    valid_provenances = {"natural_omission", "artificial_omission"}
    if not omissions.empty:
        assert omissions["provenance"].isin(valid_provenances).all(), (
            f"Unexpected OMISSION provenance: {omissions['provenance'].unique()}"
        )


def test_duplication_provenance_valid():
    """DUPLICATION cases must have a valid provenance value (labels-3.0.0 short tags)."""
    cohort   = _make_cohort()
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    dups = cases[cases["mutation_type"] == "DUPLICATION"]
    # labels-3.0.0 uses short provenance tags
    valid_provenances = {"natural_duplication", "artificial_duplication"}
    if not dups.empty:
        assert dups["provenance"].isin(valid_provenances).all(), (
            f"Unexpected DUPLICATION provenance: {dups['provenance'].unique()}"
        )


def test_none_provenance_is_no_discrepancy():
    """NONE cases must have provenance='no_discrepancy'."""
    cohort   = _make_cohort()
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    none_cases = cases[cases["mutation_type"] == "NONE"]
    assert (none_cases["provenance"] == "no_discrepancy").all()


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def test_required_columns_present():
    """Output must contain all required schema columns (labels-3.0.0)."""
    required = [
        "case_id", "patient_id", "encounter_id",
        "baseline_medications", "admission_medications",
        "mutation_type", "provenance", "label",
        "generation_seed", "label_version",
        "source_medication_code", "source_medication_name", "mutation_description",
    ]
    cohort   = _make_cohort()
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    for col in required:
        assert col in cases.columns, f"Missing required column: {col}"


def test_label_binary():
    """Label must only contain 0 or 1."""
    cohort   = _make_cohort()
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    assert set(cases["label"].unique()).issubset({0, 1})


def test_generation_seed_stored():
    """generation_seed column must equal the seed passed to generate_cases (labels-3.0.0)."""
    cohort   = _make_cohort(1)
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    for seed in [0, 42, 12345]:
        cases = generate_cases(cohort, pre_meds, adm_meds, seed=seed)
        assert (cases["generation_seed"] == seed).all(), (
            f"generation_seed column must equal {seed}"
        )


# ---------------------------------------------------------------------------
# Disabled mutation types (DQI-005)
# ---------------------------------------------------------------------------

def test_frequency_discrepancy_never_generated():
    """FREQUENCY_DISCREPANCY must never appear — DQI-005 disables it."""
    cohort   = _make_cohort()
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    assert "FREQUENCY_DISCREPANCY" not in cases["mutation_type"].values, (
        "FREQUENCY_DISCREPANCY must not be generated (DQI-005)"
    )


def test_route_discrepancy_never_generated():
    """ROUTE_DISCREPANCY must never appear — DQI-005 disables it."""
    cohort   = _make_cohort()
    pre_meds = _make_pre_meds()
    adm_meds = _make_adm_meds()
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    assert "ROUTE_DISCREPANCY" not in cases["mutation_type"].values, (
        "ROUTE_DISCREPANCY must not be generated (DQI-005)"
    )


# ---------------------------------------------------------------------------
# Natural omission detection
# ---------------------------------------------------------------------------

def test_natural_omission_detected():
    """When a pre-admission med is absent from admission, OMISSION must be detected."""
    cohort = pd.DataFrame({"encounter_id": ["ENC-000"], "patient_id": ["PAT-000"]})
    pre_meds = pd.DataFrame({
        "admission_encounter_id": ["ENC-000"],
        "medication_code": ["R001"],
        "medication_name": ["MedA"],
        "medication_name_normalized": ["meda"],
        "status": ["active"],
        "source": ["medication_request"],
    })
    # Admission has DIFFERENT medication — natural omission of R001
    adm_meds = pd.DataFrame({
        "encounter_id": ["ENC-000"],
        "medication_code": ["R999"],
        "medication_name": ["MedZ"],
        "medication_name_normalized": ["medz"],
        "status": ["active"],
        "source": ["medication_administration"],
    })
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    omissions = cases[cases["mutation_type"] == "OMISSION"]
    assert len(omissions) >= 1, "Natural omission must be detected"
    assert (omissions["provenance"] == "natural_omission").all()
    assert (omissions["source_medication_code"] == "R001").all()


def test_natural_duplication_detected():
    """When same code appears twice in adm_meds, DUPLICATION must be natural."""
    cohort = pd.DataFrame({"encounter_id": ["ENC-000"], "patient_id": ["PAT-000"]})
    pre_meds = pd.DataFrame({
        "admission_encounter_id": ["ENC-000"],
        "medication_code": ["R001"],
        "medication_name": ["MedA"],
        "medication_name_normalized": ["meda"],
        "status": ["active"],
        "source": ["medication_request"],
    })
    # R002 appears twice in admission -> natural duplication
    adm_meds = pd.DataFrame({
        "encounter_id":   ["ENC-000", "ENC-000"],
        "medication_code": ["R002",    "R002"],
        "medication_name": ["MedB",    "MedB"],
        "medication_name_normalized": ["medb", "medb"],
        "status": ["active", "active"],
        "source": ["medication_administration"] * 2,
    })
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    dups = cases[cases["mutation_type"] == "DUPLICATION"]
    assert len(dups) >= 1, "Natural duplication must be detected"
    assert (dups["provenance"] == "natural_duplication").all()


# ---------------------------------------------------------------------------
# Empty input handling
# ---------------------------------------------------------------------------

def test_empty_pre_meds_only_none_and_duplication():
    """With no pre-admission meds, only NONE and DUPLICATION may appear."""
    cohort   = _make_cohort(1)
    pre_meds = pd.DataFrame(columns=[
        "admission_encounter_id", "medication_code", "medication_name",
        "medication_name_normalized", "status", "source"
    ])
    adm_meds = _make_adm_meds()
    cases = generate_cases(cohort, pre_meds, adm_meds, seed=42)
    allowed = {"NONE", "DUPLICATION"}
    present = set(cases["mutation_type"].unique())
    unexpected = present - allowed
    assert not unexpected, f"Unexpected mutation types with empty pre_meds: {unexpected}"


def test_label_version_constant_exists():
    """LABEL_VERSION must be a non-empty string."""
    assert isinstance(LABEL_VERSION, str) and len(LABEL_VERSION) > 0


def test_active_mutation_types_excludes_disabled():
    """ACTIVE_MUTATION_TYPES must not contain FREQUENCY or ROUTE discrepancy."""
    assert "FREQUENCY_DISCREPANCY" not in ACTIVE_MUTATION_TYPES
    assert "ROUTE_DISCREPANCY" not in ACTIVE_MUTATION_TYPES
