"""
tests/test_rules.py
--------------------
Unit tests for Sub-Task 6: medication normalizer + discrepancy engine.

Run: pytest tests/test_rules.py -v
"""

import pytest
import pandas as pd
from src.rules.medication_normalizer import (
    normalize_name,
    normalize_medication,
    build_medication_index,
    UNRESOLVED_FLAG,
)
from src.rules.discrepancy_engine import (
    check_omission,
    check_duplication,
    check_dose_mismatch,
    run_all_rules,
    load_rule_config,
)


CONFIG_PATH = "configs/discrepancy_rules.json"
RULE_VERSION = "rules-0.1.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pre(codes, names=None, statuses=None, doses=None):
    n = len(codes)
    return pd.DataFrame({
        "medication_code": codes,
        "medication_name": names or codes,
        "medication_name_normalized": [str(c).lower() for c in (names or codes)],
        "status": statuses or (["active"] * n),
        "dose_value": doses or ([None] * n),
    })


def _adm(codes, names=None, doses=None):
    n = len(codes)
    return pd.DataFrame({
        "medication_code": codes,
        "medication_name": names or codes,
        "medication_name_normalized": [str(c).lower() for c in (names or codes)],
        "status": ["active"] * n,
        "dose_value": doses or ([None] * n),
    })


# ---------------------------------------------------------------------------
# medication_normalizer
# ---------------------------------------------------------------------------

class TestNormalizeName:

    def test_lowercase_strip(self):
        assert normalize_name("  Metformin  ") == "metformin"

    def test_dosage_stripped(self):
        result = normalize_name("Metformin 500 MG")
        assert "500" not in result
        assert "metformin" in result

    def test_empty_string(self):
        assert normalize_name("") == ""

    def test_none_returns_empty(self):
        assert normalize_name(None) == ""


class TestNormalizeMedication:

    def test_code_preferred_over_name(self):
        key, resolved = normalize_medication("Warfarin 5mg", "R001")
        assert key == "R001"
        assert resolved is True

    def test_name_fallback_when_no_code(self):
        key, resolved = normalize_medication("warfarin", None)
        assert key == "warfarin"
        assert resolved is True

    def test_unresolved_when_both_null(self):
        key, resolved = normalize_medication(None, None)
        assert key == UNRESOLVED_FLAG
        assert resolved is False

    def test_unresolved_when_both_empty(self):
        key, resolved = normalize_medication("", "")
        assert key == UNRESOLVED_FLAG
        assert resolved is False

    def test_code_whitespace_treated_as_empty(self):
        key, resolved = normalize_medication("warfarin", "   ")
        assert resolved is True
        assert key == "warfarin"


class TestBuildMedicationIndex:

    def test_adds_norm_key_column(self):
        df = _pre(["R001", "R002"])
        result = build_medication_index(df)
        assert "norm_key" in result.columns
        assert "is_resolved" in result.columns

    def test_code_used_as_key(self):
        df = _pre(["R001"])
        result = build_medication_index(df)
        assert result.iloc[0]["norm_key"] == "R001"
        assert bool(result.iloc[0]["is_resolved"]) is True

    def test_unresolved_flag_for_empty(self):
        df = pd.DataFrame({
            "medication_code": [None],
            "medication_name": [None],
            "medication_name_normalized": [None],
            "status": ["active"],
            "dose_value": [None],
        })
        result = build_medication_index(df)
        assert result.iloc[0]["norm_key"] == UNRESOLVED_FLAG


# ---------------------------------------------------------------------------
# discrepancy_engine — check_omission
# ---------------------------------------------------------------------------

class TestCheckOmission:

    def _cfg(self, enabled=True):
        return {"enabled": enabled, "require_active_status": True}

    def test_omission_detected(self):
        """R001 in pre, not in adm → POTENTIAL_OMISSION."""
        pre = _pre(["R001"])
        adm = _adm(["R002"])
        flags = check_omission(pre, adm, self._cfg(), RULE_VERSION)
        flag_types = [f["flag_type"] for f in flags]
        assert "POTENTIAL_OMISSION" in flag_types

    def test_no_omission_when_present(self):
        """R001 in both pre and adm → no POTENTIAL_OMISSION."""
        pre = _pre(["R001"])
        adm = _adm(["R001"])
        flags = check_omission(pre, adm, self._cfg(), RULE_VERSION)
        flag_types = [f["flag_type"] for f in flags]
        assert "POTENTIAL_OMISSION" not in flag_types

    def test_disabled_rule_returns_empty(self):
        pre = _pre(["R001"])
        adm = _adm(["R002"])
        flags = check_omission(pre, adm, self._cfg(enabled=False), RULE_VERSION)
        assert flags == []

    def test_completed_med_excluded_when_require_active(self):
        """completed status → should not trigger omission."""
        pre = _pre(["R001"], statuses=["completed"])
        adm = _adm(["R002"])
        flags = check_omission(pre, adm, self._cfg(), RULE_VERSION)
        flag_types = [f["flag_type"] for f in flags]
        assert "POTENTIAL_OMISSION" not in flag_types

    def test_unresolved_flag_when_code_and_name_null(self):
        """Medication with null code and name → UNRESOLVED_MEDICATION_MATCH."""
        pre = pd.DataFrame({
            "medication_code": [None],
            "medication_name": [None],
            "medication_name_normalized": [None],
            "status": ["active"],
            "dose_value": [None],
        })
        adm = _adm(["R001"])
        flags = check_omission(pre, adm, self._cfg(), RULE_VERSION)
        flag_types = [f["flag_type"] for f in flags]
        assert "UNRESOLVED_MEDICATION_MATCH" in flag_types

    def test_verification_required_always_true(self):
        """Every flag must have verification_required=True."""
        pre = _pre(["R001"])
        adm = _adm(["R002"])
        flags = check_omission(pre, adm, self._cfg(), RULE_VERSION)
        for flag in flags:
            assert flag["verification_required"] is True

    def test_multiple_omissions(self):
        """Multiple meds in pre, none in adm → multiple flags."""
        pre = _pre(["R001", "R002", "R003"])
        adm = _adm(["R999"])
        flags = check_omission(pre, adm, self._cfg(), RULE_VERSION)
        omission_flags = [f for f in flags if f["flag_type"] == "POTENTIAL_OMISSION"]
        assert len(omission_flags) == 3


