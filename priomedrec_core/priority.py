"""Deterministic priority composition. Rules and SLA can only raise a tier."""
from __future__ import annotations

from typing import Any

from .thresholds import high_threshold, medium_threshold

TIER_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
TIER_FROM_INT = {value: key for key, value in TIER_ORDER.items()}


def tier_int(tier: str | None) -> int:
    return TIER_ORDER.get((tier or "LOW").upper(), 1)


def tier_from_score(
    score: float,
    high_threshold_value: float | None = None,
    medium_threshold_value: float | None = None,
) -> str:
    high = high_threshold() if high_threshold_value is None else high_threshold_value
    medium = medium_threshold() if medium_threshold_value is None else medium_threshold_value
    if score >= high:
        return "HIGH"
    if score >= medium:
        return "MEDIUM"
    return "LOW"


def compute_priority(
    ml_score: float | None,
    discrepancies: list[dict[str, Any]] | None = None,
    sla_hours_elapsed: float | None = None,
    sla_config: dict[str, Any] | None = None,
    current_tier: str | None = None,
) -> dict[str, Any]:
    """Return ``max(ML, rules, SLA, current)`` with machine-readable reasons."""
    reasons: list[dict[str, str]] = []
    ml_tier = tier_from_score(ml_score) if ml_score is not None else "MEDIUM"
    if ml_score is None:
        reasons.append({"source": "system", "reason": "Model ML tidak tersedia — default MEDIUM", "tier": ml_tier})
    else:
        reasons.append({"source": "ml", "reason": f"Skor ML {ml_score:.3f} → {ml_tier}", "tier": ml_tier})

    rules_floor = "LOW"
    for finding in discrepancies or []:
        severity = finding.get("severity_tier", finding.get("severity", 3))
        high_alert = bool(finding.get("is_high_alert", False))
        if severity in (1, "1", "HIGH") or high_alert:
            rules_floor = "HIGH"
            reasons.append({"source": "rules", "reason": "Temuan Tier-1 atau high-alert memerlukan telaah", "tier": "HIGH"})
        elif severity in (2, "2", "MEDIUM") and tier_int(rules_floor) < 2:
            rules_floor = "MEDIUM"
            reasons.append({"source": "rules", "reason": "Temuan Tier-2 memerlukan telaah", "tier": "MEDIUM"})

    candidate = max(tier_int(ml_tier), tier_int(rules_floor))
    sla_floor = "LOW"
    if sla_hours_elapsed is not None and sla_config:
        cfg = sla_config.get(TIER_FROM_INT[candidate], {})
        if sla_hours_elapsed >= float(cfg.get("target_hours", float("inf"))):
            sla_floor = "HIGH"
            reasons.append({"source": "sla", "reason": "SLA breach → eskalasi HIGH", "tier": "HIGH"})
        elif sla_hours_elapsed >= float(cfg.get("warning_hours", float("inf"))):
            sla_floor = "MEDIUM"
            reasons.append({"source": "sla", "reason": "SLA warning → MEDIUM", "tier": "MEDIUM"})
    final = TIER_FROM_INT[max(candidate, tier_int(sla_floor), tier_int(current_tier))]
    return {"final_tier": final, "ml_tier": ml_tier, "ml_score": ml_score, "rules_floor": rules_floor, "sla_floor": sla_floor, "priority_reasons": reasons}
