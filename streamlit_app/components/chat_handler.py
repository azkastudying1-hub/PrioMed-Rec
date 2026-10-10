"""
streamlit_app/components/chat_handler.py
------------------------------------------
Chat input → Langflow/FastAPI → structured response.

Extracts patient_id from free-text input, calls the backend,
and returns the response dict.
"""

from __future__ import annotations

import re
from typing import Optional

from streamlit_app.utils.langflow_client import call_langflow


# Common Indonesian/English patterns for patient queries
_PATIENT_ID_PATTERNS = [
    r"pasien\s+([A-Za-z0-9\-]+)",
    r"patient\s+([A-Za-z0-9\-]+)",
    r"analisis\s+([A-Za-z0-9\-]+)",
    r"review\s+([A-Za-z0-9\-]+)",
    r"\b(P\d+)\b",   # full token e.g. P001, P123
]

# Bare ID: must start with a letter followed by at least 2 chars, no common words
_BARE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9\-]{2,49}$")
_STOP_WORDS = {
    "pasien", "patient", "analisis", "review", "ini", "ada", "yang", "dengan",
    "kenapa", "mengapa", "apa", "bagaimana", "hello", "world", "this", "text",
    "contains", "no", "id", "at", "all", "here", "and", "the", "for", "is",
    "sentence", "text",
}


def extract_patient_id(text: str) -> Optional[str]:
    """
    Extract a patient_id from free-text chat input.

    Examples:
      "Analisis pasien P001"              → "P001"
      "Kenapa patient P001 diprioritaskan?" → "P001"
      "pasien abc-123-xyz"                → "abc-123-xyz"
    """
    for pattern in _PATIENT_ID_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if candidate.lower() not in _STOP_WORDS:
                return candidate
    # Fallback: bare ID (single token, no spaces, starts with letter, not a stop word)
    text_stripped = text.strip()
    if (_BARE_ID_RE.fullmatch(text_stripped)
            and text_stripped.lower() not in _STOP_WORDS):
        return text_stripped
    return None


def is_question(text: str) -> bool:
    """Return True if the input looks like a Q&A query (not a pure analysis request)."""
    question_keywords = [
        "kenapa", "mengapa", "apa", "bagaimana", "kapan", "siapa",
        "why", "what", "how", "when", "explain", "jelaskan", "ringkas",
    ]
    lower = text.lower()
    return any(kw in lower for kw in question_keywords)


def handle_chat(user_input: str) -> dict:
    """
    Process a chat input and return an analysis response dict.

    Flow:
      1. Extract patient_id from input text.
      2. Determine if it's an analysis request or a Q&A question.
      3. Call Langflow (or direct FastAPI fallback).
      4. Return response dict.
    """
    if not user_input or not user_input.strip():
        return {
            "error": "empty_input",
            "message": "Ketik nama/ID pasien untuk memulai analisis.",
            "report": "ℹ️ Ketik query seperti: **Analisis pasien P001**",
            "report_available": False,
        }

    patient_id = extract_patient_id(user_input)
    if not patient_id:
        return {
            "error": "no_patient_id",
            "message": f"Tidak dapat mengekstrak patient_id dari: '{user_input}'",
            "report": (
                "❌ **Patient ID tidak ditemukan.**\n\n"
                "Coba format:\n"
                "- `Analisis pasien P001`\n"
                "- `Kenapa pasien P001 diprioritaskan?`\n"
                "- `P001`"
            ),
            "report_available": False,
        }

    # Determine question vs pure analysis
    question: Optional[str] = None
    if is_question(user_input):
        question = user_input

    return call_langflow(patient_id, question=question)
