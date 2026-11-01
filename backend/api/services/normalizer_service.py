"""
api/services/normalizer_service.py
------------------------------------
Normalizer obat 5 tahap (B-111).

Tahap:
  1. Exact match     — cocok persis dengan drug_alias.csv (case-insensitive)
  2. Alias match     — cocok dengan known alias/brand names
  3. Fuzzy match     — RapidFuzz similarity ≥ 80% (rapidfuzz)
  4. KFA/RxNorm stub — placeholder untuk integrasi BPOM KFA (belum aktif)
  5. Unresolved      — masuk antrian "tak dikenali" untuk review apoteker

PERINGATAN: confidence rendah ≠ "aman". Obat yang tidak dikenali TIDAK boleh
diasumsikan aman — harus masuk antrian review.

Status: DRAFT_PERLU_VALIDASI_APOTEKER (S10)
Owner: TBD-apoteker
"""

from __future__ import annotations

import csv
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Load drug alias table
# ---------------------------------------------------------------------------

_ALIAS_CSV_PATH = Path(__file__).parent.parent.parent / "knowledge" / "drug_alias.csv"


@lru_cache(maxsize=1)
def _load_alias_table() -> Dict[str, Dict]:
    """
    Load drug_alias.csv into dict keyed by brand_name (lowercase, stripped).
    Returns: {brand_lower: {generic_name, atc_code, drug_class, is_high_alert, confidence}}
    """
    table: Dict[str, Dict] = {}
    if not _ALIAS_CSV_PATH.exists():
        return table

    try:
        with open(_ALIAS_CSV_PATH, encoding="utf-8", newline="") as fh:
            # Filter out comment lines before passing to DictReader
            lines = [ln for ln in fh if not ln.strip().startswith("#") and ln.strip()]
        import io
        reader = csv.DictReader(io.StringIO("".join(lines)))
        for row in reader:
            brand = row.get("brand_name", "").strip().lower()
            if brand and not brand.startswith("#"):
                try:
                    table[brand] = {
                        "generic_name": row.get("generic_name", "").strip(),
                        "atc_code": row.get("atc_code", "").strip(),
                        "drug_class": row.get("drug_class", "").strip(),
                        "is_high_alert": row.get("is_high_alert", "false").lower() in ("true", "1", "yes"),
                        "confidence": float(row.get("confidence", "1.0")),
                        "source": row.get("source", "manual"),
                        "status": row.get("status", "DRAFT_PERLU_VALIDASI_APOTEKER"),
                    }
                except (ValueError, TypeError):
                    pass
    except Exception:
        pass
    return table


def reload_alias_table() -> int:
    """Force reload of alias table (call after CSV update). Returns count."""
    _load_alias_table.cache_clear()
    return len(_load_alias_table())


# ---------------------------------------------------------------------------
# Normalize result dataclass
# ---------------------------------------------------------------------------

class NormalizeResult:
    """Hasil normalisasi satu nama obat."""
    __slots__ = (
        "drug_name_raw", "drug_name_normalized", "drug_generic",
        "drug_atc", "drug_class", "is_high_alert",
        "method", "confidence", "status",
    )

    def __init__(
        self,
        drug_name_raw: str,
        drug_name_normalized: str,
        drug_generic: str,
        drug_atc: Optional[str],
        drug_class: Optional[str],
        is_high_alert: bool,
        method: str,
        confidence: float,
        status: str,
    ):
        self.drug_name_raw = drug_name_raw
        self.drug_name_normalized = drug_name_normalized
        self.drug_generic = drug_generic
        self.drug_atc = drug_atc
        self.drug_class = drug_class
        self.is_high_alert = is_high_alert
        self.method = method          # exact | alias | fuzzy | kfa | unresolved
        self.confidence = confidence  # 0.0..1.0
        self.status = status          # ok | draft | unresolved

    def to_dict(self) -> Dict:
        return {k: getattr(self, k) for k in self.__slots__}


# ---------------------------------------------------------------------------
# 5-stage normalization pipeline
# ---------------------------------------------------------------------------

