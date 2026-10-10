"""
tests/test_features.py
-----------------------
Unit tests for Sub-Task 4: feature engineering.

Uses small synthetic DataFrames — no I/O from large CSV files.

Run: pytest tests/test_features.py -v
"""

import pytest
import pandas as pd
import numpy as np

from src.features.medication_features import (
    compute_medication_features,
    POLYPHARMACY_THRESHOLD,
    _is_high_alert,
    _load_high_alert_keywords,
)
from src.features.clinical_features import (
    compute_age,
    encode_gender,
    compute_active_condition_count,
    compute_prior_encounter_count,
    compute_clinical_features,
)
from src.features.feature_pipeline import (
    build_feature_matrix,
    FEATURE_COLUMNS,
    FEATURE_VERSION,
)


# ---------------------------------------------------------------------------
# Synthetic data fixtures
# ---------------------------------------------------------------------------

def make_cohort(n: int = 3) -> pd.DataFrame:
    """Small synthetic cohort."""
    return pd.DataFrame({
        "encounter_id":    [f"ENC-{i:03}" for i in range(n)],
        "patient_id":      [f"PAT-{i:03}" for i in range(n)],
        "encounter_start": pd.to_datetime([
            "2023-01-10T08:00:00+00:00",
            "2023-06-01T10:00:00+00:00",
            "2023-09-20T09:00:00+00:00",
        ], utc=True)[:n],
        "encounter_end": pd.to_datetime([
            "2023-01-14T08:00:00+00:00",
            "2023-06-05T10:00:00+00:00",
            "2023-09-24T09:00:00+00:00",
        ], utc=True)[:n],
        "birth_date": pd.to_datetime([
            "1955-03-01T00:00:00+00:00",  # ~67 yrs old at enc
            "1990-07-15T00:00:00+00:00",  # ~32 yrs
            "1940-01-01T00:00:00+00:00",  # ~83 yrs
        ], utc=True)[:n],
        "gender": ["male", "female", "male"][:n],
        "age": [67, 32, 83][:n],
        "age_65_plus": [1, 0, 1][:n],
    })


_PRE_COLS = ["admission_encounter_id", "medication_code", "medication_name",
             "medication_name_normalized", "status"]
_ADM_COLS = ["encounter_id", "medication_code", "medication_name",
             "medication_name_normalized", "status"]


def make_pre_meds(enc_id: str, codes: list[str], status: str = "active") -> pd.DataFrame:
    """Pre-admission meds for one encounter."""
    if not codes:
        return pd.DataFrame(columns=_PRE_COLS)
    rows = [{"admission_encounter_id": enc_id, "medication_code": c,
             "medication_name": c, "medication_name_normalized": c.lower(),
             "status": status} for c in codes]
    return pd.DataFrame(rows)


def make_adm_meds(enc_id: str, codes: list[str]) -> pd.DataFrame:
    """Admission meds for one encounter."""
    if not codes:
        return pd.DataFrame(columns=_ADM_COLS)
    rows = [{"encounter_id": enc_id, "medication_code": c,
             "medication_name": c, "medication_name_normalized": c.lower(),
             "status": "active"} for c in codes]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# medication_features
# ---------------------------------------------------------------------------

