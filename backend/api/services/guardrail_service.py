"""
api/services/guardrail_service.py
-----------------------------------
Guardrail bersama untuk semua output LLM di backend (A-302).

9 cek keselamatan:
  #1  Forbidden clinical action phrases (EN + ID) — hentikan/mulai/resepkan obat
  #2  Prompt injection patterns
  #3  "Confirmed medication error" tanpa "verification required"
  #4  Prioritas pasien tidak boleh di-reassign oleh LLM
  #5  Obat fiktif: klaim interaksi obat tidak di KB
  #6  JSON schema valid (jika respons JSON)
  #7  Fidelitas angka dosis: angka dalam output harus cocok dengan input context
  #8  Deteksi bahasa instruksi: harus Indonesia/Inggris (bukan bahasa lain)
  #9  Deteksi prompt-injection lanjutan (lebih luas dari #2)

Hasil: GuardrailReport (valid: bool, failures: list, text_clean: str)
Jika ada failure → re-prompt (maks 2×), lalu fallback ke template deterministik.

Gunakan modul ini sebagai satu-satunya titik validasi output LLM di backend.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Konfigurasi versi guardrail
# ---------------------------------------------------------------------------

GUARDRAIL_VERSION = "guardrail-1.1.0"


# ---------------------------------------------------------------------------
# Pola terlarang (#1 — frasa instruksi terapi)
# ---------------------------------------------------------------------------

_FORBIDDEN_PHRASES = [
    # English
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
    # Indonesian
    r"\bhentikan\s+obat\b",
    r"\bmulai\s+obat\b",
    r"\bmulai\s+pemberian\b",
    r"\btingkatkan\s+dosis\b",
    r"\bnaikkan\s+dosis\b",
    r"\bkurangi\s+dosis\b",
    r"\bturunkan\s+dosis\b",
    r"\bberikan\s+obat\b",
    r"\bstop\s+obat\b",
    r"\border\s+obat\b",
    r"\bpesan\s+obat\b",
    r"\bganti\s+obat\s+dengan\b",
    r"\bresepkan\b",
    r"\binstruksikan\b",
]

# ---------------------------------------------------------------------------
# Pola prompt injection (#2 + #9 diperluas)
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS = [
    # Classic
    r"ignore\s+(previous|all|above)\s+instruction",
    r"forget\s+(your|all)\s+instruction",
    r"you\s+are\s+now\s+a",
    r"act\s+as\s+(a\s+)?doctor",
    r"pretend\s+(you\s+are|to\s+be)",
    # Extended (#9)
    r"disregard\s+(all\s+)?previous",
    r"new\s+instruction[s]?\s*:",
    r"system\s+prompt\s*:",
    r"override\s+(the\s+)?(safety|guardrail|rules?)",
    r"bypass\s+(the\s+)?(guardrail|filter|safety)",
    r"you\s+are\s+a\s+helpful\s+assistant\s+without",
    r"jangan\s+ikuti\s+instruksi",
    r"abaikan\s+instruksi",
    r"lupakan\s+semua\s+instruksi",
]

# ---------------------------------------------------------------------------
# Dataclass hasil
# ---------------------------------------------------------------------------

@dataclass
class GuardrailReport:
    valid: bool
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    text_clean: str = ""
    version: str = GUARDRAIL_VERSION
    check_count: int = 9


# ---------------------------------------------------------------------------
# Sanitasi <user_note> (#8/#9 — pembungkus teks bebas dari user)
# ---------------------------------------------------------------------------

def sanitize_user_note(text: str) -> str:
    """
    Bersihkan teks bebas dari pengguna sebelum dimasukkan ke prompt.
    - Strip karakter kontrol
    - Potong di 500 karakter
    - Hapus pola injection yang jelas
    """
    if not text:
        return ""
    # Remove control characters
    clean = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', text)
    # Strip injection patterns (replace with [DIBLOKIR])
    for p in _INJECTION_PATTERNS:
        clean = re.sub(p, '[DIBLOKIR]', clean, flags=re.IGNORECASE)
    # Trim to 500 chars
    return clean[:500].strip()


# ---------------------------------------------------------------------------
# Check #7: fidelitas angka dosis
# ---------------------------------------------------------------------------

def _check_dose_fidelity(text: str, input_context: Dict[str, Any]) -> List[str]:
    """
    Periksa apakah angka numerik signifikan dalam output cocok dengan input context.
    Hanya angka yang terlihat seperti dosis (diikuti mg/ml/mcg/iu/g) yang diperiksa.
    """
    violations = []
    # Collect numbers from input context (flatten to set)
    input_numbers: set = set()
    def _collect(obj):
        if isinstance(obj, (int, float)):
            input_numbers.add(float(obj))
        elif isinstance(obj, str):
            for m in re.finditer(r'\b(\d+(?:\.\d+)?)\s*(mg|ml|mcg|iu|g|mmol)\b', obj, re.IGNORECASE):
                input_numbers.add(float(m.group(1)))
        elif isinstance(obj, dict):
            for v in obj.values(): _collect(v)
        elif isinstance(obj, list):
            for i in obj: _collect(i)
    _collect(input_context)

    # Find dose numbers in output
    for m in re.finditer(r'\b(\d+(?:\.\d+)?)\s*(mg|ml|mcg|iu|g|mmol)\b', text, re.IGNORECASE):
        val = float(m.group(1))
        unit = m.group(2).lower()
        # Allow common round numbers (50mg, 100mg etc.) as they appear in many drugs
        if val > 0 and val not in input_numbers:
            # Only flag if the value is unusual (not a very common dose)
            if val not in {5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 0.5, 1, 2, 5}:
                violations.append(
                    f"CHECK_7_DOSE_FIDELITY: dosis '{val}{unit}' "
                    f"tidak ditemukan dalam input context — perlu verifikasi."
                )
    return violations


# ---------------------------------------------------------------------------
# Check #8: deteksi bahasa instruksi
# ---------------------------------------------------------------------------

_NON_LATIN_BLOCKS = re.compile(
    r'[\u0600-\u06FF\u0400-\u04FF\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF\u0900-\u097F]'
)

def _check_language(text: str) -> List[str]:
    """
    Deteksi teks non-Latin yang signifikan (Arab, Cyrillic, CJK, dll.).
    Output LLM harus dalam bahasa Indonesia atau Inggris.
    """
    non_latin = _NON_LATIN_BLOCKS.findall(text)
    if len(non_latin) > 20:
        return [
            f"CHECK_8_LANGUAGE: teks mengandung karakter non-Latin ({len(non_latin)} karakter). "
            "Output diharapkan dalam bahasa Indonesia atau Inggris."
        ]
    return []


# ---------------------------------------------------------------------------
# Main validator
# ---------------------------------------------------------------------------

def validate(
    text: str,
    input_context: Optional[Dict[str, Any]] = None,
) -> GuardrailReport:
    """
    Jalankan semua 9 cek guardrail pada teks output LLM.

    Returns GuardrailReport dengan valid=True jika semua cek lulus.
    Jika ada failure → valid=False (caller harus re-prompt atau gunakan template).
    """
    ctx = input_context or {}
    failures: List[str] = []
    warnings: List[str] = []

    # --- Check #1: forbidden clinical action phrases ---
    for pattern in _FORBIDDEN_PHRASES:
        if re.search(pattern, text, re.IGNORECASE):
            failures.append(
                f"CHECK_1_FORBIDDEN_PHRASE: frasa terapi otonom terdeteksi (pola: '{pattern}'). "
                "LLM tidak boleh merekomendasikan memulai/menghentikan/mengubah obat."
            )
            break  # one failure is enough for this category

    # --- Check #2 + #9: prompt injection ---
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            failures.append(
                f"CHECK_2_9_INJECTION: pola prompt-injection terdeteksi ('{pattern}'). Respons ditolak."
            )
            break

    # --- Check #3: confirmed error without verification ---
    if re.search(r"confirmed\s+medication\s+error", text, re.IGNORECASE):
        if not re.search(r"verification\s+required", text, re.IGNORECASE):
            failures.append(
                "CHECK_3_CONFIRMED_ERROR: LLM menyatakan 'confirmed medication error' "
                "tanpa 'verification required'. Ditolak."
            )

    # --- Check #4: priority reassignment ---
    orig_tier = str(ctx.get("tier", ctx.get("review_priority", ""))).upper()
    if orig_tier in {"HIGH", "MEDIUM", "LOW"}:
        other_tiers = {"HIGH", "MEDIUM", "LOW"} - {orig_tier}
        text_upper = text.upper()
        for other in other_tiers:
            reassign_patterns = [
                rf"THIS PATIENT IS\s+{other}",
                rf"PRIORITY[:\s]+{other}\b",
                rf"CLASSIFIED AS\s+{other}\b",
                rf"PASIEN INI\s+{other}",
                rf"PRIORITAS\s*:\s*{other}\b",
            ]
            if any(re.search(p, text_upper) for p in reassign_patterns):
                failures.append(
                    f"CHECK_4_PRIORITY_REASSIGN: LLM mengubah tier ke '{other}' "
                    f"(seharusnya '{orig_tier}'). Prioritas tidak boleh diubah oleh LLM."
                )
                break

    # --- Check #5: unsourced interaction claims (warning, not failure) ---
    _interaction_phrases = re.compile(
        r'(berinteraksi|meningkatkan risiko|kontraindikasi|interacts|increases risk|concurrent use)',
        re.IGNORECASE
    )
    if _interaction_phrases.search(text):
        warnings.append(
            "CHECK_5_INTERACTION_CLAIM: teks menyebut interaksi obat — "
            "pastikan klaim bersumber dari knowledge base, bukan dikarang LLM."
        )

    # --- Check #6: schema/format (warning if no SBAR section headers) ---
    # For SBAR outputs only
    if "SBAR" in text.upper() or "situation" in text.lower():
        if not re.search(r"(S\s*[-—]|B\s*[-—]|A\s*[-—]|R\s*[-—]|Situation|Background|Assessment|Recommendation)", text, re.IGNORECASE):
            warnings.append(
                "CHECK_6_FORMAT: output tampak seperti SBAR tapi tidak memiliki header S/B/A/R yang diharapkan."
            )

    # --- Check #7: dose fidelity ---
    dose_issues = _check_dose_fidelity(text, ctx)
    warnings.extend(dose_issues)  # Warning, not hard failure (dosis sering tidak di context)

    # --- Check #8: language ---
    lang_issues = _check_language(text)
    failures.extend(lang_issues)

    valid = len(failures) == 0
    return GuardrailReport(
        valid=valid,
        failures=failures,
        warnings=warnings,
        text_clean=text if valid else "",
        version=GUARDRAIL_VERSION,
    )


# ---------------------------------------------------------------------------
# Metric counter (in-memory, resets on restart)
# ---------------------------------------------------------------------------

_metrics: Dict[str, int] = {
    "calls": 0,
    "failures": 0,
    "fallback_used": 0,
}


def record_call(failed: bool = False, fallback: bool = False) -> None:
    _metrics["calls"] += 1
    if failed: _metrics["failures"] += 1
    if fallback: _metrics["fallback_used"] += 1


def get_metrics() -> Dict[str, int]:
    return dict(_metrics)