def normalize_drug_name(raw: str) -> NormalizeResult:
    """
    Normalisasi satu nama obat melalui 5 tahap.
    Confidence rendah (< 0.7) ditandai sebagai 'draft', TIDAK dianggap aman.
    """
    if not raw or not raw.strip():
        return NormalizeResult(
            drug_name_raw=raw, drug_name_normalized="", drug_generic="",
            drug_atc=None, drug_class=None, is_high_alert=False,
            method="unresolved", confidence=0.0, status="unresolved",
        )

    clean = raw.strip()
    key = clean.lower()
    table = _load_alias_table()

    # -----------------------------------------------------------------------
    # Tahap 1: Exact match (case-insensitive)
    # -----------------------------------------------------------------------
    if key in table:
        entry = table[key]
        return NormalizeResult(
            drug_name_raw=raw,
            drug_name_normalized=entry["generic_name"] or clean,
            drug_generic=entry["generic_name"],
            drug_atc=entry["atc_code"] or None,
            drug_class=entry["drug_class"] or None,
            is_high_alert=entry["is_high_alert"],
            method="exact",
            confidence=entry["confidence"],
            status="ok" if entry["confidence"] >= 0.9 else "draft",
        )

    # -----------------------------------------------------------------------
    # Tahap 2: Alias — remove parenthetical, dosage, common suffixes
    # -----------------------------------------------------------------------
    import re
    alias_key = re.sub(r"\s*\(.*?\)", "", key)          # remove (...)
    alias_key = re.sub(r"\s+\d+\s*(mg|ml|mcg|iu|g)\b", "", alias_key)  # remove dose
    alias_key = alias_key.strip()
    if alias_key != key and alias_key in table:
        entry = table[alias_key]
        return NormalizeResult(
            drug_name_raw=raw,
            drug_name_normalized=entry["generic_name"] or clean,
            drug_generic=entry["generic_name"],
            drug_atc=entry["atc_code"] or None,
            drug_class=entry["drug_class"] or None,
            is_high_alert=entry["is_high_alert"],
            method="alias",
            confidence=min(entry["confidence"], 0.9),
            status="draft",
        )

    # -----------------------------------------------------------------------
    # Tahap 3: Fuzzy match (RapidFuzz)
    # -----------------------------------------------------------------------
    try:
        from rapidfuzz import process as rf_process, fuzz
        if table:
            candidates = list(table.keys())
            result = rf_process.extractOne(
                key, candidates,
                scorer=fuzz.WRatio,
                score_cutoff=80,
            )
            if result:
                best_key, score, _ = result
                entry = table[best_key]
                confidence = round(score / 100.0, 3)
                return NormalizeResult(
                    drug_name_raw=raw,
                    drug_name_normalized=entry["generic_name"] or best_key,
                    drug_generic=entry["generic_name"],
                    drug_atc=entry["atc_code"] or None,
                    drug_class=entry["drug_class"] or None,
                    is_high_alert=entry["is_high_alert"],
                    method="fuzzy",
                    confidence=confidence * 0.85,  # Discount fuzzy confidence
                    status="draft",
                )
    except ImportError:
        pass

    # -----------------------------------------------------------------------
    # Tahap 4: KFA/RxNorm stub (tidak aktif — siap untuk integrasi)
    # -----------------------------------------------------------------------
    # kfa_result = _lookup_kfa(key)  # TODO: implement when BPOM KFA API available
    # if kfa_result: return kfa_result

    # -----------------------------------------------------------------------
    # Tahap 5: Unresolved — masuk antrian review
    # -----------------------------------------------------------------------
    return NormalizeResult(
        drug_name_raw=raw,
        drug_name_normalized=clean,  # Return as-is
        drug_generic="",
        drug_atc=None,
        drug_class=None,
        is_high_alert=False,  # Tidak aman! Harus diverifikasi apoteker
        method="unresolved",
        confidence=0.0,
        status="unresolved",
    )


def normalize_batch(drug_names: List[str]) -> List[NormalizeResult]:
    """Normalisasi daftar nama obat."""
    return [normalize_drug_name(name) for name in drug_names]
