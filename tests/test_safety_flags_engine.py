"""
tests/test_safety_flags_engine.py
------------------------------------
Unit tests for src/rules/safety_flags_engine.py

Run: pytest tests/test_safety_flags_engine.py -v
"""

from __future__ import annotations

import csv
import os
import pytest
import tempfile

from src.rules.safety_flags_engine import (
    _clear_lookup_cache,
    check_single_drug,
    check_medication_list,
    check_admission_medications,
    _BEERS_AGE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Fixture: write a minimal CSV to use as lookup in tests
# ---------------------------------------------------------------------------

_MINIMAL_CSV = [
    ["drug_name", "high_alert", "nti", "beers_pim", "category", "route", "source"],
    ["warfarin",    "1", "1", "0", "anticoagulants", "oral", "ISMP_2024"],
    ["digoxin",     "1", "1", "1", "inotropic_agents", "IV/PO", "ISMP_2024"],
    ["diazepam",    "0", "0", "1", "", "", "AGS_BEERS_2023"],
    ["morphine",    "1", "0", "0", "opioids", "IV/PO", "ISMP_2024"],
    ["metformin",   "0", "0", "0", "", "", ""],
]


@pytest.fixture(autouse=True)
def reset_lookup_cache(tmp_path):
    """Ensure each test starts with a fresh lookup cache."""
    _clear_lookup_cache()
    # Write minimal CSV
    csv_path = tmp_path / "drug_risk_lookup.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(_MINIMAL_CSV)
    yield str(csv_path)
    _clear_lookup_cache()


# ---------------------------------------------------------------------------
# Test 1: check_single_drug — basic flag generation
# ---------------------------------------------------------------------------

class TestCheckSingleDrug:

    def test_high_alert_drug_flagged(self, reset_lookup_cache):
        flags = check_single_drug("warfarin", lookup_path=reset_lookup_cache)
        types = [f["flag_type"] for f in flags]
        assert "ISMP_HIGH_ALERT" in types

    def test_nti_drug_flagged(self, reset_lookup_cache):
        flags = check_single_drug("warfarin", lookup_path=reset_lookup_cache)
        types = [f["flag_type"] for f in flags]
        assert "NTI_DRUG" in types

    def test_beers_pim_flag_emitted_for_elderly(self, reset_lookup_cache):
        flags = check_single_drug("diazepam", patient_age=70, lookup_path=reset_lookup_cache)
        types = [f["flag_type"] for f in flags]
        assert "BEERS_PIM" in types

    def test_beers_pim_suppressed_for_young_patient(self, reset_lookup_cache):
        flags = check_single_drug("diazepam", patient_age=50, lookup_path=reset_lookup_cache)
        types = [f["flag_type"] for f in flags]
        assert "BEERS_PIM" not in types, (
            "Beers PIM must not be flagged for patients under 65"
        )

    def test_beers_pim_suppressed_when_age_none(self, reset_lookup_cache):
        flags = check_single_drug("diazepam", patient_age=None, lookup_path=reset_lookup_cache)
        types = [f["flag_type"] for f in flags]
        assert "BEERS_PIM" not in types, (
            "Beers PIM must not be flagged when patient_age is None"
        )

    def test_unknown_drug_returns_empty(self, reset_lookup_cache):
        flags = check_single_drug("unknownxyz123", lookup_path=reset_lookup_cache)
        assert flags == [], "Unknown drug must return empty list, not error"

    def test_safe_drug_no_flags(self, reset_lookup_cache):
        flags = check_single_drug("metformin", patient_age=70, lookup_path=reset_lookup_cache)
        assert flags == [], "Metformin has no safety flags in lookup"

    def test_digoxin_all_three_flags(self, reset_lookup_cache):
        """Digoxin is high-alert + NTI + Beers PIM — should produce 3 flags for elderly."""
        flags = check_single_drug("digoxin", patient_age=75, lookup_path=reset_lookup_cache)
        types = {f["flag_type"] for f in flags}
        assert types == {"ISMP_HIGH_ALERT", "NTI_DRUG", "BEERS_PIM"}, (
            f"Digoxin for 75-year-old must produce all 3 flag types, got: {types}"
        )

    def test_case_insensitive_lookup(self, reset_lookup_cache):
        """Drug name lookup must be case-insensitive."""
        flags = check_single_drug("WARFARIN", lookup_path=reset_lookup_cache)
        assert any(f["flag_type"] == "ISMP_HIGH_ALERT" for f in flags), (
            "Lookup must be case-insensitive"
        )

    def test_flag_carries_verification_required(self, reset_lookup_cache):
        flags = check_single_drug("warfarin", lookup_path=reset_lookup_cache)
        for flag in flags:
            assert flag.get("verification_required") is True, (
                "Every flag must carry verification_required=True"
            )

    def test_flag_carries_status_candidate(self, reset_lookup_cache):
        flags = check_single_drug("morphine", lookup_path=reset_lookup_cache)
        for flag in flags:
            assert flag.get("status") == "CANDIDATE", (
                f"Flag status must be CANDIDATE, got '{flag.get('status')}'"
            )

    def test_flag_carries_source_fields(self, reset_lookup_cache):
        flags = check_single_drug("warfarin", lookup_path=reset_lookup_cache)
        for flag in flags:
            assert "source" in flag, "Flag must carry 'source' field"
            assert "source_version" in flag, "Flag must carry 'source_version' field"

    def test_beers_flag_carries_beers_note(self, reset_lookup_cache):
        flags = check_single_drug("digoxin", patient_age=70, lookup_path=reset_lookup_cache)
        beers = next((f for f in flags if f["flag_type"] == "BEERS_PIM"), None)
        assert beers is not None
        assert "beers_note" in beers, "Beers PIM flag must carry 'beers_note'"
        assert "age_threshold" in beers, "Beers PIM flag must carry 'age_threshold'"
        assert beers["age_threshold"] == _BEERS_AGE_THRESHOLD


# ---------------------------------------------------------------------------
# Test 2: check_medication_list — aggregated output
# ---------------------------------------------------------------------------

class TestCheckMedicationList:

    def test_empty_list_returns_zero_counts(self, reset_lookup_cache):
        result = check_medication_list([], lookup_path=reset_lookup_cache)
        assert result["total_flag_count"] == 0
        assert result["flags"] == []

    def test_count_fields_match_flags_list(self, reset_lookup_cache):
        result = check_medication_list(
            ["warfarin", "diazepam"],
            patient_age=70,
            lookup_path=reset_lookup_cache,
        )
        ha = sum(1 for f in result["flags"] if f["flag_type"] == "ISMP_HIGH_ALERT")
        nti = sum(1 for f in result["flags"] if f["flag_type"] == "NTI_DRUG")
        beers = sum(1 for f in result["flags"] if f["flag_type"] == "BEERS_PIM")
        assert result["high_alert_count"] == ha
        assert result["nti_count"] == nti
        assert result["beers_pim_count"] == beers
        assert result["total_flag_count"] == len(result["flags"])

    def test_blank_names_skipped(self, reset_lookup_cache):
        result = check_medication_list(["", "  ", None], lookup_path=reset_lookup_cache)
        assert result["total_flag_count"] == 0

    def test_multiple_drugs_aggregate(self, reset_lookup_cache):
        result = check_medication_list(
            ["warfarin", "morphine", "metformin"],
            lookup_path=reset_lookup_cache,
        )
        assert result["high_alert_count"] == 2  # warfarin + morphine
        assert result["nti_count"] == 1         # warfarin only

    def test_result_carries_lookup_version(self, reset_lookup_cache):
        result = check_medication_list(["warfarin"], lookup_path=reset_lookup_cache)
        assert "lookup_version" in result
        assert result["lookup_version"]

    def test_result_carries_source_versions(self, reset_lookup_cache):
        result = check_medication_list(["warfarin"], lookup_path=reset_lookup_cache)
        assert "source_versions" in result
        assert isinstance(result["source_versions"], dict)


# ---------------------------------------------------------------------------
# Test 3: check_admission_medications — dict-based input
# ---------------------------------------------------------------------------

class TestCheckAdmissionMedications:

    def test_accepts_medication_dicts(self, reset_lookup_cache):
        admission = [
            {"medication_name": "warfarin", "dose": "5mg"},
            {"medication_name": "metformin", "dose": "500mg"},
        ]
        result = check_admission_medications(admission, lookup_path=reset_lookup_cache)
        assert result["high_alert_count"] == 1

    def test_falls_back_to_drug_name_key(self, reset_lookup_cache):
        admission = [{"drug_name": "morphine"}]
        result = check_admission_medications(admission, lookup_path=reset_lookup_cache)
        assert result["high_alert_count"] == 1

    def test_empty_list_returns_zero(self, reset_lookup_cache):
        result = check_admission_medications([], lookup_path=reset_lookup_cache)
        assert result["total_flag_count"] == 0

    def test_beers_age_gate_works(self, reset_lookup_cache):
        admission = [{"medication_name": "diazepam"}]
        # Young patient: no Beers flag
        r_young = check_admission_medications(admission, patient_age=40, lookup_path=reset_lookup_cache)
        r_old   = check_admission_medications(admission, patient_age=68, lookup_path=reset_lookup_cache)
        assert r_young["beers_pim_count"] == 0
        assert r_old["beers_pim_count"] == 1
