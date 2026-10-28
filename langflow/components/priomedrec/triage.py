"""Deterministic Phase-A Langflow adapters."""
from __future__ import annotations

from lfx.io import Output
from lfx.schema import Data

from priomedrec_core.contracts import AnalysisInput
from priomedrec_core.pipeline import run_phase_a
from priomedrec_core.priority import tier_from_score

from .base import PMRJsonComponent


class PMRPayloadValidator(PMRJsonComponent):
    display_name = "PMR Payload Validator"
    description = "Memvalidasi kontrak input sintetik tanpa LLM."

    def run(self) -> Data:
        data = AnalysisInput.model_validate(self.payload())
        return self.result_data(data.model_dump(mode="json"))


class PMRFeatureExtractor(PMRJsonComponent):
    display_name = "PMR Feature Extractor"
    description = "Meneruskan fitur terverifikasi untuk inferensi deterministik."

    def run(self) -> Data:
        data = AnalysisInput.model_validate(self.payload())
        return self.result_data({"features": data.features, "encounter_id": data.encounter_id})


class PMRInferenceGuard(PMRJsonComponent):
    display_name = "PMR InferenceGuard"
    description = "Memvalidasi fitur melalui InferenceGuard sebelum model dipanggil."

    def run(self) -> Data:
        data = AnalysisInput.model_validate(self.payload())
        from src.models.inference_guard import InferenceGuard
        guard = InferenceGuard.load()
        guard.validate_and_extract(data.features)
        return self.result_data({"accepted": True, "features": data.features})


class PMRXGBoostScorer(PMRJsonComponent):
    display_name = "PMR XGBoost Scorer"
    description = "Skor ML deterministik; tidak membuat rekomendasi terapi."

    def run(self) -> Data:
        return self.result_data(run_phase_a(self.payload()))


class PMRSHAPExplainer(PMRJsonComponent):
    display_name = "PMR SHAP Explainer"
    description = "Menjelaskan kontributor skor dari hasil ML terverifikasi."

    outputs = [Output(name="result", display_name="Penjelasan", method="run", tool_mode=True)]

    def run(self) -> Data:
        return self.result_data(run_phase_a(self.payload()))


class PMRThresholdMapper(PMRJsonComponent):
    display_name = "PMR Threshold Mapper"
    description = "Memetakan probabilitas ke tier tanpa menurunkan prioritas."

    def run(self) -> Data:
        payload = self.payload()
        probability = float(payload.get("probability", payload.get("risk_probability", 0)))
        return self.result_data({"probability": probability, "tier_ml": tier_from_score(probability)})
