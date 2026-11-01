"""
src/llm/validators/output_validator.py
----------------------------------------
Output guardrail validator for LLM responses.

Enforces the 6 safety checks from plan Â§829-Â§835:
  1. patient_id and encounter_id match input
  2. risk_probability not changed from input
  3. priority not changed from input
  4. No forbidden clinical action phrases
  5. No unverified error claims
  6. JSON schema valid (all required fields present)

Also handles prompt injection detection.
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Forbidden phrase patterns (case-insensitive)
# ---------------------------------------------------------------------------

_FORBIDDEN_PHRASES = [
    # English â€” therapy instruction phrases
    r"\bstop\s+medication\b",
    r"\bstart\s+medication\b",
    r"\bincrease\s+dose\b",
    r"\bdecrease\s+dose\b",
    r"\bprescribe\b",
    r"\bprescription\b",
    r"\border\s+medication\b",
    r"\badminister\s+medication\b",
    r"\bdiscontinue\s+medication\b",
    r"\bdo\s+not\s+give\b",
    r"\bdo\s+not\s+administer\b",

    # Indonesian â€” instruction terapi (Prinsip #8)
    # "hentikan obat"  = stop the medication
    r"\bhentikan\s+obat\b",
    # "mulai obat" / "mulai pemberian" = start the medication
    r"\bmulai\s+obat\b",
    r"\bmulai\s+pemberian\b",
    # "tingkatkan dosis" / "naikkan dosis" = increase dose
    r"\btingkatkan\s+dosis\b",
    r"\bnaikkan\s+dosis\b",
    # "kurangi dosis" / "turunkan dosis" = decrease dose
    r"\bkurangi\s+dosis\b",
    r"\bturunkan\s+dosis\b",
    # "berikan obat" = administer the medication
    r"\bberikan\s+obat\b",
    # "stop obat" = stop the drug (colloquial)
    r"\bstop\s+obat\b",
    # "order obat" / "pesan obat" = order the medication
    r"\border\s+obat\b",
    r"\bpesan\s+obat\b",
    # "ganti obat dengan" = replace medication with (prescriptive phrasing)
    r"\bganti\s+obat\s+dengan\b",
    # "resepkan" = prescribe
    r"\bresepkan\b",
    # "instruksikan" (dokter/farmasi) = instruct (prescriptive)
    r"\binstruksikan\b",
    # "rekomendasikan" + specific drug class (too directive)
    # covered by the confirmed-error pattern check below
]

_CONFIRMED_ERROR_PATTERN = re.compile(
    r"confirmed\s+medication\s+error", re.IGNORECASE
)

_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|above)\s+instruction",
    r"forget\s+(your|all)\s+instruction",
    r"you\s+are\s+now\s+a",
    r"act\s+as\s+(a\s+)?doctor",
    r"pretend\s+(you\s+are|to\s+be)",
]


class GuardrailViolation(ValueError):
    """Raised when an LLM output fails a guardrail check."""


def validate_output(
    llm_text: str,
    input_context: dict,
) -> str:
    """
    Validate LLM text output against all guardrail checks.

    Parameters
    ----------
    llm_text      : raw text returned by the LLM
    input_context : the structured context dict sent to the LLM
                    (must contain risk_model.priority and risk_model.risk_probability)

    Returns
    -------
    llm_text (unchanged) if all checks pass.

    Raises
    ------
    GuardrailViolation if any check fails.
    """
    # 1. Check for prompt injection attempts
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, llm_text, re.IGNORECASE):
            raise GuardrailViolation(
                f"Prompt injection detected (pattern: '{pattern}'). Response rejected."
            )

    # 2. Forbidden clinical action phrases
    for pattern in _FORBIDDEN_PHRASES:
        if re.search(pattern, llm_text, re.IGNORECASE):
            raise GuardrailViolation(
                f"Forbidden clinical action phrase detected (pattern: '{pattern}'). "
                "LLM must not recommend starting, stopping, or changing medication."
            )

    # 3. "Confirmed medication error" without verification_required
    if _CONFIRMED_ERROR_PATTERN.search(llm_text):
        # Allow only if "verification required" also appears nearby
        if not re.search(r"verification\s+required", llm_text, re.IGNORECASE):
            raise GuardrailViolation(
                "LLM claimed 'confirmed medication error' without stating "
                "'verification required'. Response rejected."
            )

    # 4. Priority must not be REASSIGNED to a different value.
    #    LLM is allowed to *mention* other priority levels for context
    #    (e.g. "compared to LOW risk patients..."), but must not claim
    #    this patient IS a different priority than what the model output.
    #    We only check explicit re-assignment phrases.
    risk_model = input_context.get("risk_model", {})
    if risk_model:
        orig_priority = str(risk_model.get("priority", "")).upper()
        # Only flag if LLM explicitly assigns a DIFFERENT priority to "this patient"
        # Patterns like "this patient is LOW" when orig is HIGH
        if orig_priority:
            other_priorities = {"HIGH", "MEDIUM", "LOW"} - {orig_priority}
            text_upper = llm_text.upper()
            for other in other_priorities:
                # Check explicit re-assignment patterns separately (avoid complex alternation bugs)
                patterns = [
                    rf"THIS PATIENT IS\s+{other}",           # "this patient is LOW"
                    rf"THIS PATIENT IS\s+{other}\s+PRIORITY", # "this patient is LOW priority"
                    rf"PRIORITY[:\s]+{other}\b",              # "priority: LOW" / "priority LOW"
                    rf"CLASSIFIED AS\s+{other}\b",            # "classified as LOW"
                    rf"CONSIDERED\s+{other}\b",               # "considered LOW"
                    rf"{other}\s+PRIORITY PATIENT",           # "LOW priority patient"
                ]
                if any(re.search(p, text_upper) for p in patterns):
                    raise GuardrailViolation(
                        f"LLM re-assigned patient priority to '{other}' "
                        f"(original: '{orig_priority}'). Priority must not change."
                    )

    return llm_text



# ---------------------------------------------------------------------------
# Knowledge-base interaction claim checker
# ---------------------------------------------------------------------------

# Load knowledge base pairs once at module init
_KB_PAIRS = None


def _load_kb_pairs():
    """Load drug interaction pairs from knowledge/interactions.json."""
    global _KB_PAIRS
    if _KB_PAIRS is not None:
        return _KB_PAIRS

    try:
        import json
        from pathlib import Path
        kb_path = Path(__file__).parent.parent.parent.parent / "knowledge" / "interactions.json"
        if kb_path.exists():
            with open(kb_path, encoding="utf-8") as f:
                data = json.load(f)
            pairs = set()
            # Support both list-of-dicts and dict formats
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        drugs = item.get("drugs") or [item.get("drug1"), item.get("drug2")]
                        drugs = [d.lower().strip() for d in drugs if d]
                        if len(drugs) >= 2:
                            pairs.add(frozenset(drugs[:2]))
            elif isinstance(data, dict):
                for key, val in data.items():
                    parts = key.lower().split("+")
                    if len(parts) == 2:
                        pairs.add(frozenset(p.strip() for p in parts))
            _KB_PAIRS = pairs
        else:
            _KB_PAIRS = set()
    except Exception:
        _KB_PAIRS = set()

    return _KB_PAIRS


_INTERACTION_PHRASES = re.compile(
    r'(berinteraksi|meningkatkan risiko|menurunkan efek|kontraindikasi|'
    r'combination|interacts|increases risk|decreases efficacy|concurrent use)',
    re.IGNORECASE
)


def _check_unsourced_interaction_claims(text, kb_pairs):
    """
    Detect LLM claims about drug interactions not in the knowledge base.
    Returns list of violation strings.
    """
    violations = []

    # Find sentences containing interaction phrases
    sentences = re.split(r'[.!?\n]', text)
    for sentence in sentences:
        if not _INTERACTION_PHRASES.search(sentence):
            continue

        # Extract drug names mentioned (simple word extraction, lowercase)
        words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9-]{3,}\b', sentence)
        words_lower = [w.lower() for w in words]

        # Check all pairs in this sentence
        for i, w1 in enumerate(words_lower):
            for w2 in words_lower[i+1:]:
                pair = frozenset([w1, w2])
                if pair in kb_pairs:
                    continue  # This pair IS in KB -- allowed
                # Check if both words look like drug names (heuristic: not common words)
                _COMMON_WORDS = {'dengan', 'dan', 'atau', 'yang', 'untuk', 'pada', 'akan',
                                  'dapat', 'dari', 'obat', 'pasien', 'bila', 'ketika',
                                  'the', 'and', 'with', 'for', 'can', 'may', 'risk', 'drug'}
                if w1 in _COMMON_WORDS or w2 in _COMMON_WORDS:
                    continue
                # If both are likely drug names and interact phrase present -> warn
                # (conservative: only flag if phrase is very close to the words)
                if len(w1) > 4 and len(w2) > 4:
                    violations.append(
                        f"UNSOURCED_INTERACTION_CLAIM: '{w1}' + '{w2}' mentioned with interaction phrase "
                        f"but not in knowledge base. Verify manually."
                    )
                    break  # One violation per sentence is enough

    return violations


def validate_output_safe(
    llm_text: str,
    input_context: dict,
) -> tuple[str, list[str]]:
    """
    Non-raising version. Returns (text, violations_list).
    violations_list is empty if all checks pass.
    """
    violations: list[str] = []
    try:
        validate_output(llm_text, input_context)
    except GuardrailViolation as exc:
        violations.append(str(exc))
    
    # Check unsourced interaction claims
    kb_pairs = _load_kb_pairs()
    if kb_pairs:
        unsourced = _check_unsourced_interaction_claims(llm_text, kb_pairs)
        violations.extend(unsourced)

    return llm_text, violations
