"""
tests/test_fase1_b111_normalizer.py
--------------------------------------
Tes unit untuk B-111: drug name normalizer (5 tahap).
"""
import pytest


@pytest.fixture(autouse=True)
def reload_alias_table():
    """Reload alias table before each test to ensure fresh CSV parse."""
    from api.services.normalizer_service import reload_alias_table as _reload
    _reload()
    yield


def test_exact_match_generic():
    from api.services.normalizer_service import normalize_drug_name
    result = normalize_drug_name("warfarin")
    assert result.method == "exact"
    assert result.is_high_alert is True
    assert result.confidence >= 0.9
    assert result.status in ("ok", "draft")


def test_exact_match_brand():
    from api.services.normalizer_service import normalize_drug_name
    result = normalize_drug_name("Norvasc")
    assert result.method == "exact"
    assert result.drug_generic == "amlodipine"


def test_case_insensitive():
    from api.services.normalizer_service import normalize_drug_name
    r1 = normalize_drug_name("METFORMIN")
    r2 = normalize_drug_name("metformin")
    assert r1.drug_generic == r2.drug_generic


def test_alias_strips_dose():
    from api.services.normalizer_service import normalize_drug_name
    # "warfarin 5mg" → alias stage strips dose → exact match on "warfarin"
    result = normalize_drug_name("warfarin 5mg")
    assert result.method in ("alias", "exact")
    assert "warfarin" in result.drug_name_normalized.lower()


def test_unresolved_unknown_drug():
    from api.services.normalizer_service import normalize_drug_name
    result = normalize_drug_name("xyzobatfiktif123")
    assert result.method == "unresolved"
    assert result.confidence == 0.0
    assert result.status == "unresolved"
    # Safety: is_high_alert must be False (not safe to assume)
    assert result.is_high_alert is False


def test_empty_input():
    from api.services.normalizer_service import normalize_drug_name
    result = normalize_drug_name("")
    assert result.method == "unresolved"
    assert result.confidence == 0.0


def test_high_alert_drugs():
    """Known high-alert drugs must be flagged."""
    from api.services.normalizer_service import normalize_drug_name
    for drug in ["warfarin", "heparin", "insulin", "morphine", "fentanyl", "digoxin"]:
        result = normalize_drug_name(drug)
        assert result.is_high_alert is True, f"Expected {drug} to be high alert"


def test_batch_normalize():
    from api.services.normalizer_service import normalize_batch
    results = normalize_batch(["warfarin", "metformin", "unknowndrug"])
    assert len(results) == 3
    assert results[0].is_high_alert is True
    assert results[2].method == "unresolved"


def test_to_dict():
    from api.services.normalizer_service import normalize_drug_name
    result = normalize_drug_name("aspirin")
    d = result.to_dict()
    assert "drug_name_raw" in d
    assert "method" in d
    assert "confidence" in d
