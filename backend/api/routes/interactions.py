"""
api/routes/interactions.py
---------------------------
POST /interactions/check  — lookup drug pair in curated KB (interactions.json)
POST /interactions/safety — ISMP high-alert / NTI / Beers PIM flags per admission list

Clinical safety rules (Project Principles 5, 6, 7):
  - ONLY returns entries from the internal curated knowledge base
  - If pair not found: explicit "no entry" message (NOT "no interaction")
  - LLM NEVER invents interaction claims — source must be in interactions.json
  - Every card shows: reason, monitoring, source, source_url, year, status
  - "NEEDS_PHARMACIST_REVIEW" or "CANDIDATE" on every result — never a final verdict
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()

_KB_PATH = Path("knowledge/interactions.json")

# Lazy-loaded KB cache
_kb_cache: list[dict] | None = None


def _load_kb() -> list[dict]:
    global _kb_cache
    if _kb_cache is None:
        if not _KB_PATH.exists():
            _kb_cache = []
        else:
            with open(_KB_PATH, encoding="utf-8") as f:
                _kb_cache = json.load(f)
    return _kb_cache


def _normalize(name: str) -> str:
    return name.lower().strip()


def _pair_matches(entry: dict, a: str, b: str) -> bool:
    """Check if a KB entry matches a drug pair (order-insensitive, substring)."""
    da = _normalize(entry.get("drug_a", ""))
    db = _normalize(entry.get("drug_b", ""))
    na, nb = _normalize(a), _normalize(b)
    return (
        (na in da or da in na) and (nb in db or db in nb)
    ) or (
        (nb in da or da in nb) and (na in db or db in na)
    )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class InteractionCheckRequest(BaseModel):
    drugs: List[str] = Field(
        ...,
        min_length=2,
        description="List of drug names to check pairwise. Minimum 2 drugs required."
    )


class InteractionEntry(BaseModel):
    drug_a:     str
    drug_b:     str
    reason:     str
    monitoring: str
    source:     str
    source_url: Optional[str] = None
    year:       int
    status:     str = "NEEDS_PHARMACIST_REVIEW"
    found_in_kb: bool = True


class InteractionCheckResponse(BaseModel):
    drugs_checked:       List[str]
    pairs_checked:       int
    entries_found:       int
    interactions:        List[InteractionEntry]
    kb_version:          str
    no_entry_disclaimer: str


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/interactions/check",
    response_model=InteractionCheckResponse,
    tags=["interactions"],
    summary="Check drug pairs against curated interaction knowledge base",
)
def check_interactions(request: InteractionCheckRequest) -> InteractionCheckResponse:
    """
    Check a list of drugs pairwise against the internal curated interaction KB.

    **Important disclaimers (displayed in every response):**
    - A result NOT found in KB does NOT mean the combination is safe.
    - This KB is a small demo set (~10 entries). Full interaction checking
      requires reference to Martindale, Micromedex, or Lexicomp.
    - Every entry carries status=NEEDS_PHARMACIST_REVIEW — never a final verdict.
    - Source is cited on every entry. LLM never invents interaction claims.
    """
    kb = _load_kb()
    drugs = request.drugs
    found: list[InteractionEntry] = []

    # Generate all pairs
    pairs_checked = 0
    for i in range(len(drugs)):
        for j in range(i + 1, len(drugs)):
            pairs_checked += 1
            a, b = drugs[i], drugs[j]
            for entry in kb:
                if _pair_matches(entry, a, b):
                    found.append(InteractionEntry(
                        drug_a=entry["drug_a"],
                        drug_b=entry["drug_b"],
                        reason=entry["reason"],
                        monitoring=entry["monitoring"],
                        source=entry["source"],
                        source_url=entry.get("source_url"),
                        year=entry["year"],
                        status=entry.get("status", "NEEDS_PHARMACIST_REVIEW"),
                        found_in_kb=True,
                    ))

    return InteractionCheckResponse(
        drugs_checked=drugs,
        pairs_checked=pairs_checked,
        entries_found=len(found),
        interactions=found,
        kb_version="interactions-v0.1.0-demo",
        no_entry_disclaimer=(
            "Pasangan obat yang tidak ditemukan di basis pengetahuan demo ini BUKAN berarti "
            "tidak ada interaksi klinis. Basis pengetahuan ini hanya mencakup ~10 entri pilihan "
            "untuk keperluan demonstrasi. Gunakan referensi institusi (Martindale, Micromedex, "
            "Lexicomp, atau MIMS) untuk verifikasi interaksi yang komprehensif."
        ),
    )


# ---------------------------------------------------------------------------
# POST /interactions/safety — ISMP high-alert / NTI / Beers PIM flags
# ---------------------------------------------------------------------------

class SafetyMedItem(BaseModel):
    medication_name: str

class SafetyFlagsRequest(BaseModel):
    medications: List[SafetyMedItem] = Field(
        ..., description="Admission medication list from BPMH"
    )
    patient_age: Optional[int] = Field(
        None, description="Patient age in years (required for Beers PIM gate ≥65)"
    )

class SafetyFlagEntry(BaseModel):
    flag_type: str
    drug_name: str
    category: str
    route: str
    source: str
    source_version: str
    source_url: str
    status: str = "CANDIDATE"
    verification_required: bool = True
    beers_note: Optional[str] = None
    age_threshold: Optional[int] = None

class SafetyFlagsResponse(BaseModel):
    flags: List[SafetyFlagEntry]
    high_alert_count: int
    nti_count: int
    beers_pim_count: int
    total_flag_count: int
    lookup_version: str
    source_versions: Dict[str, Any]


@router.post(
    "/interactions/safety",
    response_model=SafetyFlagsResponse,
    tags=["interactions"],
    summary="Check admission medication list for ISMP high-alert, NTI, and Beers PIM flags",
)
def check_safety_flags(request: SafetyFlagsRequest) -> SafetyFlagsResponse:
    """
    Stage 2 (post-BPMH) safety flags from three evidence-based registries:
      - ISMP High-Alert Medications (Acute Care, 2024)
      - FDA Narrow Therapeutic Index (NTI) drugs
      - AGS Beers Criteria 2023 PIM (age ≥ 65 only)

    Every flag carries source, source_version, source_url, status=CANDIDATE,
    and verification_required=True — never a confirmed clinical verdict.

    Returns empty flags list (not an error) for drugs not found in the lookup.
    """
    from src.rules.safety_flags_engine import check_medication_list

    drug_names = [m.medication_name for m in request.medications if m.medication_name.strip()]
    result = check_medication_list(drug_names, patient_age=request.patient_age)

    return SafetyFlagsResponse(
        flags=[SafetyFlagEntry(**f) for f in result["flags"]],
        high_alert_count=result["high_alert_count"],
        nti_count=result["nti_count"],
        beers_pim_count=result["beers_pim_count"],
        total_flag_count=result["total_flag_count"],
        lookup_version=result["lookup_version"],
        source_versions=result["source_versions"],
    )
