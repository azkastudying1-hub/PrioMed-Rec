from priomedrec_core.contracts import AnalysisInput
from priomedrec_core.priority import compute_priority


def test_core_contract_defaults_are_synthetic_and_safe():
    payload = AnalysisInput()
    assert payload.patient_id.startswith("SYNTHETIC-")
    assert payload.pre_admission_meds == []


def test_priority_core_rules_and_sla_never_lower_ml_tier():
    result = compute_priority(0.90, discrepancies=[], sla_hours_elapsed=0, sla_config={"HIGH": {"target_hours": 99, "warning_hours": 98}}, current_tier="LOW")
    assert result["final_tier"] == "HIGH"


def test_priority_core_tier_one_escalates():
    result = compute_priority(0.05, discrepancies=[{"severity_tier": 1}])
    assert result["final_tier"] == "HIGH"
