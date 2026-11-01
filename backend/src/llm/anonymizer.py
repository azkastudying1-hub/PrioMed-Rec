"""
src/llm/anonymizer.py
----------------------
Anonymization layer for PrioMed-Rec LLM calls.

Before sending patient context to any external LLM, this module:
  - Replaces patient_id with a session-consistent anonymous token
  - Redacts names and other PII from free-text fields
  - Respects LLM_DATA_MODE env var:
      synthetic  = data is synthetic, send as-is
      anonymized = redact PII before sending (production default)
      blocked    = do not call LLM at all

Usage:
  from src.llm.anonymizer import anonymize_context, should_call_llm
  
  if not should_call_llm():
      return fallback_report()
  
  safe_context = anonymize_context(context)
  result = _call_llm(system, user_prompt_from(safe_context))
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any


def get_llm_data_mode() -> str:
    """Returns LLM_DATA_MODE env var: synthetic | anonymized | blocked."""
    return os.getenv("LLM_DATA_MODE", "anonymized").strip().lower()


def should_call_llm() -> bool:
    """Returns False if LLM_DATA_MODE=blocked."""
    return get_llm_data_mode() != "blocked"


def _anon_token(patient_id: str) -> str:
    """Generate a consistent anonymous token for a patient_id within this session."""
    # Use first 8 chars of SHA256 — consistent within a process, not reversible
    digest = hashlib.sha256(f"priomed-anon-{patient_id}".encode()).hexdigest()[:8].upper()
    return f"PATIENT_ANON_{digest}"


# PII patterns to redact from free text
_PII_PATTERNS = [
    # Indonesian names (common patterns)
    (re.compile(r'\b(Tn\.|Ny\.|An\.|Sdr\.)\s+[A-Z][a-z]+(\s+[A-Z][a-z]+)*\b'), '[NAMA_DIREDAKSI]'),
    # Generic name patterns in ALL CAPS
    (re.compile(r'\b[A-Z]{2,}\s+[A-Z]{2,}(\s+[A-Z]{2,})*\b'), '[NAMA_DIREDAKSI]'),
    # Phone numbers
    (re.compile(r'\b(\+62|0)[0-9\-\s]{8,14}\b'), '[TELP_DIREDAKSI]'),
    # NIK / ID numbers (16 digits)
    (re.compile(r'\b[0-9]{16}\b'), '[NIK_DIREDAKSI]'),
    # Dates of birth patterns (when clearly DOB context)
    (re.compile(r'(lahir|TTL|tanggal lahir)[:\s]+\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}', re.IGNORECASE), 
     '[TGL_LAHIR_DIREDAKSI]'),
]


def _redact_text(text: str) -> str:
    """Apply PII redaction patterns to a free-text string."""
    if not text:
        return text
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def anonymize_context(context: dict) -> dict:
    """
    Return a copy of context with PII anonymized.
    
    In 'synthetic' mode: returns context unchanged.
    In 'anonymized' mode: replaces patient_id, redacts PII text fields.
    In 'blocked' mode: should not be called (check should_call_llm() first).
    """
    mode = get_llm_data_mode()
    
    if mode == "synthetic":
        return context  # Synthetic data — safe to send as-is
    
    if mode == "blocked":
        raise RuntimeError("LLM_DATA_MODE=blocked — LLM calls are disabled.")
    
    # mode == "anonymized" (default for production)
    import copy
    ctx = copy.deepcopy(context)
    
    # Anonymize patient section
    if "patient" in ctx and isinstance(ctx["patient"], dict):
        patient = ctx["patient"]
        original_pid = patient.get("patient_id", "")
        if original_pid:
            patient["patient_id"] = _anon_token(original_pid)
        # Keep age/gender (not PII) but redact encounter_id
        if patient.get("encounter_id"):
            patient["encounter_id"] = "ENC_ANON"
        # Redact any name fields
        for key in ("name", "patient_name", "nama", "nama_pasien"):
            if key in patient:
                patient[key] = "[NAMA_DIREDAKSI]"
    
    # Redact source_notes and free text in medication lists
    for med_list_key in ("pre_admission_meds", "admission_meds"):
        if med_list_key in ctx and isinstance(ctx[med_list_key], list):
            for med in ctx[med_list_key]:
                if isinstance(med, dict):
                    for text_field in ("source_notes", "indication_note", "note", "comment"):
                        if med.get(text_field):
                            med[text_field] = _redact_text(str(med[text_field]))
    
    return ctx
