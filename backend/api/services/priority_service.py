"""
api/services/priority_service.py
----------------------------------
Composite priority service (B-105).

Rumus:
    final_tier = max(ml_tier, rules_floor, sla_floor)

Prinsip ADR-04:
  - Rules & SLA hanya boleh MENAIKKAN tier, tidak menurunkan
  - ML mengurutkan dalam-tier (skor kontinu)
  - Tier-1 discrepancy otomatis menaikkan ke HIGH
  - High-alert otomatis menaikkan ke HIGH

Tiers: HIGH > MEDIUM > LOW
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from priomedrec_core.thresholds import high_threshold, medium_threshold


# ---------------------------------------------------------------------------
# Tier ordering
# ---------------------------------------------------------------------------

TIER_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
TIER_FROM_INT = {3: "HIGH", 2: "MEDIUM", 1: "LOW"}


def _tier_int(tier: Optional[str]) -> int:
    if not tier:
        return 1
    return TIER_ORDER.get(tier.upper(), 1)


def _tier_from_score(
    score: float,
    high_thresh: float | None = None,
    med_thresh: float | None = None,
) -> str:
    """Map ML probability score → tier using the versioned threshold file."""
    high = high_threshold() if high_thresh is None else high_thresh
    medium = medium_threshold() if med_thresh is None else med_thresh
    if score >= high:
        return "HIGH"
    if score >= medium:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Main composite function
# ---------------------------------------------------------------------------

def compute_priority(
    ml_score: Optional[float],
    discrepancies: Optional[List[Dict[str, Any]]] = None,
    sla_hours_elapsed: Optional[float] = None,
    sla_config: Optional[Dict[str, Any]] = None,
    current_tier: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Hitung tier prioritas final dan kumpulkan alasan.

    Args:
        ml_score: Probabilitas dari model XGBoost (0..1), bisa None.
        discrepancies: List diskrepansi dari rule engine, dengan field
                       'severity_tier' (int 1/2/3) dan 'is_high_alert' (bool).
        sla_hours_elapsed: Jam sejak admisi.
        sla_config: {"HIGH": {"target_hours": 2, "warning_hours": 1}, ...}
        current_tier: Tier saat ini (untuk memastikan tidak menurun).

    Returns:
        {
            "final_tier": "HIGH" | "MEDIUM" | "LOW",
            "ml_tier": str,
            "ml_score": float | None,
            "rules_floor": str,
            "sla_floor": str,
            "priority_reasons": [{"source": str, "reason": str, "tier": str}],
        }
    """
    reasons: List[Dict[str, str]] = []

    # --- ML tier ---
    if ml_score is not None:
        ml_tier = _tier_from_score(ml_score)
    else:
        ml_tier = "MEDIUM"  # Default bila model tidak tersedia (conservative)
        reasons.append({"source": "system", "reason": "Model ML tidak tersedia — default MEDIUM", "tier": ml_tier})

    tier_int = _tier_int(ml_tier)
    if ml_score is not None:
        reasons.append({
            "source": "ml",
            "reason": f"Skor ML {ml_score:.3f} → {ml_tier}",
            "tier": ml_tier,
        })

    # --- Rules floor ---
    rules_floor = "LOW"
    if discrepancies:
        for disc in discrepancies:
            sev = disc.get("severity_tier", 2)
            is_ha = disc.get("is_high_alert", False)
            rule_type = disc.get("rule_type", "")
            drug = disc.get("drug_name", "")

            if sev == 1 or is_ha:
                rules_floor = "HIGH"
                label = "high-alert" if is_ha else "Tier-1"
                reasons.append({
                    "source": "rules",
                    "reason": f"Diskrepansi {label}: {rule_type} — {drug}",
                    "tier": "HIGH",
                })
            elif sev == 2 and _tier_int(rules_floor) < 2:
                rules_floor = "MEDIUM"
                reasons.append({
                    "source": "rules",
                    "reason": f"Diskrepansi Tier-2: {rule_type} — {drug}",
                    "tier": "MEDIUM",
                })

    tier_int = max(tier_int, _tier_int(rules_floor))

    # --- SLA floor ---
    sla_floor = "LOW"
    if sla_hours_elapsed is not None and sla_config:
        current_final = TIER_FROM_INT.get(tier_int, "LOW")
        cfg = sla_config.get(current_final, {})
        warning_h = cfg.get("warning_hours", 4.0)
        target_h = cfg.get("target_hours", 8.0)

        if sla_hours_elapsed >= target_h:
            sla_floor = "HIGH"
            reasons.append({
                "source": "sla",
                "reason": f"SLA breach: {sla_hours_elapsed:.1f}j ≥ {target_h:.1f}j → eskalasi HIGH",
                "tier": "HIGH",
            })
        elif sla_hours_elapsed >= warning_h:
            sla_floor = "MEDIUM"
            reasons.append({
                "source": "sla",
                "reason": f"SLA warning: {sla_hours_elapsed:.1f}j ≥ {warning_h:.1f}j → MEDIUM",
                "tier": "MEDIUM",
            })

    tier_int = max(tier_int, _tier_int(sla_floor))

    # --- Current tier floor (rules & SLA hanya boleh menaikkan) ---
    if current_tier:
        tier_int = max(tier_int, _tier_int(current_tier))

    final_tier = TIER_FROM_INT.get(tier_int, "LOW")

    return {
        "final_tier": final_tier,
        "ml_tier": ml_tier,
        "ml_score": ml_score,
        "rules_floor": rules_floor,
        "sla_floor": sla_floor,
        "priority_reasons": reasons,
    }


def serialize_reasons(reasons: List[Dict[str, str]]) -> str:
    """Serialize priority_reasons list to JSON string for DB storage."""
    return json.dumps(reasons, ensure_ascii=False)


def deserialize_reasons(json_str: Optional[str]) -> List[Dict[str, str]]:
    """Deserialize priority_reasons from DB JSON string."""
    if not json_str:
        return []
    try:
        return json.loads(json_str)
    except Exception:
        return []
