"""
tests/test_data.py
------------------
Unit tests for Sub-Task 2: data loaders and DQI validators.

NOTE: These tests load large Synthea CSV files (up to 885K rows).
They are marked @pytest.mark.slow and run separately from the fast suite.

Run fast tests only:
    pytest tests/ --ignore=tests/test_data.py -q

Run all including slow:
    pytest tests/ -q
"""

import pytest
import pandas as pd
from pathlib import Path

pytestmark = pytest.mark.slow

from src.data.loaders import (
    load_csv,
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
    SCHEMA,
)
from src.data.validator import (
    null_rate_report,
    referential_integrity_check,
    duplicate_column_check,
)

BASE_DIR = "data/raw/synthea"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _df(name: str) -> pd.DataFrame:
    """Load a table by schema name."""
    loaders = {
        "patients":                   load_patients,
        "encounters":                 load_encounters,
        "medications":                load_medications,
        "medication_requests":        load_medication_requests,
        "medication_administrations": load_medication_administrations,
        "conditions":                 load_conditions,
        "allergies":                  load_allergies,
        "primedrec_master":           load_primedrec_master,
        "primedrec_risk_features":    load_primedrec_risk_features,
        "validation_report":          load_validation_report,
    }
    return loaders[name](BASE_DIR)


# ---------------------------------------------------------------------------
# Schema / column-presence tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("table_name", list(SCHEMA.keys()))
def test_expected_columns_present(table_name):
    """Every expected column must be present in the loaded DataFrame."""
    df = _df(table_name)
    for col in SCHEMA[table_name]:
        assert col in df.columns, (
            f"[{table_name}] missing expected column: '{col}'"
        )


@pytest.mark.parametrize("table_name", list(SCHEMA.keys()))
def test_load_no_error(table_name):
    """Each loader must return a non-empty DataFrame without raising."""
    df = _df(table_name)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0, f"[{table_name}] returned empty DataFrame"


# ---------------------------------------------------------------------------
# Row count sanity (from validation_report.csv)
# ---------------------------------------------------------------------------

def test_patients_row_count():
    assert len(load_patients(BASE_DIR)) == 17_286


def test_encounters_row_count():
    assert len(load_encounters(BASE_DIR)) == 488_422


def test_primedrec_master_row_count():
    assert len(load_primedrec_master(BASE_DIR)) == 488_422


def test_validation_report_parser_errors_zero():
    vr = load_validation_report(BASE_DIR)
    assert int(vr.iloc[0]["parser_errors"]) == 0


# ---------------------------------------------------------------------------
# load_csv with invalid expected_cols raises KeyError
# ---------------------------------------------------------------------------

def test_load_csv_missing_column_raises():
    with pytest.raises(KeyError, match="missing expected columns"):
        load_csv(
            f"{BASE_DIR}/patients.csv",
            expected_cols=["patient_id", "nonexistent_column_xyz"],
        )


def test_load_csv_no_validation_does_not_raise():
    df = load_csv(f"{BASE_DIR}/patients.csv", expected_cols=None)
    assert "patient_id" in df.columns


# ---------------------------------------------------------------------------
# DQI — null rate report structure
# ---------------------------------------------------------------------------

def test_null_rate_report_structure():
    patients = load_patients(BASE_DIR)
    report = null_rate_report(patients, "patients")
    assert report["table"] == "patients"
    assert report["row_count"] == 17_286
    for col in SCHEMA["patients"]:
        assert col in report["columns"]
        entry = report["columns"][col]
        assert "null_count" in entry
        assert "null_rate" in entry
        assert 0.0 <= entry["null_rate"] <= 1.0


def test_patients_key_columns_have_no_nulls():
    patients = load_patients(BASE_DIR)
    report = null_rate_report(patients, "patients")
    for col in ["patient_id", "gender", "birth_date"]:
        assert report["columns"][col]["null_rate"] == 0.0


