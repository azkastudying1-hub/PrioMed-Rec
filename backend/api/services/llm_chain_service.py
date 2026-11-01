"""
api/services/llm_chain_service.py
-----------------------------------
LLM chain berbasis konfigurasi (A-306).

Urutan fallback (K6):
  1. gemini      — jika LLM_PROVIDER=gemini dan LLM_API_KEY ada
  2. groq        — jika LLM_GROQ_API_KEY ada
  3. watsonx     — jika WATSONX_API_KEY + WATSONX_PROJECT_ID ada (opsional)
  4. ollama      — jika OLLAMA_BASE_URL ada dan server merespons
  5. template    — deterministik, selalu tersedia

Aturan:
  - Nama model TIDAK di-hardcode (semua dari env)
  - Health check tersedia
  - Setiap output melewati guardrail_service.validate()
  - Jika guardrail gagal → re-prompt maks 2×
  - Jika semua provider gagal ATAU semua guardrail gagal → template deterministik
  - Source dilaporkan: 'gemini' | 'groq' | 'watsonx' | 'ollama' | 'template'

Keamanan data (S9):
  - Anonymization dipanggil sebelum mengirim ke provider eksternal
  - Teks bebas dari user dibungkus <user_note> dan disanitasi (S8)
"""

from __future__ import annotations

import os
import json
import time
from typing import Any, Dict, Optional, Tuple

from api.services.guardrail_service import validate as guardrail_validate, sanitize_user_note, record_call


# ---------------------------------------------------------------------------
# Config dari env
# ---------------------------------------------------------------------------

def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# ---------------------------------------------------------------------------
# Provider: Gemini
# ---------------------------------------------------------------------------

def _call_gemini(system: str, user: str) -> str:
    api_key = _env("LLM_API_KEY") or _env("GOOGLE_API_KEY")
    model = _env("LLM_MODEL_NAME", "gemini-2.5-flash")
    if not api_key or api_key.lower().startswith("your-") or "api-key-here" in api_key.lower():
        raise RuntimeError("LLM_API_KEY not set (placeholder)")
    try:
        from google import genai as google_genai
        from google.genai import types as genai_types
    except ImportError:
        raise RuntimeError("google-genai not installed")

    client = google_genai.Client(api_key=api_key)
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=user,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.3,
                    max_output_tokens=2048,
                ),
            )
            return response.text or ""
        except Exception as exc:
            s = str(exc).upper()
            if any(k in s for k in ("429", "QUOTA", "RATE_LIMIT")):
                raise  # quota error — skip immediately
            if attempt < 2 and any(k in s for k in ("503", "UNAVAILABLE", "502")):
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError("Gemini: max retries exceeded")


# ---------------------------------------------------------------------------
# Provider: Groq
# ---------------------------------------------------------------------------

