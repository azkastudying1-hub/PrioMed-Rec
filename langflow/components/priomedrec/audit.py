"""Deterministic Phase-B Langflow adapters."""
from __future__ import annotations

from lfx.io import Output
from lfx.schema import Data

from priomedrec_core.contracts import AnalysisInput
from priomedrec_core.pipeline import run_phase_b
from priomedrec_core.priority import compute_priority

from .base import PMRJsonComponent


class PMRMedicationNormalizer(PMRJsonComponent):
    display_name = "PMR Medication Normalizer"
    description = "Normalisasi nama obat deterministik; confidence rendah tetap perlu verifikasi."
    outputs = [Output(name="result", display_name="Normalisasi", method="run", tool_mode=True)]

    def run(self) -> Data:
        from api.services.normalizer_service import normalize_batch
        names = self.payload().get("drug_names", [])
        return self.result_data({"items": [item.to_dict() for item in normalize_batch(names)]})


class PMRDiscrepancyRules(PMRJsonComponent):
    display_name = "PMR Discrepancy Rules"
    description = "Deteksi omisi, duplikasi, dan substitusi secara deterministik."

    def run(self) -> Data:
        return self.result_data(run_phase_b(self.payload()))


class PMRSafetyFlags(PMRJsonComponent):
    display_name = "PMR Safety Flags"
    description = "Menandai high-alert, NTI, dan Beers dari lookup terkurasi."
    outputs = [Output(name="result", display_name="Safety flags", method="run", tool_mode=True)]

    def run(self) -> Data:
        from src.rules.safety_flags_engine import check_medication_list
        medications = self.payload().get("medications", [])
        return self.result_data(check_medication_list(medications))


class PMRInteractionChecker(PMRJsonComponent):
    display_name = "PMR Interaction Checker"
    description = "Mengecek DDI terkurasi; hasil selalu perlu verifikasi apoteker."
    outputs = [Output(name="result", display_name="Interaksi", method="run", tool_mode=True)]

    def run(self) -> Data:
        from api.routes.interactions import check_interactions, InteractionCheckRequest
        payload = self.payload()
        response = check_interactions(InteractionCheckRequest(medications=payload.get("medications", [])))
        return self.result_data(response.model_dump())


class PMRAllergyChecker(PMRJsonComponent):
    display_name = "PMR Allergy Checker"
    description = "Meneruskan konflik alergi terstruktur dari aturan deterministik."
    outputs = [Output(name="result", display_name="Konflik alergi", method="run", tool_mode=True)]

    def run(self) -> Data:
        payload = self.payload()
        return self.result_data({"allergy_conflicts": payload.get("allergy_conflicts", []), "verification_required": True})


class PMRSeverityTiering(PMRJsonComponent):
    display_name = "PMR Severity Tiering"
    description = "Meringkas severity findings tanpa LLM."

    def run(self) -> Data:
        findings = self.payload().get("findings", [])
        return self.result_data({"findings": findings, "tier_1_count": sum(1 for item in findings if item.get("severity_tier") == 1)})


class PMRPriorityComposer(PMRJsonComponent):
    display_name = "PMR Priority Composer"
    description = "Prioritas final = max(ML, aturan, SLA); hanya dapat naik."
    outputs = [Output(name="result", display_name="Prioritas", method="run", tool_mode=True)]

    def run(self) -> Data:
        payload = self.payload()
        return self.result_data(compute_priority(payload.get("ml_score"), payload.get("discrepancies"), payload.get("sla_hours_elapsed"), payload.get("sla_config"), payload.get("current_tier")))