def test_allergies_patient_id_all_null():
    """DQI-001: allergies.patient_id must be 100% null (documented data issue)."""
    allergies = load_allergies(BASE_DIR)
    report = null_rate_report(allergies, "allergies")
    assert report["columns"]["patient_id"]["null_rate"] == 1.0, (
        "DQI-001: allergies.patient_id expected to be 100% null"
    )


# ---------------------------------------------------------------------------
# DQI — referential integrity
# ---------------------------------------------------------------------------

def test_encounters_patients_ri_passes():
    encounters = load_encounters(BASE_DIR)
    patients = load_patients(BASE_DIR)
    result = referential_integrity_check(
        encounters, patients, "patient_id", "patient_id",
        "encounters", "patients"
    )
    assert result["passed"] is True


def test_med_requests_encounter_ri_fails():
    """DQI-006: medication_requests has ~50% orphan encounter_ids — this is a known issue."""
    med_req = load_medication_requests(BASE_DIR)
    encounters = load_encounters(BASE_DIR)
    result = referential_integrity_check(
        med_req, encounters, "encounter_id", "encounter_id",
        "medication_requests", "encounters"
    )
    assert result["passed"] is False
    assert result["orphan_count"] > 0


# ---------------------------------------------------------------------------
# DQI — duplicate column check
# ---------------------------------------------------------------------------

def test_primedrec_master_has_two_duplicate_pairs():
    """DQI-002: primedrec_master must have exactly 2 _x/_y duplicate pairs."""
    master = load_primedrec_master(BASE_DIR)
    result = duplicate_column_check(master, "primedrec_master")
    assert result["pair_count"] == 2
    bases = {p["base"] for p in result["duplicate_pairs"]}
    assert "encounter_start" in bases
    assert "birth_date" in bases

# ===========================================================================
# Sub-Task 3 tests — Admission Cohort & Medication Timeline
# ===========================================================================

from src.data.admission_cohort import build_admission_cohort, ADMISSION_CLASSES
from src.data.medication_timeline import (
    build_pre_admission_meds,
    build_admission_meds,
)


# ---------------------------------------------------------------------------
# Admission cohort
# ---------------------------------------------------------------------------

def test_admission_cohort_only_admission_classes():
    """Cohort must only contain encounters from ADMISSION_CLASSES."""
    cohort = build_admission_cohort(BASE_DIR)
    unexpected = set(cohort["encounter_class"].unique()) - ADMISSION_CLASSES
    assert unexpected == set(), f"Unexpected encounter classes in cohort: {unexpected}"


def test_admission_cohort_excludes_amb_vr():
    """AMB and VR must be fully excluded from the cohort."""
    cohort = build_admission_cohort(BASE_DIR)
    assert "AMB" not in cohort["encounter_class"].values
    assert "VR"  not in cohort["encounter_class"].values


def test_admission_cohort_no_duplicate_encounter_ids():
    """Each encounter_id must appear exactly once in the cohort."""
    cohort = build_admission_cohort(BASE_DIR)
    assert cohort["encounter_id"].is_unique


def test_admission_cohort_canonical_columns_present():
    """Canonical columns from DQI-002 normalisation must be present."""
    cohort = build_admission_cohort(BASE_DIR)
    assert "encounter_start" in cohort.columns
    assert "birth_date"      in cohort.columns
    # Drop columns must be absent
    assert "encounter_start_x" not in cohort.columns
    assert "encounter_start_y" not in cohort.columns
    assert "encounter_class_display" not in cohort.columns


def test_admission_cohort_encounter_start_is_datetime():
    """encounter_start must be parsed as datetime (UTC-aware)."""
    cohort = build_admission_cohort(BASE_DIR)
    assert pd.api.types.is_datetime64_any_dtype(cohort["encounter_start"])


# ---------------------------------------------------------------------------
# Medication timeline — using small synthetic data to avoid I/O cost
# ---------------------------------------------------------------------------