class TestMedicationFeatures:

    def test_pre_admission_count(self):
        cohort   = make_cohort(1)
        pre_meds = make_pre_meds("ENC-000", ["R001", "R002", "R003"])
        adm_meds = make_adm_meds("ENC-000", [])
        feat = compute_medication_features(cohort, pre_meds, adm_meds)
        assert feat.loc["ENC-000", "pre_admission_medication_count"] == 3

    def test_admission_count(self):
        cohort   = make_cohort(1)
        pre_meds = make_pre_meds("ENC-000", [])
        adm_meds = make_adm_meds("ENC-000", ["R010", "R011"])
        feat = compute_medication_features(cohort, pre_meds, adm_meds)
        assert feat.loc["ENC-000", "admission_medication_count"] == 2

    def test_new_medications(self):
        """R002 is only in adm (not pre) → new_count = 1."""
        cohort   = make_cohort(1)
        pre_meds = make_pre_meds("ENC-000", ["R001"])
        adm_meds = make_adm_meds("ENC-000", ["R001", "R002"])
        feat = compute_medication_features(cohort, pre_meds, adm_meds)
        # R002 in adm but not in pre → new_count = 1
        assert feat.loc["ENC-000", "new_medication_count"] == 1
        # R001 in both → discontinued_count = 0
        assert feat.loc["ENC-000", "discontinued_medication_count"] == 0

    def test_discontinued_medications(self):
        """R002 is only in pre (not adm) → discontinued_count = 1."""
        cohort   = make_cohort(1)
        pre_meds = make_pre_meds("ENC-000", ["R001", "R002"])
        adm_meds = make_adm_meds("ENC-000", ["R001"])
        feat = compute_medication_features(cohort, pre_meds, adm_meds)
        # R002 in pre but not adm → discontinued
        assert feat.loc["ENC-000", "discontinued_medication_count"] == 1
        # R001 in both → new_count = 0
        assert feat.loc["ENC-000", "new_medication_count"] == 0

    def test_polypharmacy_below_threshold(self):
        """4 total meds → polypharmacy_flag = 0."""
        cohort   = make_cohort(1)
        pre_meds = make_pre_meds("ENC-000", ["R001", "R002"])
        adm_meds = make_adm_meds("ENC-000", ["R003", "R004"])
        feat = compute_medication_features(cohort, pre_meds, adm_meds)
        assert feat.loc["ENC-000", "polypharmacy_flag"] == 0

    def test_polypharmacy_at_threshold(self):
        """5 total meds → polypharmacy_flag = 1."""
        cohort   = make_cohort(1)
        pre_meds = make_pre_meds("ENC-000", ["R001", "R002", "R003"])
        adm_meds = make_adm_meds("ENC-000", ["R004", "R005"])
        feat = compute_medication_features(cohort, pre_meds, adm_meds)
        assert feat.loc["ENC-000", "polypharmacy_flag"] == 1

    def test_polypharmacy_threshold_constant(self):
        """The threshold must be exactly 5 (project requirement)."""
        assert POLYPHARMACY_THRESHOLD == 5

    def test_high_alert_flag_detected(self):
        cohort   = make_cohort(1)
        pre_meds = make_pre_meds("ENC-000", [])
        adm_meds = make_adm_meds("ENC-000", ["warfarin 5mg"])
        feat = compute_medication_features(cohort, pre_meds, adm_meds)
        assert feat.loc["ENC-000", "high_alert_flag"] == 1

    def test_high_alert_flag_not_triggered(self):
        cohort   = make_cohort(1)
        pre_meds = make_pre_meds("ENC-000", [])
        adm_meds = make_adm_meds("ENC-000", ["amoxicillin 500mg"])
        feat = compute_medication_features(cohort, pre_meds, adm_meds)
        assert feat.loc["ENC-000", "high_alert_flag"] == 0

    def test_duplicate_candidates(self):
        """Same code twice in admission list → 1 duplicate candidate."""
        cohort   = make_cohort(1)
        pre_meds = make_pre_meds("ENC-000", [])
        adm_meds = make_adm_meds("ENC-000", ["R001", "R001", "R002"])
        feat = compute_medication_features(cohort, pre_meds, adm_meds)
        assert feat.loc["ENC-000", "potential_duplicate_candidates"] >= 1

    def test_no_nulls_in_output(self):
        cohort   = make_cohort(3)
        pre_meds = make_pre_meds("ENC-000", ["R001"])
        adm_meds = make_adm_meds("ENC-001", ["R010"])
        feat = compute_medication_features(cohort, pre_meds, adm_meds)
        assert not feat.isnull().any().any(), "Feature matrix must not contain NaN"

    def test_zero_meds_encounter_gives_zero_counts(self):
        cohort   = make_cohort(1)
        pre_meds = pd.DataFrame(columns=["admission_encounter_id", "medication_code",
                                          "medication_name", "medication_name_normalized", "status"])
        adm_meds = pd.DataFrame(columns=["encounter_id", "medication_code",
                                          "medication_name", "medication_name_normalized", "status"])
        feat = compute_medication_features(cohort, pre_meds, adm_meds)
        assert feat.loc["ENC-000", "total_medication_count"] == 0
        assert feat.loc["ENC-000", "polypharmacy_flag"] == 0


# ---------------------------------------------------------------------------
# clinical_features
# ---------------------------------------------------------------------------

