"""
api/routes/v1/knowledge.py
---------------------------
GET/POST /api/v1/knowledge/lookup — knowledge base lookup (A-307 Tool 4).

Read-only endpoint for drug knowledge lookup:
  - alias:       drug name normalization (brand → INN)
  - interaction: known DDI from knowledge/interactions.json
  - allergy:     cross-reactivity rules from configs/allergy_rules.json (DRAFT)
  - high_alert:  whether drug is in the high-alert list

Used by:
  - MCP Tool 4 (lookup_drug_knowledge)
  - Future: Knowledge Lookup page in UI (F-215, PILOT)

Safety: read-only, no clinical decisions made here.
        All allergy/DDI content is DRAFT_PERLU_VALIDASI_APOTEKER.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class KnowledgeLookupRequest(BaseModel):
    drug_name: str
    lookup_type: str = "alias"  # alias | interaction | allergy | high_alert
    actor_type: Optional[str] = None


class KnowledgeLookupResponse(BaseModel):
    drug_name: str
    lookup_type: str
    results: List[Dict[str, Any]]
    source: str
    status: str   # "DRAFT_PERLU_VALIDASI_APOTEKER" always for clinical content
    count: int


# ---------------------------------------------------------------------------
# Data loaders (lazy, cached)
# ---------------------------------------------------------------------------

_ALIAS_CACHE: Optional[Dict[str, str]] = None
_INTERACTIONS_CACHE: Optional[Any] = None
_ALLERGY_CACHE: Optional[Any] = None
_HIGH_ALERT_CACHE: Optional[List[str]] = None


def _load_aliases() -> Dict[str, str]:
    global _ALIAS_CACHE
    if _ALIAS_CACHE is not None:
        return _ALIAS_CACHE
    p = Path("knowledge/drug_alias.csv")
    cache: Dict[str, str] = {}
    if p.exists():
        with open(p, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                brand = (row.get("brand_name") or row.get("alias") or "").strip().lower()
                inn = (row.get("inn_name") or row.get("standard_name") or "").strip()
                if brand and inn:
                    cache[brand] = inn
    _ALIAS_CACHE = cache
    return cache


def _load_interactions() -> Any:
    global _INTERACTIONS_CACHE
    if _INTERACTIONS_CACHE is not None:
        return _INTERACTIONS_CACHE
    p = Path("knowledge/interactions.json")
    if p.exists():
        with open(p, encoding="utf-8") as f:
            _INTERACTIONS_CACHE = json.load(f)
    else:
        _INTERACTIONS_CACHE = []
    return _INTERACTIONS_CACHE


def _load_allergy_rules() -> Any:
    global _ALLERGY_CACHE
    if _ALLERGY_CACHE is not None:
        return _ALLERGY_CACHE
    p = Path("configs/allergy_rules.json")
    if p.exists():
        with open(p, encoding="utf-8") as f:
            _ALLERGY_CACHE = json.load(f)
    else:
        _ALLERGY_CACHE = {}
    return _ALLERGY_CACHE


def _load_high_alert() -> List[str]:
    global _HIGH_ALERT_CACHE
    if _HIGH_ALERT_CACHE is not None:
        return _HIGH_ALERT_CACHE
    p = Path("configs/discrepancy_rules.json")
    if p.exists():
        with open(p, encoding="utf-8") as f:
            cfg = json.load(f)
        _HIGH_ALERT_CACHE = [d.lower() for d in cfg.get("high_alert_drugs", [])]
    else:
        _HIGH_ALERT_CACHE = []
    return _HIGH_ALERT_CACHE


# ---------------------------------------------------------------------------
# Lookup logic
# ---------------------------------------------------------------------------

def _lookup_alias(drug_name: str) -> List[Dict[str, Any]]:
    aliases = _load_aliases()
    norm = drug_name.strip().lower()
    results = []
    # Exact match
    if norm in aliases:
        results.append({"match_type": "exact", "brand": drug_name, "inn": aliases[norm]})
    # Fuzzy / substring match (top 5)
    for brand, inn in aliases.items():
        if brand != norm and (norm in brand or brand in norm):
            results.append({"match_type": "partial", "brand": brand, "inn": inn})
        if len(results) >= 5:
            break
    return results


def _lookup_interaction(drug_name: str) -> List[Dict[str, Any]]:
    interactions = _load_interactions()
    norm = drug_name.strip().lower()
    results = []
    if isinstance(interactions, list):
        for item in interactions:
            drug_a = str(item.get("drug_a", "")).lower()
            drug_b = str(item.get("drug_b", "")).lower()
            if norm in drug_a or norm in drug_b:
                results.append({
                    "drug_a": item.get("drug_a"),
                    "drug_b": item.get("drug_b"),
                    "severity": item.get("severity"),
                    "description": item.get("description", ""),
                    "status": "DRAFT_PERLU_VALIDASI_APOTEKER",
                })
    elif isinstance(interactions, dict):
        items = interactions.get("interactions", [])
        for item in items:
            drug_a = str(item.get("drug_a", "")).lower()
            drug_b = str(item.get("drug_b", "")).lower()
            if norm in drug_a or norm in drug_b:
                results.append({
                    "drug_a": item.get("drug_a"),
                    "drug_b": item.get("drug_b"),
                    "severity": item.get("severity"),
                    "description": item.get("description", ""),
                    "status": "DRAFT_PERLU_VALIDASI_APOTEKER",
                })
    return results[:10]


def _lookup_allergy(drug_name: str) -> List[Dict[str, Any]]:
    allergy_data = _load_allergy_rules()
    norm = drug_name.strip().lower()
    results = []
    rules = allergy_data.get("cross_reactivity_rules", []) if isinstance(allergy_data, dict) else []
    for rule in rules:
        trigger = str(rule.get("trigger_class", "")).lower()
        cross = [str(c).lower() for c in rule.get("cross_reactive_with", [])]
        if norm in trigger or any(norm in c for c in cross):
            results.append({
                "trigger_class": rule.get("trigger_class"),
                "cross_reactive_with": rule.get("cross_reactive_with"),
                "evidence_level": rule.get("evidence_level"),
                "note": rule.get("note", ""),
                "status": "DRAFT_PERLU_VALIDASI_APOTEKER",
                "owner": "TBD-apoteker",
            })
    return results[:5]


def _lookup_high_alert(drug_name: str) -> List[Dict[str, Any]]:
    high_alerts = _load_high_alert()
    norm = drug_name.strip().lower()
    is_high_alert = any(norm in ha or ha in norm for ha in high_alerts)
    return [{
        "drug_name": drug_name,
        "is_high_alert": is_high_alert,
        "matched": norm if is_high_alert else None,
        "note": (
            "Obat ini termasuk dalam daftar high-alert — konfirmasi manual diperlukan sebelum APPROVE."
            if is_high_alert
            else "Obat ini tidak terdeteksi dalam daftar high-alert lokal."
        ),
        "status": "DRAFT_PERLU_VALIDASI_APOTEKER",
    }]


# ---------------------------------------------------------------------------
# POST /api/v1/knowledge/lookup
# ---------------------------------------------------------------------------

@router.post(
    "/lookup",
    response_model=KnowledgeLookupResponse,
    summary="Cari informasi obat dari knowledge base (read-only)",
)
async def lookup_drug_knowledge(body: KnowledgeLookupRequest) -> KnowledgeLookupResponse:
    """
    Cari informasi obat dari knowledge base PrioMed-Rec (hanya baca).

    Jenis pencarian:
    - alias:       normalisasi nama obat (brand → INN)
    - interaction: daftar interaksi obat dikenal di KB
    - allergy:     aturan reaksi silang alergi (DRAFT)
    - high_alert:  apakah obat masuk daftar high-alert

    Semua konten klinis berstatus DRAFT_PERLU_VALIDASI_APOTEKER.
    """
    lookup_type = body.lookup_type.lower().strip()

    if lookup_type == "alias":
        results = _lookup_alias(body.drug_name)
        source = "knowledge/drug_alias.csv"
    elif lookup_type == "interaction":
        results = _lookup_interaction(body.drug_name)
        source = "knowledge/interactions.json"
    elif lookup_type == "allergy":
        results = _lookup_allergy(body.drug_name)
        source = "configs/allergy_rules.json"
    elif lookup_type == "high_alert":
        results = _lookup_high_alert(body.drug_name)
        source = "configs/discrepancy_rules.json"
    else:
        results = []
        source = "unknown"

    return KnowledgeLookupResponse(
        drug_name=body.drug_name,
        lookup_type=lookup_type,
        results=results,
        source=source,
        status="DRAFT_PERLU_VALIDASI_APOTEKER",
        count=len(results),
    )
