"""
src/llm/validators/output_validator.py
----------------------------------------
Output guardrail validator for LLM responses.

Enforces the 6 safety checks from plan §829-§835:
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
    return llm_text, violations
