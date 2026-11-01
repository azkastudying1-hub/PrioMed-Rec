"""
api/routes/v1/ai.py
---------------------
AI Gateway — semua panggilan AI melalui FastAPI (A-301, ADR-02).

Browser TIDAK PERNAH memanggil Langflow/LLM langsung.
Alur: UI → POST /api/v1/ai/sbar | /ai/copilot → LLM chain → guardrail → respons

Endpoint:
  POST /api/v1/ai/sbar      — hasilkan SBAR dari data encounter
  POST /api/v1/ai/copilot   — tanya-jawab copilot tentang kasus

Setiap respons membawa:
  - source: "gemini" | "groq" | "watsonx" | "ollama" | "template"
  - guardrail_version: string
  - ai_draft_label: "Draf AI — wajib diverifikasi apoteker" (S12)

Langkah keselamatan (S2, S3, S7, S12):
  - Semua respons melewati guardrail_service.validate()
  - Template deterministik sebagai fallback terakhir
  - Teks bebas user dibungkus <user_note> dan disanitasi
  - Tidak ada panggilan LLM langsung dari browser
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth.rbac import TokenData, require_roles, UserRole
from api.services.guardrail_service import sanitize_user_note, GUARDRAIL_VERSION
from api.services.llm_chain_service import call_with_guardrail
from api.db.session import session_scope as get_session
from api.db.models import SbarDraft, Encounter

router = APIRouter(prefix="/ai", tags=["ai-gateway"])

_AI_DRAFT_LABEL = "Draf AI — wajib diverifikasi apoteker"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SbarRequest(BaseModel):
    encounter_id: str
    context_override: Optional[Dict[str, Any]] = None  # Extra context from client


class SbarResponse(BaseModel):
    encounter_id: str
    sbar_text: str
    source: str                   # gemini | groq | watsonx | ollama | template
    guardrail_version: str
    ai_draft_label: str
    warnings: list[str] = []


class CopilotRequest(BaseModel):
    encounter_id: Optional[str] = None
    question: str = Field(..., min_length=1, max_length=500)
    context_override: Optional[Dict[str, Any]] = None


class CopilotResponse(BaseModel):
    answer: str
    source: str
    guardrail_version: str
    ai_draft_label: str
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# POST /api/v1/ai/sbar
# ---------------------------------------------------------------------------

@router.post(
    "/sbar",
    response_model=SbarResponse,
    summary="Hasilkan draf SBAR dari data encounter (AI Gateway)",
)
async def generate_sbar(
    body: SbarRequest,
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR)
    ),
):
    """
    Hasilkan draf SBAR untuk encounter menggunakan LLM chain dengan fallback.
    Output selalu melewati guardrail. Source dilaporkan untuk transparansi.
    """
    # Build context from DB or override
    context = body.context_override or {}
    context["encounter_id"] = body.encounter_id

    with get_session() as session:
        enc = session.query(Encounter).filter(Encounter.id == body.encounter_id).first()
        if enc:
            context.setdefault("patient_id", enc.patient_id)
            context.setdefault("tier", enc.latest_tier)
            context.setdefault("ml_score", enc.ml_score)

    # Load versioned system prompt
    system_prompt = _load_prompt_system("sbar_v1")
    user_prompt = _build_sbar_user_prompt(context)

    text, source = call_with_guardrail(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        context=context,
        task="sbar",
    )

    # Optionally persist to sbar_drafts
    try:
        _persist_sbar_draft(body.encounter_id, text, source, current_user.user_id)
    except Exception:
        pass  # Non-blocking

    return SbarResponse(
        encounter_id=body.encounter_id,
        sbar_text=text,
        source=source,
        guardrail_version=GUARDRAIL_VERSION,
        ai_draft_label=_AI_DRAFT_LABEL,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/ai/copilot
# ---------------------------------------------------------------------------

@router.post(
    "/copilot",
    response_model=CopilotResponse,
    summary="Tanya-jawab copilot tentang kasus (AI Gateway)",
)
async def copilot_answer(
    body: CopilotRequest,
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR)
    ),
):
    """
    Menjawab pertanyaan apoteker tentang kasus menggunakan LLM.
    Teks bebas dari user disanitasi dan dibungkus <user_note>.
    """
    safe_q = sanitize_user_note(body.question)

    context: Dict[str, Any] = body.context_override or {}
    if body.encounter_id:
        context["encounter_id"] = body.encounter_id
        with get_session() as session:
            enc = session.query(Encounter).filter(Encounter.id == body.encounter_id).first()
            if enc:
                context.setdefault("patient_id", enc.patient_id)
                tier = enc.latest_tier
                if not tier:
                    from api.db.models import QueueEntry

                    qe = (
                        session.query(QueueEntry)
                        .filter(QueueEntry.encounter_id == body.encounter_id)
                        .first()
                    )
                    if qe:
                        tier = {2: "HIGH", 1: "MEDIUM", 0: "LOW"}.get(
                            getattr(qe, "tier_rank", None), None
                        )
                context.setdefault("tier", tier)

    system_prompt = _load_prompt_system("copilot_v1")
    user_prompt = (
        f"Konteks kasus: {json.dumps(context, ensure_ascii=False)[:1000]}\n\n"
        f"Pertanyaan apoteker:\n<user_note>{safe_q}</user_note>"
    )

    text, source = call_with_guardrail(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        context=context,
        task="copilot",
        user_question=safe_q,
    )

    return CopilotResponse(
        answer=text,
        source=source,
        guardrail_version=GUARDRAIL_VERSION,
        ai_draft_label=_AI_DRAFT_LABEL,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/ai/health
# ---------------------------------------------------------------------------

@router.get(
    "/health",
    summary="Status provider LLM",
)
async def ai_health(
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.ADMIN)
    ),
):
    """Periksa ketersediaan semua provider LLM."""
    from api.services.llm_chain_service import health_check, _PROVIDERS
    from api.services.guardrail_service import get_metrics
    return {
        "providers": health_check(),
        "guardrail_version": GUARDRAIL_VERSION,
        "guardrail_metrics": get_metrics(),
        "fallback_order": [p[0] for p in _PROVIDERS] + ["template"],
        "prompt_versions": {"sbar": "sbar_v1", "copilot": "copilot_v1"},
    }


# ---------------------------------------------------------------------------
# GET /api/v1/ai/status  (no secret leakage)
# ---------------------------------------------------------------------------

@router.get(
    "/status",
    summary="Status ringkas provider AI + Langflow",
)
async def ai_status():
    """Laporkan kesiapan provider, model, Langflow, dan mode eksekusi tanpa secret."""
    import os

    from api.services.llm_chain_service import _env

    llm_provider = _env("LLM_PROVIDER", "gemini")
    if llm_provider == "gemini":
        model_name = _env("LLM_MODEL_NAME", "gemini-2.5-flash")
    elif llm_provider == "groq":
        model_name = _env("LLM_GROQ_MODEL", "llama-3.3-70b-versatile")
    else:
        model_name = _env("LLM_MODEL_NAME", "")

    langflow_configured = bool(_env("LANGFLOW_MASTER_FLOW_ID") and (_env("LANGFLOW_API_KEY") or True))
    # Langflow client requires API key in current implementation
    langflow_configured = bool(_env("LANGFLOW_MASTER_FLOW_ID") and _env("LANGFLOW_API_KEY"))

    def _key_configured(val: str) -> bool:
        v = (val or "").strip()
        if not v:
            return False
        low = v.lower()
        if low.startswith("your-") or "api-key-here" in low or "changeme" in low:
            return False
        return True

    if llm_provider == "gemini":
        llm_configured = _key_configured(_env("LLM_API_KEY") or _env("GOOGLE_API_KEY"))
    elif llm_provider == "groq":
        llm_configured = _key_configured(_env("LLM_GROQ_API_KEY"))
    else:
        llm_configured = bool(_env("OLLAMA_BASE_URL"))

    return {
        "provider": llm_provider,
        "model": model_name,
        "langflow_configured": langflow_configured,
        "execution_mode": _env("EXECUTION_MODE", "langflow_first"),
        "llm_configured": llm_configured,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_prompt_system(prompt_name: str) -> str:
    """Load system prompt dari prompts/ direktori."""
    from pathlib import Path
    p = Path(__file__).parent.parent.parent.parent / "prompts" / f"{prompt_name}.md"
    if p.exists():
        content = p.read_text(encoding="utf-8")
        # Extract ---SYSTEM--- section
        if "---SYSTEM---" in content:
            parts = content.split("---SYSTEM---")
            if len(parts) > 1:
                sys_part = parts[1].split("---USER---")[0].strip()
                return sys_part
    # Fallback system prompt
    return (
        "Anda adalah asisten AI PrioMed-Rec. "
        "Bantu apoteker memahami data rekonsiliasi obat pasien. "
        "Jangan mengambil keputusan klinis. "
        "Setiap output wajib dimulai dengan disclaimer verifikasi apoteker."
    )


def _build_sbar_user_prompt(context: Dict[str, Any]) -> str:
    return (
        "Susun DRAF SBAR rekonsiliasi obat menggunakan data terstruktur berikut:\n\n"
        f"{json.dumps(context, indent=2, ensure_ascii=False)}\n\n"
        "Gunakan HANYA data di atas. Jangan mengarang informasi klinis."
    )


def _persist_sbar_draft(
    encounter_id: str,
    text: str,
    source: str,
    created_by: str,
) -> None:
    """Simpan SBAR draft ke database (non-blocking, best-effort)."""
    import uuid
    from datetime import datetime, timezone

    with get_session() as session:
        # Get current max version
        import sqlalchemy as sa
        max_ver = session.execute(
            sa.text("SELECT COALESCE(MAX(version), 0) FROM sbar_drafts WHERE encounter_id = :enc_id"),
            {"enc_id": encounter_id},
        ).scalar() or 0

        draft = SbarDraft(
            id=str(uuid.uuid4()),
            encounter_id=encounter_id,
            version=int(max_ver) + 1,
            situation=None,
            background=None,
            assessment=None,
            recommendation=None,
            source=source,
            llm_provider=source,
            prompt_version="sbar_v1",
            guardrail_passed=True,
            is_sent_to_dpjp=False,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=created_by,
        )
        session.add(draft)
        session.commit()