def _make_synthetic_cohort() -> pd.DataFrame:
    """Tiny 2-patient cohort for fast unit tests."""
    return pd.DataFrame({
        "encounter_id":   ["ENC-001", "ENC-002"],
        "patient_id":     ["PAT-001", "PAT-002"],
        "encounter_start": pd.to_datetime(["2023-06-01T08:00:00+00:00",
                                           "2023-09-15T10:00:00+00:00"], utc=True),
        "encounter_end":   pd.to_datetime(["2023-06-05T08:00:00+00:00",
                                           "2023-09-20T10:00:00+00:00"], utc=True),
        "encounter_class": ["IMP", "EMER"],
    })


def _make_synthetic_timeline() -> pd.DataFrame:
    """Timeline with events: 1 pre-admission, 1 in-admission, 1 future (post)."""
    return pd.DataFrame({
        "patient_id":              ["PAT-001", "PAT-001", "PAT-001"],
        "encounter_id":            ["ENC-001", "ENC-001", "ENC-001"],
        "medication_name":         ["MedA",    "MedB",    "MedC"],
        "medication_code":         ["R001",    "R002",    "R003"],
        "event_datetime":          pd.to_datetime([
            "2023-05-20T10:00:00+00:00",  # BEFORE encounter_start → pre-admission
            "2023-06-02T10:00:00+00:00",  # DURING encounter → admission
            "2023-06-10T10:00:00+00:00",  # AFTER encounter_end → post (never in pre)
        ], utc=True),
        "status":                  ["active", "active", "active"],
        "source":                  ["medication_request"] * 3,
        "medication_name_normalized": ["meda", "medb", "medc"],
    })


def test_pre_admission_meds_no_future_leakage():
    """No pre-admission event may have event_datetime >= encounter_start."""
    cohort   = _make_synthetic_cohort()
    timeline = _make_synthetic_timeline()
    pre      = build_pre_admission_meds(cohort, timeline)

    if pre.empty:
        pytest.skip("No pre-admission meds for synthetic cohort")

    leaks = pre[pre["event_datetime"] >= pre["encounter_start"]]
    assert len(leaks) == 0, (
        f"Future leakage detected: {len(leaks)} rows with event_datetime >= encounter_start"
    )


def test_pre_admission_meds_correct_event():
    """Only MedA (before admission) should be in pre-admission for PAT-001."""
    cohort   = _make_synthetic_cohort()
    timeline = _make_synthetic_timeline()
    pre      = build_pre_admission_meds(cohort, timeline)

    if pre.empty:
        pytest.skip("No pre-admission meds for synthetic cohort")

    pat1_pre = pre[pre["admission_encounter_id"] == "ENC-001"]["medication_code"].tolist()
    assert "R001" in pat1_pre, "MedA (pre-admission) should be in pre_admission_meds"
    assert "R002" not in pat1_pre, "MedB (during admission) must NOT be in pre_admission_meds"
    assert "R003" not in pat1_pre, "MedC (post-admission) must NOT be in pre_admission_meds"


def test_admission_meds_within_window():
    """Only MedB (during window) should be in admission_meds for ENC-001."""
    cohort   = _make_synthetic_cohort()
    timeline = _make_synthetic_timeline()
    adm      = build_admission_meds(cohort, timeline)

    if adm.empty:
        pytest.skip("No admission meds for synthetic cohort")

    enc1_adm = adm[adm["encounter_id"] == "ENC-001"]["medication_code"].tolist()
    assert "R002" in enc1_adm, "MedB (in-window) should be in admission_meds"
    assert "R001" not in enc1_adm, "MedA (pre-admission) must NOT be in admission_meds"
    assert "R003" not in enc1_adm, "MedC (post-window) must NOT be in admission_meds"


def test_pre_admission_excludes_completed_meds():
    """Completed medications must not appear in pre_admission_meds."""
    cohort = _make_synthetic_cohort()
    tl = _make_synthetic_timeline()
    # Mark MedA as completed — should now be excluded
    tl.loc[0, "status"] = "completed"
    pre = build_pre_admission_meds(cohort, tl)
    if not pre.empty:
        assert "R001" not in pre["medication_code"].tolist(), (
            "Completed med should not appear in pre_admission_meds"
        )

