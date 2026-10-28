from pathlib import Path


def test_pmr_component_catalog_has_required_deterministic_adapters():
    root = Path("langflow/components/priomedrec")
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    required = ["PayloadValidator", "FeatureExtractor", "InferenceGuard", "XGBoostScorer", "SHAPExplainer", "ThresholdMapper", "MedicationNormalizer", "DiscrepancyRules", "SafetyFlags", "InteractionChecker", "AllergyChecker", "SeverityTiering", "PriorityComposer", "Guardrail", "DeterministicSBARTemplate", "DraftReview"]
    assert all(f"PMR{name}" in source for name in required)
    assert "priomedrec_core" in source


def test_draft_review_component_is_explicitly_human_approved():
    source = Path("langflow/components/priomedrec/safety.py").read_text(encoding="utf-8")
    assert '"action": "DRAFT_REVIEW"' in source
    assert '"requires_human_approval": True' in source
