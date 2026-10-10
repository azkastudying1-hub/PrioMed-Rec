"""
src/llm/service.py
-------------------
LLM integration service for PrioMed-Rec.

Connects to hosted LLM API (Gemini / Groq / Mistral / OpenAI-compatible)
via environment variables. Provides 4 task functions:
  - generate_summary()
  - explain_risk()
  - explain_discrepancy()
  - answer_query()

Every function:
  1. Builds the task-specific prompt
  2. Calls the LLM API with automatic fallback chain
  3. Runs output through the guardrail validator
  4. Returns the validated text

Clinical safety:
  - LLM NEVER recomputes risk_probability or priority — these come from ML only.
  - All LLM output is validated by output_validator before returning.
  - If ALL providers fail, a safe fallback message is returned.
  - API keys are read from .env — never hardcoded.

Fallback Chain (automatic, configured via .env):
  1. Primary  : LLM_PROVIDER / LLM_API_KEY / LLM_MODEL_NAME
  2. Gemini-2 : LLM_FALLBACK_MODEL (second Gemini model, same key, different quota bucket)
  3. Groq     : LLM_GROQ_API_KEY (free, no strict daily limit)

On 429 quota error → immediately skip to next (no retry waste)
On 503 transient   → up to 3 retries with back-off, then skip to next
On auth error      → fail fast (wrong key = no point retrying)

Environment variables (.env):
  LLM_PROVIDER          = gemini | groq | mistral | openai
  LLM_API_KEY           = <primary API key>
  LLM_MODEL_NAME        = gemini-2.5-flash
  LLM_BASE_URL          = (optional, for Groq/Mistral/custom)
  LLM_FALLBACK_MODEL    = gemini-1.5-flash-8b  (optional second Gemini model)
  LLM_GROQ_API_KEY      = (optional Groq key — automatic last-resort fallback)
  LLM_GROQ_MODEL        = llama-3.3-70b-versatile (default)

SDK used:
  gemini  → google-genai>=1.0.0  (new official SDK)
  others  → openai>=1.0.0        (openai-compatible)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Load .env automatically so LLM_API_KEY is available at import time
try:
    from dotenv import load_dotenv as _load_dotenv
    _env = Path(__file__).parent.parent.parent / ".env"
    if _env.exists():
        _load_dotenv(_env)
except ImportError:
    pass

from src.llm.prompts.task_prompts import (
    patient_summary_prompt,
    risk_explanation_prompt,
    discrepancy_explanation_prompt,
    pharmacist_qa_prompt,
    _system_prompt,
)
from src.llm.validators.output_validator import validate_output_safe


# ---------------------------------------------------------------------------
# Custom exception — raised by _safe_call so callers can catch cleanly
# ---------------------------------------------------------------------------

class LLMError(RuntimeError):
    """Raised when the LLM call fails or output is blocked by guardrails."""


# ---------------------------------------------------------------------------
# Unavailable / safe fallback message
# ---------------------------------------------------------------------------

_LLM_UNAVAILABLE_MSG = (
    "LLM service is currently unavailable. "
    "Please review the structured data provided by the prioritization and discrepancy systems. "
    "Pharmacist verification is required for all flagged items."
)


# ---------------------------------------------------------------------------
# Error-type detection helpers
# ---------------------------------------------------------------------------

def _is_quota_error(exc: Exception) -> bool:
    """True if the error is a quota / rate-limit error (HTTP 429)."""
    s = str(exc).upper()
    return any(k in s for k in (
        "429", "RESOURCE_EXHAUSTED", "QUOTA_EXCEEDED", "QUOTA EXCEEDED",
        "EXCEEDED YOUR CURRENT QUOTA", "RATE_LIMIT_EXCEEDED", "RATE LIMIT",
        "TOO MANY REQUESTS",
    ))


def _is_transient_error(exc: Exception) -> bool:
    """True if the error is a temporary server-side error (HTTP 503 etc.)."""
    s = str(exc).upper()
    return any(k in s for k in (
        "503", "UNAVAILABLE", "HIGH DEMAND", "OVERLOADED",
        "502", "504", "INTERNAL", "SERVICE_UNAVAILABLE",
    ))


def _reload_env() -> None:
    """Re-read .env so live edits take effect without server restart."""
    try:
        from dotenv import load_dotenv as _ld
        for _c in [
            Path(__file__).resolve().parent.parent.parent / ".env",
            Path.cwd() / ".env",
        ]:
            if _c.exists():
                _ld(_c, override=True)
                break
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Single-provider call helpers
# ---------------------------------------------------------------------------

def _call_gemini(api_key: str, model: str, system: str, user: str) -> str:
    """
    Call Gemini via google-genai SDK.
    - Retries up to 3× on 503/transient errors with exponential back-off.
    - Raises RuntimeError immediately on 429 quota errors (no point retrying).
    """
    import time

    try:
        from google import genai as google_genai       # type: ignore
        from google.genai import types as genai_types  # type: ignore
    except ImportError:
        raise RuntimeError(
            "google-genai package not installed. Run: pip install google-genai>=1.0.0"
        )

    client = google_genai.Client(api_key=api_key)

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=user,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.2,
                    max_output_tokens=4096,
                ),
            )
            if not response.text:
                finish = (
                    response.candidates[0].finish_reason
                    if response.candidates else "unknown"
                )
                raise RuntimeError(
                    f"Gemini returned empty response. Finish reason: {finish}"
                )
            return response.text

        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            # Quota errors → fail fast, let the fallback chain handle it
            if _is_quota_error(exc):
                raise RuntimeError(f"Gemini API error: {exc}") from exc
            # Transient → retry with back-off
            if _is_transient_error(exc) and attempt < 2:
                wait = 2 * (attempt + 1)
                print(
                    f"[LLM] Gemini transient error (attempt {attempt+1}/3), "
                    f"retrying in {wait}s… {exc}",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue
            raise RuntimeError(f"Gemini API error: {exc}") from exc

    raise RuntimeError(f"Gemini API error after retries: {last_exc}") from last_exc


def _call_openai_compat(
    api_key: str,
    model: str,
    system: str,
    user: str,
    base_url: str = "",
) -> str:
    """
    Call any OpenAI-compatible API (Groq, Mistral, OpenAI, etc.).
    Raises RuntimeError on failure.
    """
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        raise RuntimeError(
            "openai package not installed. Run: pip install openai>=1.0.0"
        )

    client = OpenAI(api_key=api_key, base_url=base_url or None)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature=0.2,
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        raise RuntimeError(f"OpenAI-compat API error: {exc}") from exc


# ---------------------------------------------------------------------------
# Main LLM call — automatic fallback chain
# ---------------------------------------------------------------------------

def _call_llm(system: str, user: str) -> str:
    """
    Call the configured LLM with an automatic 3-step fallback chain.

    Chain:
      1. Primary  : LLM_PROVIDER + LLM_API_KEY + LLM_MODEL_NAME
      2. Gemini-2 : same key + LLM_FALLBACK_MODEL (different quota bucket)
      3. Groq     : LLM_GROQ_API_KEY + LLM_GROQ_MODEL (free, generous limit)

    Errors collected; final RuntimeError lists all failures if chain exhausted.
    """
    _reload_env()

    provider       = os.getenv("LLM_PROVIDER", "").lower().strip()
    api_key        = os.getenv("LLM_API_KEY", "").strip()
    model_name     = os.getenv("LLM_MODEL_NAME", "gemini-2.5-flash").strip()
    base_url       = os.getenv("LLM_BASE_URL", "").strip()
    fallback_model = os.getenv("LLM_FALLBACK_MODEL", "").strip()
    groq_key       = os.getenv("LLM_GROQ_API_KEY", "").strip()
    groq_model     = os.getenv("LLM_GROQ_MODEL", "llama-3.3-70b-versatile").strip()

    if not api_key:
        raise RuntimeError("LLM_API_KEY not set in .env.")
    if not provider:
        raise RuntimeError(
            "LLM_PROVIDER not set in .env. Supported: gemini, groq, openai, mistral."
        )

    errors: list[str] = []

    # ── Step 1: primary provider ──────────────────────────────────────────
    try:
        if provider == "gemini":
            return _call_gemini(api_key, model_name, system, user)
        elif provider in ("groq", "openai", "mistral"):
            eff_url = base_url
            if provider == "groq" and not eff_url:
                eff_url = "https://api.groq.com/openai/v1"
            return _call_openai_compat(api_key, model_name, system, user, eff_url)
        else:
            raise RuntimeError(
                f"Unknown LLM_PROVIDER='{provider}'. "
                "Supported: gemini, groq, openai, mistral."
            )
    except Exception as exc:  # noqa: BLE001
        err_msg = str(exc)
        errors.append(f"[{provider.upper()} primary / {model_name}] {err_msg}")
        # Non-retriable errors (bad API key, auth failure) → fail fast
        if not (_is_quota_error(exc) or _is_transient_error(exc)):
            # Check for auth-related keywords
            s = err_msg.upper()
            if any(k in s for k in ("401", "403", "INVALID_API_KEY", "API_KEY_INVALID",
                                     "PERMISSION_DENIED", "UNAUTHORIZED")):
                raise RuntimeError(
                    f"LLM authentication failed — check LLM_API_KEY in .env.\n{err_msg}"
                ) from exc
        print(
            f"[LLM] Primary provider failed (quota/transient), trying fallback chain… {err_msg}",
            file=sys.stderr,
        )

    # ── Step 2: Gemini fallback model (same key, different quota bucket) ──
    if provider == "gemini" and fallback_model and fallback_model != model_name:
        try:
            result = _call_gemini(api_key, fallback_model, system, user)
            print(
                f"[LLM] ✓ Used Gemini fallback model: {fallback_model}",
                file=sys.stderr,
            )
            return result
        except Exception as exc:  # noqa: BLE001
            errors.append(f"[GEMINI fallback / {fallback_model}] {exc}")
            print(
                f"[LLM] Gemini fallback model '{fallback_model}' also failed: {exc}",
                file=sys.stderr,
            )

    # ── Step 3: Groq fallback (free, generous daily quota) ────────────────
    if groq_key:
        try:
            result = _call_openai_compat(
                groq_key, groq_model, system, user,
                "https://api.groq.com/openai/v1",
            )
            print(
                f"[LLM] ✓ Used Groq fallback: {groq_model}",
                file=sys.stderr,
            )
            return result
        except Exception as exc:  # noqa: BLE001
            errors.append(f"[GROQ fallback / {groq_model}] {exc}")
            print(
                f"[LLM] Groq fallback also failed: {exc}",
                file=sys.stderr,
            )

    # ── All providers exhausted ───────────────────────────────────────────
    chain_summary = "\n  • ".join(errors)
    raise RuntimeError(
        f"Semua LLM provider gagal:\n  • {chain_summary}\n\n"
        "💡 Solusi cepat — tambahkan di .env:\n"
        "  LLM_FALLBACK_MODEL=gemini-1.5-flash-8b\n"
        "  LLM_GROQ_API_KEY=<key gratis dari https://console.groq.com>\n"
        "  LLM_GROQ_MODEL=llama-3.3-70b-versatile"
    )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def generate_summary(context: dict) -> str:
    """
    Generate a patient admission summary for pharmacist review.

    Parameters
    ----------
    context : LLM input contract dict (§23 PROJECT_CONTEXT)

    Returns
    -------
    Validated summary text (SBAR format).
    """
    system = _system_prompt()
    user   = patient_summary_prompt(context)
    return _safe_call(system, user, context)


def explain_risk(context: dict) -> str:
    """
    Explain why the patient received their risk score/priority.

    Parameters
    ----------
    context : must contain risk_model.risk_probability, risk_model.priority,
              explainability.top_features

    Returns
    -------
    Validated risk explanation text.
    """
    system = _system_prompt()
    user   = risk_explanation_prompt(context)
    return _safe_call(system, user, context)


def explain_discrepancy(context: dict) -> str:
    """
    Explain the medication discrepancy flags from the rule engine.

    Parameters
    ----------
    context : must contain discrepancy_engine.flags

    Returns
    -------
    Validated discrepancy explanation text.
    """
    system = _system_prompt()
    user   = discrepancy_explanation_prompt(context)
    return _safe_call(system, user, context)


def answer_query(question: str, context: dict) -> str:
    """
    Answer a pharmacist question grounded in the structured context.

    Parameters
    ----------
    question : natural-language question from pharmacist
    context  : structured patient + risk + discrepancy context

    Returns
    -------
    Validated answer text.
    """
    system = _system_prompt()
    user   = pharmacist_qa_prompt(question, context)
    return _safe_call(system, user, context)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _safe_call(system: str, user: str, input_context: dict) -> str:
    """
    Call LLM and validate output. Raises LLMError on failure so the caller
    can distinguish a real LLM response from an error condition.
    """
    try:
        raw = _call_llm(system, user)
    except Exception as exc:  # noqa: BLE001
        raise LLMError(
            "LLM service unavailable. Please review the structured data above. "
            "Pharmacist judgment is required for all clinical decisions. "
            f"[Error: {type(exc).__name__}: {exc}]"
        ) from exc

    text, violations = validate_output_safe(raw, input_context)
    if violations:
        raise LLMError(
            "LLM response was blocked by safety guardrails. "
            f"Violations: {'; '.join(violations)}"
        )
    return text
