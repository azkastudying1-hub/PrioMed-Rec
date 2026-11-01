"""PrioMed-Rec MCP server — IBM Bob-compatible (A-307).

All 5 tools delegate to the FastAPI AI Gateway so a conversational agent
cannot invent scores, discrepancies, or pharmacist decisions.

Safety constraints (ADR-07, S6):
  - Writing tools (draft_pharmacist_review) ONLY create DRAFT status.
  - actor_type is always 'agent_via_mcp' — identity comes from the API token,
    never from a tool argument.
  - The pharmacist must confirm every DRAFT in the UI before it takes effect.

Requires:
  PRIOMEDREC_API_URL   — base URL of the running FastAPI (default: http://127.0.0.1:8000)
  PRIOMEDREC_API_KEY   — service API key (X-Service-Token header)
"""
from __future__ import annotations

import os
from typing import Any, Literal

import httpx
from fastmcp import FastMCP

API_URL = os.getenv("PRIOMEDREC_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("PRIOMEDREC_API_KEY", "")

mcp = FastMCP("PrioMed-Rec Clinical Safety Tools")

_ACTOR_TYPE = "agent_via_mcp"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if API_KEY:
        h["X-Service-Token"] = API_KEY
    return h


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET request to the FastAPI, returning explicit, auditable result."""
    try:
        response = httpx.get(
            f"{API_URL}{path}",
            params=params,
            headers=_headers(),
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"PrioMed-Rec API unavailable: {exc}"}


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST request to the FastAPI, returning explicit, auditable result."""
    try:
        response = httpx.post(
            f"{API_URL}{path}",
            json=payload,
            headers=_headers(),
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"PrioMed-Rec API unavailable: {exc}"}


# ---------------------------------------------------------------------------
# Tool 1 — Read: get_worklist
# ---------------------------------------------------------------------------

@mcp.tool()
def get_worklist(
    tier: str | None = None,
    status: str | None = None,
    ward: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Ambil daftar antrian rekonsiliasi obat dari worklist farmasi.

    Hanya membaca data — tidak mengubah status apa pun.
    Kembalikan daftar kasus beserta Prioritas Telaah Farmasi, SLA, dan tier aturan.

    Args:
        tier:   Filter tier (HIGH / MEDIUM / LOW). Kosongkan untuk semua.
        status: Filter status (PENDING / IN_REVIEW / dll). Kosongkan untuk semua.
        ward:   Filter bangsal (mis. 'ICU', 'Bedah'). Kosongkan untuk semua.
        limit:  Maksimum jumlah item yang dikembalikan (1–100; default 20).
    """
    params: dict[str, Any] = {"limit": min(max(1, limit), 100)}
    if tier:
        params["tier"] = tier.upper()
    if status:
        params["status"] = status.upper()
    if ward:
        params["ward"] = ward
    return _get("/api/v1/worklist", params=params)


# ---------------------------------------------------------------------------
# Tool 2 — Read: rank_admission_risk
# ---------------------------------------------------------------------------

@mcp.tool()
def rank_admission_risk(
    patient_id: str,
    encounter_id: str = "",
) -> dict[str, Any]:
    """
    Hitung skor prioritas telaah farmasi untuk satu pasien menggunakan model ML + aturan.

    Hanya membaca — tidak mengubah terapi.  Skor final = max(ml_tier, rules_floor, sla_floor).
    Penjelasan SHAP dalam bahasa klinis disertakan dalam respons.

    Args:
        patient_id:   Identitas pasien (sintetis/demo).
        encounter_id: ID kunjungan rawat inap (opsional; diambil dari DB bila kosong).
    """
    payload: dict[str, Any] = {"patient_id": patient_id}
    if encounter_id:
        payload["encounter_id"] = encounter_id
    return _post("/api/v1/prioritize/batch", {"patient_ids": [patient_id]})


# ---------------------------------------------------------------------------
# Tool 3 — Read: detect_medication_discrepancy
# ---------------------------------------------------------------------------

@mcp.tool()
def detect_medication_discrepancy(
    encounter_id: str,
    question: str | None = None,
) -> dict[str, Any]:
    """
    Jalankan rule engine deterministik untuk mendeteksi diskrepansi obat pada kunjungan.

    LLM TIDAK terlibat dalam deteksi ini (S2).
    Kategori: omisi, duplikasi, substitusi, interaksi, alergi, high-alert.
    Setiap temuan disertai severity tier (1/2/3) dan flag high_alert.

    Args:
        encounter_id: ID kunjungan rawat inap yang akan dianalisis.
        question:     Pertanyaan opsional untuk konteks (mis. 'Apakah ada obat jantung?').
    """
    return _post(
        "/analyze",
        {
            "encounter_id": encounter_id,
            "question": question,
            "actor_type": _ACTOR_TYPE,
        },
    )


# ---------------------------------------------------------------------------
# Tool 4 — Read: lookup_drug_knowledge
# ---------------------------------------------------------------------------

@mcp.tool()
def lookup_drug_knowledge(
    drug_name: str,
    lookup_type: Literal["alias", "interaction", "allergy", "high_alert"] = "alias",
) -> dict[str, Any]:
    """
    Cari informasi obat dari knowledge base PrioMed-Rec (hanya baca).

    Sumber data: knowledge/drug_alias.csv, knowledge/interactions.json,
    configs/allergy_rules.json (DRAFT_PERLU_VALIDASI_APOTEKER).

    Args:
        drug_name:   Nama obat yang dicari (merek dagang, INN, atau alias).
        lookup_type: Jenis pencarian:
                     - 'alias'       : normalisasi nama obat (brand → INN)
                     - 'interaction' : daftar interaksi obat dikenal di KB
                     - 'allergy'     : aturan reaksi silang alergi (DRAFT)
                     - 'high_alert'  : apakah obat masuk daftar high-alert
    """
    return _post(
        "/api/v1/knowledge/lookup",
        {
            "drug_name": drug_name,
            "lookup_type": lookup_type,
            "actor_type": _ACTOR_TYPE,
        },
    )


# ---------------------------------------------------------------------------
# Tool 5 — Write (DRAFT ONLY): draft_pharmacist_review
# ---------------------------------------------------------------------------

@mcp.tool()
def draft_pharmacist_review(
    encounter_id: str,
    suggested_action: Literal["APPROVE", "EDIT", "REJECT", "ESCALATE"],
    pharmacist_note: str = "",
    discrepancy_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Buat DRAF rekomendasi review untuk diverifikasi apoteker di UI (BUKAN keputusan final).

    PENTING — Batasan ADR-07 / S6:
      • Status hasil selalu DRAFT_REVIEW — bukan keputusan final.
      • Apoteker WAJIB mengonfirmasi, mengubah, atau menolak draf ini di UI.
      • actor_type dicatat sebagai 'agent_via_mcp' di audit trail.
      • Tool ini TIDAK dapat mengubah status kasus menjadi APPROVED/REJECTED.

    Args:
        encounter_id:      ID kunjungan yang akan di-draft.
        suggested_action:  Saran tindakan (APPROVE / EDIT / REJECT / ESCALATE).
        pharmacist_note:   Catatan opsional untuk apoteker (disanitasi server-side).
        discrepancy_ids:   ID diskrepansi yang dirujuk (opsional).
    """
    return _post(
        "/api/v1/review/draft",
        {
            "encounter_id": encounter_id,
            "suggested_action": suggested_action.upper(),
            "pharmacist_note": pharmacist_note,
            "discrepancy_ids": discrepancy_ids or [],
            "actor_type": _ACTOR_TYPE,
            # Explicitly assert DRAFT status — server enforces this regardless
            "force_status": "DRAFT_REVIEW",
        },
    )


if __name__ == "__main__":
    mcp.run()
