"""
tests/test_fase1_b105_priority.py
-----------------------------------
Tes unit untuk B-105: composite priority service.
"""


def test_ml_only_high():
    from api.services.priority_service import compute_priority
    result = compute_priority(ml_score=0.85)
    assert result["final_tier"] == "HIGH"
    assert result["ml_tier"] == "HIGH"


def test_ml_only_medium():
    from api.services.priority_service import compute_priority
    result = compute_priority(ml_score=0.5)
    assert result["final_tier"] == "MEDIUM"


def test_ml_only_low():
    from api.services.priority_service import compute_priority
    result = compute_priority(ml_score=0.2)
    assert result["final_tier"] == "LOW"


def test_tier1_discrepancy_escalates_to_high():
    from api.services.priority_service import compute_priority
    discs = [{"severity_tier": 1, "is_high_alert": False, "rule_type": "omission", "drug_name": "warfarin"}]
    result = compute_priority(ml_score=0.3, discrepancies=discs)
    assert result["final_tier"] == "HIGH"
    assert result["rules_floor"] == "HIGH"


def test_high_alert_escalates_to_high():
    from api.services.priority_service import compute_priority
    discs = [{"severity_tier": 2, "is_high_alert": True, "rule_type": "omission", "drug_name": "insulin"}]
    result = compute_priority(ml_score=0.2, discrepancies=discs)
    assert result["final_tier"] == "HIGH"


def test_sla_breach_escalates():
    from api.services.priority_service import compute_priority
    cfg = {"HIGH": {"target_hours": 2.0, "warning_hours": 1.0},
           "MEDIUM": {"target_hours": 8.0, "warning_hours": 4.0},
           "LOW": {"target_hours": 24.0, "warning_hours": 16.0}}
    # LOW ml, but 10h elapsed ≥ LOW target 24? No → 10h >= warning_hours 16? No either
    # Use MEDIUM ml score so SLA config uses MEDIUM bucket (8h target, 4h warning)
    # 10h ≥ 8h target → SLA breach → HIGH
    result = compute_priority(ml_score=0.5, sla_hours_elapsed=10.0, sla_config=cfg)
    assert result["final_tier"] == "HIGH"
    sla_reasons = [r for r in result["priority_reasons"] if r["source"] == "sla"]
    assert len(sla_reasons) > 0


def test_rules_never_decrease_tier():
    from api.services.priority_service import compute_priority
    # ML gives HIGH, rules give LOW → final should stay HIGH
    discs = [{"severity_tier": 3, "is_high_alert": False, "rule_type": "omission", "drug_name": "omeprazole"}]
    result = compute_priority(ml_score=0.9, discrepancies=discs)
    assert result["final_tier"] == "HIGH"


def test_current_tier_floor():
    from api.services.priority_service import compute_priority
    # Current is HIGH, ML gives MEDIUM → should stay HIGH
    result = compute_priority(ml_score=0.4, current_tier="HIGH")
    assert result["final_tier"] == "HIGH"


def test_no_ml_score_defaults_medium():
    from api.services.priority_service import compute_priority
    result = compute_priority(ml_score=None)
    assert result["final_tier"] == "MEDIUM"
    assert any(r["source"] == "system" for r in result["priority_reasons"])


def test_reasons_populated():
    from api.services.priority_service import compute_priority
    discs = [{"severity_tier": 1, "is_high_alert": True, "rule_type": "omission", "drug_name": "warfarin"}]
    result = compute_priority(ml_score=0.7, discrepancies=discs)
    sources = {r["source"] for r in result["priority_reasons"]}
    assert "ml" in sources
    assert "rules" in sources