class TestClinicalFeatures:

    def test_compute_age_approximate(self):
        birth = pd.Series(pd.to_datetime(["1955-01-01"], utc=True))
        start = pd.Series(pd.to_datetime(["2023-01-01"], utc=True))
        age = compute_age(birth, start)
        assert abs(age.iloc[0] - 68.0) < 0.1

    def test_compute_age_young(self):
        birth = pd.Series(pd.to_datetime(["2010-06-15"], utc=True))
        start = pd.Series(pd.to_datetime(["2023-06-15"], utc=True))
        age = compute_age(birth, start)
        assert abs(age.iloc[0] - 13.0) < 0.1

    def test_encode_gender_male(self):
        result = encode_gender(pd.Series(["male", "Male", "M"]))
        assert list(result) == [1, 1, 1]

    def test_encode_gender_female(self):
        result = encode_gender(pd.Series(["female", "Female", "F"]))
        assert list(result) == [0, 0, 0]

    def test_encode_gender_unknown(self):
        result = encode_gender(pd.Series(["unknown", "other", ""]))
        assert list(result) == [-1, -1, -1]

    def test_active_condition_count_leakage_safe(self):
        """Conditions after encounter_start must NOT be counted."""
        cohort = make_cohort(1)
        conditions = pd.DataFrame({
            "patient_id":      ["PAT-000", "PAT-000"],
            "onset_date":      pd.to_datetime(["2022-01-01", "2024-01-01"], utc=True),
            "clinical_status": ["active", "active"],
            "condition_code":  ["C001", "C002"],
            "condition_name":  ["Cond A", "Cond B"],
            "condition_id":    ["id1", "id2"],
            "encounter_id":    ["ENC-X", "ENC-X"],
            "verification_status": ["confirmed", "confirmed"],
        })
        counts = compute_active_condition_count(cohort, conditions)
        assert counts.iloc[0] == 1  # Only 2022 condition qualifies

    def test_prior_encounter_count_leakage_safe(self):
        """Only encounters BEFORE this admission count."""
        cohort = make_cohort(1)
        all_enc = pd.DataFrame({
            "patient_id":      ["PAT-000", "PAT-000", "PAT-000"],
            "encounter_start": pd.to_datetime([
                "2022-05-01T00:00:00+00:00",  # before → counts
                "2023-01-10T08:00:00+00:00",  # exact same time → NOT counted
                "2023-06-01T00:00:00+00:00",  # after → NOT counted
            ], utc=True),
        })
        counts = compute_prior_encounter_count(cohort, all_enc)
        assert counts.iloc[0] == 1


# ---------------------------------------------------------------------------
# feature_pipeline
# ---------------------------------------------------------------------------

class TestFeaturePipeline:

    def _run_pipeline(self, n: int = 2):
        cohort = make_cohort(n)
        pre_meds = pd.concat([
            make_pre_meds("ENC-000", ["R001", "R002"]),
            make_pre_meds("ENC-001", ["R010"]),
        ], ignore_index=True)
        adm_meds = pd.concat([
            make_adm_meds("ENC-000", ["R002", "R003"]),
            make_adm_meds("ENC-001", ["R011", "R012", "R013", "R014", "R015"]),
        ], ignore_index=True)
        conditions = pd.DataFrame({
            "patient_id":      ["PAT-000"] * 3 + ["PAT-001"] * 2,
            "onset_date":      pd.to_datetime(["2020-01-01"] * 5, utc=True),
            "clinical_status": ["active"] * 5,
            "condition_code":  ["C001", "C002", "C003", "C010", "C011"],
            "condition_name":  ["A", "B", "C", "D", "E"],
            "condition_id":    ["id1", "id2", "id3", "id4", "id5"],
            "encounter_id":    ["ENC-X"] * 5,
            "verification_status": ["confirmed"] * 5,
        })
        all_enc = pd.DataFrame({
            "patient_id":      ["PAT-000", "PAT-001"],
            "encounter_start": pd.to_datetime(["2022-01-01", "2022-06-01"], utc=True),
        })
        return build_feature_matrix(
            cohort, pre_meds, adm_meds, conditions, all_enc,
            high_alert_config="configs/high_alert_medications.json"
        )

    def test_output_shape(self):
        X = self._run_pipeline(2)
        assert X.shape == (2, len(FEATURE_COLUMNS))

    def test_all_feature_columns_present(self):
        X = self._run_pipeline(2)
        for col in FEATURE_COLUMNS:
            assert col in X.columns, f"Missing feature column: {col}"

    def test_no_null_values(self):
        X = self._run_pipeline(2)
        assert not X.isnull().any().any(), "Feature matrix must not contain NaN"

    def test_polypharmacy_enc001_is_true(self):
        """ENC-001 has 5 adm meds + 1 pre → total ≥ 5 → polypharmacy = 1."""
        X = self._run_pipeline(2)
        assert X.loc["ENC-001", "polypharmacy_flag"] == 1

    def test_feature_version_format(self):
        assert FEATURE_VERSION.startswith("features-")
