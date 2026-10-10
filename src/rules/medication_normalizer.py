"""
src/rules/medication_normalizer.py
------------------------------------
Medication normalization utilities for the discrepancy engine.

Normalization strategy (from configs/discrepancy_rules.json):
  Primary key : medication_code (RxNorm) — preferred if not null
  Fallback    : normalized_name — lowercase, stripped, no dosage strings
  Unresolved  : returns UNRESOLVED_MEDICATION_MATCH flag if match is unsafe

Clinical safety note (PROJECT_CONTEXT §12):
  Two medications must NOT be equated solely because their names look similar.
  If normalization cannot be done safely, the UNRESOLVED flag is raised for
  pharmacist review.
"""

from __future__ import annotations

import re
from typing import Tuple

UNRESOLVED_FLAG = "UNRESOLVED_MEDICATION_MATCH"

# Patterns to strip from medication names when falling back to name matching
# (e.g. "Metformin 500 MG" → "metformin")
_DOSAGE_PATTERN = re.compile(
    r"\s+\d+\.?\d*\s*(mg|mcg|ml|g|iu|meq|mmol|unit|units|%)[^a-z]*",
    flags=re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    """
    Lowercase, strip whitespace, and optionally remove dosage strings.
    Used as fallback key when medication_code is null.
    """
    if not name or not isinstance(name, str):
        return ""
    cleaned = _DOSAGE_PATTERN.sub("", name).strip().lower()
    # Collapse multiple spaces
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned


def normalize_medication(
    name: str | None,
    code: str | None,
) -> Tuple[str, bool]:
    """
    Return a (normalized_key, is_resolved) tuple.

    Priority:
      1. If medication_code is non-null and non-empty → use it as key
      2. Else fall back to normalize_name(name)
      3. If both are empty/null → return (UNRESOLVED_FLAG, False)

    Parameters
    ----------
    name : str or None
        Raw medication display name.
    code : str or None
        RxNorm or other coding-system code.

    Returns
    -------
    (key: str, is_resolved: bool)
        is_resolved=False signals that downstream code should emit
        UNRESOLVED_MEDICATION_MATCH rather than making a comparison.
    """
    if code and str(code).strip():
        return str(code).strip(), True

    if name and str(name).strip():
        normalized = normalize_name(str(name))
        if normalized:
            return normalized, True

    return UNRESOLVED_FLAG, False


def build_medication_index(
    df: "pd.DataFrame",
    code_col: str = "medication_code",
    name_col: str = "medication_name",
) -> "pd.DataFrame":
    """
    Add `norm_key` and `is_resolved` columns to a medication DataFrame.
    Used by the discrepancy engine to build identity keys before comparison.
    """
    import pandas as pd

    results = [
        normalize_medication(
            None if pd.isna(row.get(name_col)) else row.get(name_col),
            None if pd.isna(row.get(code_col)) else row.get(code_col),
        )
        for _, row in df.iterrows()
    ]
    keys, resolved = zip(*results) if results else ([], [])
    out = df.copy()
    out["norm_key"] = list(keys)
    out["is_resolved"] = list(resolved)
    return out