# ---------------------------------------------------------------------------
# discrepancy_engine — check_duplication
# ---------------------------------------------------------------------------

class TestCheckDuplication:

    def _cfg(self, enabled=True):
        return {"enabled": enabled, "match_by": ["medication_code"]}

    def test_duplication_detected(self):
        """Same code twice in adm → POTENTIAL_DUPLICATION."""
        adm = _adm(["R001", "R001", "R002"])
        flags = check_duplication(adm, self._cfg(), RULE_VERSION)
        flag_types = [f["flag_type"] for f in flags]
        assert "POTENTIAL_DUPLICATION" in flag_types

    def test_no_duplication_when_unique(self):
        adm = _adm(["R001", "R002", "R003"])
        flags = check_duplication(adm, self._cfg(), RULE_VERSION)
        flag_types = [f["flag_type"] for f in flags]
        assert "POTENTIAL_DUPLICATION" not in flag_types

    def test_disabled_rule_returns_empty(self):
        adm = _adm(["R001", "R001"])
        flags = check_duplication(adm, self._cfg(enabled=False), RULE_VERSION)
        assert flags == []

    def test_only_duplicated_code_flagged(self):
        """R001 duplicated, R002 unique → only R001 flagged."""
        adm = _adm(["R001", "R001", "R002"])
        flags = check_duplication(adm, self._cfg(), RULE_VERSION)
        dup_flags = [f for f in flags if f["flag_type"] == "POTENTIAL_DUPLICATION"]
        assert len(dup_flags) == 1
        assert dup_flags[0]["medication_code"] == "R001"


# ---------------------------------------------------------------------------
# discrepancy_engine — check_dose_mismatch
# ---------------------------------------------------------------------------

class TestCheckDoseMismatch:

    def _cfg(self, enabled=True):
        return {"enabled": enabled, "tolerance_pct": 0}

    def test_dose_mismatch_detected(self):
        pre = _pre(["R001"], doses=[10.0])
        adm = _adm(["R001"], doses=[20.0])
        flags = check_dose_mismatch(pre, adm, self._cfg(), RULE_VERSION)
        flag_types = [f["flag_type"] for f in flags]
        assert "POTENTIAL_DOSE_MISMATCH" in flag_types

    def test_no_mismatch_same_dose(self):
        pre = _pre(["R001"], doses=[10.0])
        adm = _adm(["R001"], doses=[10.0])
        flags = check_dose_mismatch(pre, adm, self._cfg(), RULE_VERSION)
        flag_types = [f["flag_type"] for f in flags]
        assert "POTENTIAL_DOSE_MISMATCH" not in flag_types

    def test_disabled_returns_empty(self):
        pre = _pre(["R001"], doses=[10.0])
        adm = _adm(["R001"], doses=[20.0])
        flags = check_dose_mismatch(pre, adm, self._cfg(enabled=False), RULE_VERSION)
        assert flags == []

    def test_null_dose_skipped(self):
        """Null dose_value in either → skip, no false positive."""
        pre = _pre(["R001"], doses=[None])
        adm = _adm(["R001"], doses=[10.0])
        flags = check_dose_mismatch(pre, adm, self._cfg(), RULE_VERSION)
        assert flags == []


# ---------------------------------------------------------------------------
# run_all_rules — integration + determinism
# ---------------------------------------------------------------------------

class TestRunAllRules:

    def test_deterministic(self):
        """Same input → identical output every run."""
        pre = _pre(["R001", "R002"])
        adm = _adm(["R003"])
        result1 = run_all_rules("PAT-001", "ENC-001", pre, adm, CONFIG_PATH)
        result2 = run_all_rules("PAT-001", "ENC-001", pre, adm, CONFIG_PATH)
        assert result1 == result2

    def test_output_contract_keys(self):
        """Output must include patient_id, encounter_id, rule_version, flags."""
        pre = _pre(["R001"])
        adm = _adm(["R002"])
        result = run_all_rules("PAT-001", "ENC-001", pre, adm, CONFIG_PATH)
        assert "patient_id" in result
        assert "encounter_id" in result
        assert "rule_version" in result
        assert "flags" in result
        assert isinstance(result["flags"], list)

    def test_rule_version_in_output(self):
        """rule_version in output must match config file."""
        cfg = load_rule_config(CONFIG_PATH)
        pre = _pre(["R001"])
        adm = _adm([])
        result = run_all_rules("PAT-001", "ENC-001", pre, adm, CONFIG_PATH)
        assert result["rule_version"] == cfg["rule_version"]

    def test_no_flags_when_lists_match(self):
        """Identical pre and adm meds → no omission or duplication flags."""
        pre = _pre(["R001", "R002"])
        adm = _adm(["R001", "R002"])
        result = run_all_rules("PAT-001", "ENC-001", pre, adm, CONFIG_PATH)
        omission_flags = [f for f in result["flags"]
                          if f["flag_type"] == "POTENTIAL_OMISSION"]
        dup_flags = [f for f in result["flags"]
                     if f["flag_type"] == "POTENTIAL_DUPLICATION"]
        assert len(omission_flags) == 0
        assert len(dup_flags) == 0
