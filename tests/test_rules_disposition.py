"""
tests/test_rules_disposition.py
---------------------------------
Unit tests for disposition-aware omission logic (Tahap 0 poin 5).

These tests verify the CORE CLINICAL RULE from Project Foundation v2 §6.3:
  - Obat rumah DENGAN disposisi terdokumentasi → TIDAK boleh di-flag
  - Obat rumah TANPA disposisi, TANPA padanan sekelas → POTENTIAL_UNDOCUMENTED_OMISSION
  - Obat rumah TANPA disposisi, ADA padanan sekelas  → POSSIBLE_SUBSTITUTION
  - Nama obat tidak bisa dicocokkan ke kamus          → UNRESOLVED_MATCH

Run: pytest tests/test_rules_disposition.py -v
"""

from __future__ import annotations

import pytest
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers: build minimal medication DataFrames
# ---------------------------------------------------------------------------

def _med(code: str, name: str, status: str = "active", disposition: str | None = None) -> dict:
    return {
        "medication_code": code,
        "medication_name": name,
        "medication_name_normalized": name.lower().strip(),
        "status": status,
        "dose_value": None,
        "disposition": disposition,
    }


def _pre(records: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(records)


def _adm(records: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(records)


def _safe_str(value) -> str:
    """Convert a value to string, treating None and NaN (pandas float) as empty string."""
    import math
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def _has_disposition(value) -> bool:
    """Return True only if value is a non-empty, non-NaN string."""
    return bool(_safe_str(value))


def _run_disposition_aware_omission(
    pre_meds: pd.DataFrame,
    adm_meds: pd.DataFrame,
    drug_class_map: dict[str, str] | None = None,
) -> list[dict]:
    """
    Reference implementation of disposition-aware omission logic (§6.3).
    This is the TARGET behavior that discrepancy_engine.py must implement.

    Returns list of flag dicts with flag_type field.
    """
    drug_class_map = drug_class_map or {}
    flags = []

    if pre_meds.empty:
        return flags

    adm_codes = set(
        adm_meds["medication_code"].dropna().astype(str).str.strip().tolist()
        if not adm_meds.empty else []
    )
    adm_names = set(
        adm_meds["medication_name_normalized"].dropna().astype(str).str.strip().tolist()
        if not adm_meds.empty else []
    )

    for _, row in pre_meds.iterrows():
        disposition_raw = row.get("disposition")

        # Rule 1: Has documented disposition → no flag (intended, documented)
        if _has_disposition(disposition_raw):
            continue

        # Re-derive clean strings (None/NaN → empty)
        med_code = _safe_str(row.get("medication_code"))
        med_name = _safe_str(row.get("medication_name_normalized"))
        display_name = _safe_str(row.get("medication_name")) or med_name

        # Rule 2: No resolvable identity → UNRESOLVED_MATCH
        if not med_code and not med_name:
            flags.append({
                "flag_type": "UNRESOLVED_MATCH",
                "medication_code": "",
                "medication_name": display_name,
            })
            continue

        # Rule 3: Medication already in admission list → no flag
        identity_key = med_code if med_code else med_name
        if identity_key in adm_codes or med_name in adm_names:
            continue

        # Rule 4: Check for therapeutic class substitution
        home_class = drug_class_map.get(identity_key) or drug_class_map.get(med_name)
        adm_classes: set[str] = set()
        for k in adm_codes | adm_names:
            cls = drug_class_map.get(k)
            if cls:
                adm_classes.add(cls)

        if home_class and home_class in adm_classes:
            flags.append({
                "flag_type": "POSSIBLE_SUBSTITUTION",
                "medication_code": med_code,
                "medication_name": display_name,
            })
        else:
            flags.append({
                "flag_type": "POTENTIAL_UNDOCUMENTED_OMISSION",
                "medication_code": med_code,
                "medication_name": display_name,
            })

    return flags


# ---------------------------------------------------------------------------
# Test 1: Obat DENGAN disposisi → TIDAK boleh di-flag (prinsip paling penting)
# ---------------------------------------------------------------------------

class TestDispositionPreventsFlag:

    def test_dilanjutkan_no_flag(self):
        """Disposition=DILANJUTKAN → no omission flag."""
        pre = _pre([_med("R001", "Warfarin", disposition="DILANJUTKAN")])
        adm = _adm([_med("R999", "Amlodipine")])
        flags = _run_disposition_aware_omission(pre, adm)
        assert not any(f["flag_type"] == "POTENTIAL_UNDOCUMENTED_OMISSION" for f in flags), \
            "DILANJUTKAN medication must not produce omission flag"

    def test_ditunda_no_flag(self):
        """Disposition=DITUNDA → no omission flag."""
        pre = _pre([_med("R001", "Metformin", disposition="DITUNDA")])
        adm = _adm([_med("R999", "Insulin")])
        flags = _run_disposition_aware_omission(pre, adm)
        assert not any(f["flag_type"] == "POTENTIAL_UNDOCUMENTED_OMISSION" for f in flags), \
            "DITUNDA medication must not produce omission flag"

    def test_diganti_no_flag(self):
        """Disposition=DIGANTI → no omission flag."""
        pre = _pre([_med("R001", "Candesartan", disposition="DIGANTI")])
        adm = _adm([_med("R002", "Captopril")])
        flags = _run_disposition_aware_omission(pre, adm)
        assert not any(f["flag_type"] == "POTENTIAL_UNDOCUMENTED_OMISSION" for f in flags), \
            "DIGANTI medication must not produce omission flag"

    def test_dihentikan_no_flag(self):
        """Disposition=DIHENTIKAN → no omission flag."""
        pre = _pre([_med("R001", "Aspirin", disposition="DIHENTIKAN")])
        adm = _adm([_med("R999", "Warfarin")])
        flags = _run_disposition_aware_omission(pre, adm)
        assert not any(f["flag_type"] == "POTENTIAL_UNDOCUMENTED_OMISSION" for f in flags), \
            "DIHENTIKAN medication must not produce omission flag"

    def test_all_dispositions_in_batch_no_omission_flags(self):
        """Multiple meds all with dispositions → zero omission flags."""
        pre = _pre([
            _med("R001", "Warfarin",    disposition="DILANJUTKAN"),
            _med("R002", "Metformin",   disposition="DITUNDA"),
            _med("R003", "Candesartan", disposition="DIGANTI"),
            _med("R004", "Aspirin",     disposition="DIHENTIKAN"),
        ])
        adm = _adm([_med("R999", "OtherDrug")])
        flags = _run_disposition_aware_omission(pre, adm)
        omission_flags = [f for f in flags if f["flag_type"] == "POTENTIAL_UNDOCUMENTED_OMISSION"]
        assert len(omission_flags) == 0, \
            f"Expected 0 omission flags, got {len(omission_flags)}"


# ---------------------------------------------------------------------------
# Test 2: Tanpa disposisi, tanpa padanan → POTENTIAL_UNDOCUMENTED_OMISSION
# ---------------------------------------------------------------------------

class TestNonDispositionNoSubstitute:

    def test_no_disposition_no_match_flagged(self):
        """No disposition, absent from admission → POTENTIAL_UNDOCUMENTED_OMISSION."""
        pre = _pre([_med("R001", "Bisoprolol", disposition=None)])
        adm = _adm([_med("R999", "Amlodipine")])
        flags = _run_disposition_aware_omission(pre, adm)
        flag_types = [f["flag_type"] for f in flags]
        assert "POTENTIAL_UNDOCUMENTED_OMISSION" in flag_types, \
            "Missing disposition + absent from admission must flag POTENTIAL_UNDOCUMENTED_OMISSION"

    def test_empty_string_disposition_flagged(self):
        """Empty string disposition treated same as no disposition."""
        pre = _pre([_med("R001", "Bisoprolol", disposition="")])
        adm = _adm([_med("R999", "Amlodipine")])
        flags = _run_disposition_aware_omission(pre, adm)
        flag_types = [f["flag_type"] for f in flags]
        assert "POTENTIAL_UNDOCUMENTED_OMISSION" in flag_types, \
            "Empty string disposition must be treated same as None"

    def test_multiple_no_disposition_all_flagged(self):
        """Three meds without disposition all absent → three flags."""
        pre = _pre([
            _med("R001", "Bisoprolol", disposition=None),
            _med("R002", "Spironolactone", disposition=None),
            _med("R003", "Furosemide", disposition=None),
        ])
        adm = _adm([_med("R999", "Unrelated")])
        flags = _run_disposition_aware_omission(pre, adm)
        omission_flags = [f for f in flags if f["flag_type"] == "POTENTIAL_UNDOCUMENTED_OMISSION"]
        assert len(omission_flags) == 3, \
            f"Expected 3 POTENTIAL_UNDOCUMENTED_OMISSION flags, got {len(omission_flags)}"


# ---------------------------------------------------------------------------
# Test 3: Tanpa disposisi, ADA padanan sekelas → POSSIBLE_SUBSTITUTION
# ---------------------------------------------------------------------------

class TestPossibleSubstitution:

    def test_same_class_substitution_flagged(self):
        """No disposition + same therapeutic class in admission → POSSIBLE_SUBSTITUTION."""
        # Candesartan (ARB) at home, Captopril (ACE-I) in admission
        # Both classified as "RAAS" in our demo drug_class_map
        drug_class_map = {
            "R001": "RAAS",  # Candesartan
            "R002": "RAAS",  # Captopril
        }
        pre = _pre([_med("R001", "Candesartan", disposition=None)])
        adm = _adm([_med("R002", "Captopril")])
        flags = _run_disposition_aware_omission(pre, adm, drug_class_map=drug_class_map)
        flag_types = [f["flag_type"] for f in flags]
        assert "POSSIBLE_SUBSTITUTION" in flag_types, \
            "Same therapeutic class without disposition must flag POSSIBLE_SUBSTITUTION"

    def test_same_class_not_omission(self):
        """POSSIBLE_SUBSTITUTION must NOT also flag POTENTIAL_UNDOCUMENTED_OMISSION."""
        drug_class_map = {"R001": "PPI", "R002": "PPI"}
        pre = _pre([_med("R001", "Omeprazole", disposition=None)])
        adm = _adm([_med("R002", "Lansoprazole")])
        flags = _run_disposition_aware_omission(pre, adm, drug_class_map=drug_class_map)
        flag_types = [f["flag_type"] for f in flags]
        assert "POTENTIAL_UNDOCUMENTED_OMISSION" not in flag_types, \
            "When POSSIBLE_SUBSTITUTION is flagged, must not also flag POTENTIAL_UNDOCUMENTED_OMISSION"
        assert "POSSIBLE_SUBSTITUTION" in flag_types


# ---------------------------------------------------------------------------
# Test 4: Nama tidak bisa dicocokkan → UNRESOLVED_MATCH
# ---------------------------------------------------------------------------

class TestUnresolvedMatch:

    def test_null_code_and_name_unresolved(self):
        """Null code and name → UNRESOLVED_MATCH."""
        pre = pd.DataFrame([{
            "medication_code": None,
            "medication_name": None,
            "medication_name_normalized": None,
            "status": "active",
            "dose_value": None,
            "disposition": None,
        }])
        adm = _adm([_med("R001", "SomeDrug")])
        flags = _run_disposition_aware_omission(pre, adm)
        flag_types = [f["flag_type"] for f in flags]
        assert "UNRESOLVED_MATCH" in flag_types, \
            "Null code and name must produce UNRESOLVED_MATCH"

    def test_unresolved_not_omission(self):
        """UNRESOLVED_MATCH must not also flag POTENTIAL_UNDOCUMENTED_OMISSION."""
        pre = pd.DataFrame([{
            "medication_code": None,
            "medication_name": None,
            "medication_name_normalized": None,
            "status": "active",
            "dose_value": None,
            "disposition": None,
        }])
        adm = _adm([_med("R001", "SomeDrug")])
        flags = _run_disposition_aware_omission(pre, adm)
        flag_types = [f["flag_type"] for f in flags]
        assert "POTENTIAL_UNDOCUMENTED_OMISSION" not in flag_types, \
            "UNRESOLVED_MATCH must not also produce POTENTIAL_UNDOCUMENTED_OMISSION"


# ---------------------------------------------------------------------------
# Test 5: Mixed scenarios (disposition + no-disposition in same batch)
# ---------------------------------------------------------------------------

class TestMixedBatch:

    def test_mixed_batch_only_no_disposition_flagged(self):
        """
        3 meds: 2 with disposition (no flag), 1 without disposition (flagged).
        Only the one without disposition must appear in flags.
        """
        pre = _pre([
            _med("R001", "Warfarin",   disposition="DILANJUTKAN"),
            _med("R002", "Metformin",  disposition="DITUNDA"),
            _med("R003", "Bisoprolol", disposition=None),   # <- this one should flag
        ])
        adm = _adm([_med("R999", "OtherDrug")])
        flags = _run_disposition_aware_omission(pre, adm)

        flagged_codes = {f["medication_code"] for f in flags}
        assert "R001" not in flagged_codes, "Warfarin (DILANJUTKAN) must not be flagged"
        assert "R002" not in flagged_codes, "Metformin (DITUNDA) must not be flagged"
        assert "R003" in flagged_codes, "Bisoprolol (no disposition) must be flagged"

    def test_omission_flag_carries_medication_name(self):
        """Each POTENTIAL_UNDOCUMENTED_OMISSION flag must carry the medication name."""
        pre = _pre([_med("R003", "Bisoprolol", disposition=None)])
        adm = _adm([_med("R999", "OtherDrug")])
        flags = _run_disposition_aware_omission(pre, adm)
        omission = next((f for f in flags if f["flag_type"] == "POTENTIAL_UNDOCUMENTED_OMISSION"), None)
        assert omission is not None
        assert omission.get("medication_name"), "Flag must carry medication_name"

    def test_medication_in_admission_not_flagged_regardless_of_disposition(self):
        """Medication present in admission list must never be flagged even without disposition."""
        pre = _pre([_med("R001", "Warfarin", disposition=None)])
        adm = _adm([_med("R001", "Warfarin")])  # same code in admission
        flags = _run_disposition_aware_omission(pre, adm)
        flag_types = [f["flag_type"] for f in flags]
        assert "POTENTIAL_UNDOCUMENTED_OMISSION" not in flag_types, \
            "Medication present in admission list must not be flagged even without disposition"


# ---------------------------------------------------------------------------
# Test 6: Edge cases — empty lists, single medication
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_pre_meds_no_flags(self):
        """Empty pre-admission list → zero flags."""
        pre = _pre([])
        adm = _adm([_med("R001", "Warfarin")])
        flags = _run_disposition_aware_omission(pre, adm)
        assert flags == [], "Empty pre_meds must produce no flags"

    def test_empty_admission_list_no_disposition_flagged(self):
        """Empty admission list + no disposition → POTENTIAL_UNDOCUMENTED_OMISSION."""
        pre = _pre([_med("R001", "Bisoprolol", disposition=None)])
        adm = _adm([])
        flags = _run_disposition_aware_omission(pre, adm)
        flag_types = [f["flag_type"] for f in flags]
        assert "POTENTIAL_UNDOCUMENTED_OMISSION" in flag_types

    def test_empty_admission_list_with_disposition_no_flag(self):
        """Empty admission list + has disposition → no omission flag."""
        pre = _pre([_med("R001", "Metformin", disposition="DITUNDA")])
        adm = _adm([])
        flags = _run_disposition_aware_omission(pre, adm)
        flag_types = [f["flag_type"] for f in flags]
        assert "POTENTIAL_UNDOCUMENTED_OMISSION" not in flag_types
