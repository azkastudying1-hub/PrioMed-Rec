"""Narrative boundary and output packaging adapters."""
from __future__ import annotations

from lfx.io import Output
from lfx.schema import Data

from .base import PMRJsonComponent


class PMRContextBuilder(PMRJsonComponent):
    display_name = "PMR Context Builder"
    description = "Membangun konteks LLM terikat dari data terverifikasi."

    def run(self) -> Data:
        payload = self.payload()
        return self.result_data({"verified_context": payload, "ai_draft_label": "Draf AI — wajib diverifikasi apoteker"})


class PMRGuardrail(PMRJsonComponent):
    display_name = "PMR Guardrail"
    description = "Menjalankan guardrail deterministik atas narasi AI."

    def run(self) -> Data:
        from api.services.guardrail_service import validate
        payload = self.payload()
        report = validate(payload.get("text", ""), payload.get("context", {}))
        return self.result_data(report.__dict__ if hasattr(report, "__dict__") else dict(report))


class PMRDeterministicSBARTemplate(PMRJsonComponent):
    display_name = "PMR Deterministic SBAR Template"
    description = "Fallback SBAR deterministik jika LLM/guardrail gagal."

    def run(self) -> Data:
        from api.services.llm_chain_service import _build_sbar_template
        return self.result_data({"sbar_text": _build_sbar_template(self.payload()), "source": "template", "ai_draft_label": "Draf AI — wajib diverifikasi apoteker"})


class PMRResultPackager(PMRJsonComponent):
    display_name = "PMR Result Packager"
    description = "Mengemas keluaran flow terstruktur untuk verifier FastAPI."

    def run(self) -> Data:
        return self.result_data(self.payload())


class PMRCaseContext(PMRJsonComponent):
    display_name = "PMR Case Context"
    description = "Tool baca konteks kasus untuk copilot."
    outputs = [Output(name="result", display_name="Konteks kasus", method="run", tool_mode=True)]

    def run(self) -> Data:
        return self.result_data(self.payload())


class PMRDraftReview(PMRJsonComponent):
    display_name = "PMR Draft Review"
    description = "Membuat payload DRAFT_REVIEW; tidak pernah menyetujui resep atau review final."
    outputs = [Output(name="result", display_name="Draf review", method="run", tool_mode=True)]

    def run(self) -> Data:
        payload = self.payload()
        return self.result_data({"action": "DRAFT_REVIEW", "status": "DRAFT_REVIEW", "encounter_id": payload.get("encounter_id"), "requires_human_approval": True})