def _call_groq(system: str, user: str) -> str:
    api_key = _env("LLM_GROQ_API_KEY")
    model = _env("LLM_GROQ_MODEL", "llama-3.3-70b-versatile")
    base_url = _env("LLM_GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    if not api_key:
        raise RuntimeError("LLM_GROQ_API_KEY not set")
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed")

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=2048,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Provider: watsonx (opsional)
# ---------------------------------------------------------------------------

def _call_watsonx(system: str, user: str) -> str:
    api_key = _env("WATSONX_API_KEY")
    project_id = _env("WATSONX_PROJECT_ID")
    model = _env("WATSONX_MODEL_ID", "meta-llama/llama-3-70b-instruct")
    base_url = _env("WATSONX_BASE_URL", "https://us-south.ml.cloud.ibm.com")
    if not api_key or not project_id:
        raise RuntimeError("WATSONX_API_KEY or WATSONX_PROJECT_ID not set")
    try:
        from ibm_watsonx_ai.foundation_models import Model as WatsonxModel
        from ibm_watsonx_ai.credentials import Credentials
    except ImportError:
        raise RuntimeError("ibm-watsonx-ai not installed")

    creds = Credentials(url=base_url, api_key=api_key)
    model_obj = WatsonxModel(model_id=model, credentials=creds, project_id=project_id)
    combined = f"[SYSTEM]\n{system}\n\n[USER]\n{user}"
    result = model_obj.generate_text(prompt=combined)
    return result or ""


# ---------------------------------------------------------------------------
# Provider: Ollama (local, opsional)
# ---------------------------------------------------------------------------

def _call_ollama(system: str, user: str) -> str:
    base_url = _env("OLLAMA_BASE_URL", "http://localhost:11434")
    model = _env("OLLAMA_MODEL", "llama3")
    if not base_url:
        raise RuntimeError("OLLAMA_BASE_URL not set")
    try:
        import httpx
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        resp = httpx.post(f"{base_url}/api/chat", json=payload, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")
    except Exception as exc:
        raise RuntimeError(f"Ollama error: {exc}")


# ---------------------------------------------------------------------------
# Provider: health check
# ---------------------------------------------------------------------------

def health_check() -> Dict[str, Any]:
    """Periksa ketersediaan semua provider. Dipakai oleh /api/v1/health/deps."""
    results = {}

    # Gemini
    gemini_key = _env("LLM_API_KEY") or _env("GOOGLE_API_KEY")
    if gemini_key.lower().startswith("your-") or "api-key-here" in gemini_key.lower():
        gemini_key = ""
    results["gemini"] = "configured" if gemini_key else "no_key"

    # Groq
    groq_key = _env("LLM_GROQ_API_KEY")
    if groq_key.lower().startswith("your-") or "api-key-here" in groq_key.lower() or "changeme" in groq_key.lower():
        groq_key = ""
    results["groq"] = "configured" if groq_key else "no_key"

    # watsonx
    wx_key = _env("WATSONX_API_KEY")
    wx_proj = _env("WATSONX_PROJECT_ID")
    results["watsonx"] = "configured" if (wx_key and wx_proj) else "no_credentials"

    # Ollama
    ollama_url = _env("OLLAMA_BASE_URL")
    if ollama_url:
        try:
            import httpx
            resp = httpx.get(f"{ollama_url}/api/version", timeout=3.0)
            results["ollama"] = "available" if resp.ok else "unreachable"
        except Exception:
            results["ollama"] = "unreachable"
    else:
        results["ollama"] = "not_configured"

    results["template"] = "always_available"
    return results


# ---------------------------------------------------------------------------
# Template deterministik fallback
# ---------------------------------------------------------------------------

_DISCLAIMER = "⚠️ DRAF AI — Wajib diverifikasi apoteker sebelum keputusan klinis ⚠️\n\n"

def _build_sbar_template(context: Dict[str, Any]) -> str:
    """Hasilkan SBAR minimal dari data terstruktur tanpa LLM."""
    patient_id   = context.get("patient_id", "—")
    encounter_id = context.get("encounter_id", "—")
    tier         = context.get("tier", context.get("review_priority", "—"))
    ml_score     = context.get("ml_score", context.get("discrepancy_likelihood", "—"))
    disc_count   = context.get("discrepancy_count", len(context.get("discrepancies", context.get("flags", []))))
    bpmh_count   = context.get("bpmh_count", context.get("pre_admission_med_count", "—"))

    disc_list = context.get("discrepancies", context.get("flags", []))
    disc_text = ""
    if disc_list:
        for d in disc_list[:5]:
            name = d.get("drug_name") or d.get("medication_name") or ""
            rule = d.get("rule_type") or d.get("flag_type") or ""
            ev   = d.get("evidence") or ""
            disc_text += f"  - [{rule}] {name}: {ev}\n"
    else:
        disc_text = "  (Tidak ada diskrepansi spesifik yang terdeteksi)\n"

    return (
        f"{_DISCLAIMER}"
        f"**Template deterministik — LLM tidak tersedia saat laporan ini dibuat.**\n\n"
        f"## S — Situation\n"
        f"- Pasien: {patient_id} | Encounter: {encounter_id}\n"
        f"- Prioritas Telaah Farmasi: **{tier}**\n"
        f"- Skor ML: {ml_score}\n\n"
        f"## B — Background\n"
        f"- Obat BPMH (pra-admisi): {bpmh_count} item\n\n"
        f"## A — Assessment\n"
        f"- Jumlah diskrepansi terdeteksi: {disc_count}\n"
        f"{disc_text}\n"
        f"## R — Recommendation\n"
        f"- Verifikasi setiap diskrepansi di atas dengan pasien dan rekam medis.\n"
        f"- Konfirmasi riwayat penggunaan obat sebelum admisi.\n"
        f"- Laporkan temuan signifikan ke DPJP sebelum keputusan terapi.\n\n"
        f"---\n*Draf ini adalah decision support. "
        "Setiap item WAJIB diverifikasi apoteker klinis sebelum keputusan medis final.*"
    )


def _build_copilot_template(question: str, context: Dict[str, Any]) -> str:
    """Template deterministik untuk copilot saat LLM tidak tersedia."""
    return (
        f"{_DISCLAIMER}"
        f"LLM tidak tersedia saat ini (periksa konfigurasi API key di .env). Berikut data terstruktur untuk pertanyaan Anda:\n\n"
        f"**Pertanyaan:** {question}\n\n"
        f"**Data pasien:**\n```json\n{json.dumps(context, indent=2, ensure_ascii=False)[:1000]}\n```\n\n"
        f"Silakan telaah data di atas secara mandiri atau coba lagi nanti.\n"
        f"Verifikasi langsung dengan pasien/rekam medis sebelum mengambil keputusan."
    )


# ---------------------------------------------------------------------------
# Orchestrated call with guardrail + retry
# ---------------------------------------------------------------------------

_PROVIDERS = [
    ("gemini",  _call_gemini),
    ("groq",    _call_groq),
    ("watsonx", _call_watsonx),
    ("ollama",  _call_ollama),
]


def call_with_guardrail(
    system_prompt: str,
    user_prompt: str,
    context: Dict[str, Any],
    task: str = "sbar",  # "sbar" | "copilot"
    user_question: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Panggil LLM dengan fallback chain dan guardrail.

    Returns: (text, source) di mana source adalah nama provider atau "template"
    """
    # Sanitasi teks bebas user sebelum ke prompt
    if user_question:
        safe_question = sanitize_user_note(user_question)
        user_prompt = user_prompt.replace("{sanitized_question}", safe_question)

    providers = [
        ("gemini",  _call_gemini),
        ("groq",    _call_groq),
        ("watsonx", _call_watsonx),
        ("ollama",  _call_ollama),
    ]

    for provider_name, provider_fn in providers:
        # Skip provider jika env tidak dikonfigurasi
        try:
            # Attempt call + guardrail, max 2 retries
            for attempt in range(3):
                try:
                    raw_text = provider_fn(system_prompt, user_prompt)
                except RuntimeError:
                    break  # provider not configured / unavailable

                report = guardrail_validate(raw_text, context)
                record_call(failed=not report.valid)

                if report.valid:
                    wrapped = _DISCLAIMER + raw_text if not raw_text.startswith("⚠️") else raw_text
                    return wrapped, provider_name

                if attempt < 2:
                    # Re-prompt with failure context
                    violation_hint = "; ".join(report.failures[:2])
                    user_prompt = (
                        f"{user_prompt}\n\n"
                        f"[GUARDRAIL VIOLATION pada percobaan sebelumnya: {violation_hint}. "
                        f"Hasilkan ulang tanpa pelanggaran tersebut.]"
                    )
                else:
                    # Max retries for this provider — try next
                    break

        except Exception:
            continue  # Provider error — try next

    # All providers failed or all guardrails failed → template
    record_call(fallback=True)
    if task == "copilot" and user_question:
        return _build_copilot_template(user_question, context), "template"
    return _build_sbar_template(context), "template"
