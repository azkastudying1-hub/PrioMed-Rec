"""
src/llm/prompts/task_prompts.py
--------------------------------
Task-specific prompt templates for all 4 LLM functions.

Each function returns a formatted user-turn prompt string that is
combined with system_prompt.txt to form the full LLM request.

Sources: PROJECT_CONTEXT.md §26-§29
"""

from __future__ import annotations

import json
from pathlib import Path


def _system_prompt() -> str:
    """Load the system prompt from file."""
    path = Path(__file__).parent / "system_prompt.txt"
    return path.read_text(encoding="utf-8")


def patient_summary_prompt(context: dict) -> str:
    """
    Build the SBAR patient summary task prompt.
    Formats the clinical review draft using SBAR (Situation, Background, Assessment, Recommendation).
    """
    ctx_json = json.dumps(context, indent=2, default=str)
    return (
        "Anda adalah asisten AI apoteker klinis PrioMed-Rec. Susun Draf Laporan Telaah Klinis berstandar SBAR "
        "(Situation, Background, Assessment, Recommendation) yang formal, terstruktur, dan siap ditelaah apoteker.\n\n"
        "Gunakan HANYA informasi terstruktur yang disediakan dalam input context.\n\n"
        "Format Output (Wajib ikuti struktur Markdown berikut):\n\n"
        "## 📋 DRAF TELAAH KLINIS SBAR (SIAP TELAAH APOTEKER)\n\n"
        "### 🔴 S - Situation\n"
        "- **Pasien:** [Patient ID] | **Encounter:** [Encounter ID]\n"
        "- **Usia / Demografi:** [Age] thn, [Gender]\n"
        "- **Medication Review Priority:** [HIGH / MEDIUM / LOW]\n"
        "- **Predicted Discrepancy Likelihood:** [Risk Probability %]\n\n"
        "### 🏥 B - Background\n"
        "- **Riwayat Resep & Beban Obat:** Jumlah obat sebelum admisi (PAML) vs obat saat admisi (AML).\n"
        "- **Status Polifarmasi & High-Alert:** Jumlah obat berisiko tinggi (high alert) dan status polifarmasi.\n"
        "- **Diagnosis Aktif:** Jumlah kondisi diagnosis aktif pada EHR.\n\n"
        "### 📊 A - Assessment\n"
        "- **Faktor Utama Pemicu Risiko (Top SHAP Features):** Sebutkan fitur teratas yang menaikkan/menurunkan risiko beserta nilainya.\n"
        "- **Temuan Potensi Diskrepansi (Rule Engine):** Sebutkan tiap flag (OMISSION/DUPLICATION) beserta nama obatnya dan nyatakan bahwa item tersebut wajib diverifikasi.\n\n"
        "### 💡 R - Recommendation (Fokus Verifikasi Klinis Apoteker)\n"
        "- Rekomendasikan langkah verifikasi konkret untuk apoteker (contoh: 'Konfirmasi riwayat obat pra-admisi X dengan pasien', 'Klarifikasi alasan penghentian/duplikasi obat Y').\n"
        "- Gunakan frasa verifikasi klinis yang aman ('Verifikasi...', 'Konfirmasi...', 'Klarifikasi...'). Dilarang memberikan instruksi terapi otonom seperti 'stop obat' atau 'resepkan obat'.\n"
        "- Sertakan pernyataan keselamatan wajib: 'Draf ini adalah decision support. Setiap item wajib diverifikasi apoteker klinis sebelum keputusan medis final.'\n\n"
        f"Konteks Pasien:\n{ctx_json}"
    )



def risk_explanation_prompt(context: dict) -> str:
    """
    Build the risk explanation task prompt.
    PROJECT_CONTEXT §27.
    """
    ctx_json = json.dumps(context, indent=2, default=str)
    return (
        "Explain why this patient received the provided priority and risk probability.\n\n"
        "Use only:\n"
        "- the supplied ML output,\n"
        "- the supplied top features,\n"
        "- the supplied patient data.\n\n"
        "Do not recalculate the score.\n"
        "Do not change the priority.\n"
        "Do not infer unsupported clinical conclusions.\n\n"
        "Structure the response as:\n"
        "- Priority\n"
        "- Risk probability\n"
        "- Main factors\n"
        "- What the pharmacist should verify\n\n"
        f"Patient context:\n{ctx_json}"
    )


def discrepancy_explanation_prompt(context: dict) -> str:
    """
    Build the discrepancy explanation task prompt.
    PROJECT_CONTEXT §28.
    """
    ctx_json = json.dumps(context, indent=2, default=str)
    return (
        "Explain the potential medication discrepancy flags provided by the rule engine.\n\n"
        "For each flag:\n"
        "- state the discrepancy type,\n"
        "- identify the relevant medication data,\n"
        "- compare previous vs admission information,\n"
        "- explain why the rule triggered,\n"
        "- clearly state that the discrepancy requires pharmacist verification.\n\n"
        "Do not label it as a confirmed medication error.\n"
        "Do not recommend starting, stopping, or changing therapy.\n\n"
        f"Patient context:\n{ctx_json}"
    )


def pharmacist_qa_prompt(question: str, context: dict) -> str:
    """
    Build the pharmacist Q&A task prompt.
    PROJECT_CONTEXT §29.

    Parameters
    ----------
    question : the pharmacist's natural-language question
    context  : structured patient + risk + discrepancy context
    """
    ctx_json = json.dumps(context, indent=2, default=str)
    return (
        "Answer the following pharmacist question using only the provided structured context.\n\n"
        "Rules:\n"
        "- Base your answer only on the data in the context.\n"
        "- Do not add clinical advice or treatment recommendations.\n"
        "- If the answer is not available in the context, say: "
        "'Informasi tersebut tidak tersedia pada data yang diberikan, "
        "sehingga saya tidak dapat menentukannya dengan andal.'\n"
        "- Do not guess or invent clinical information.\n\n"
        f"Question: {question}\n\n"
        f"Context:\n{ctx_json}"
    )
