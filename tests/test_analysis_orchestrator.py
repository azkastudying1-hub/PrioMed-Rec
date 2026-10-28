import pytest

from api.services.analysis_orchestrator import run_analysis
from api.services.langflow_client import LangflowUnavailable


class FailingClient:
    async def run_master(self, payload):
        raise LangflowUnavailable("simulated outage")


@pytest.mark.asyncio
async def test_orchestrator_falls_back_to_local(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "langflow_first")
    monkeypatch.setattr("api.services.analysis_orchestrator.run_full", lambda request: __import__("priomedrec_core.contracts", fromlist=["AnalysisResult"]).AnalysisResult(patient_id=request.patient_id, encounter_id=request.encounter_id, phase_a={"probability": 0.1, "model_version": "m"}, phase_b={"findings": [], "rule_version": "r"}, priority={"final_tier": "LOW"}, versions={"model": "m", "rules": "r"}))
    result = await run_analysis({"patient_id": "SYNTHETIC-1", "encounter_id": "ENC-1"}, FailingClient())
    assert result["execution"]["path"] == "local_fallback"
    assert result["execution"]["fallback_reason"] == "LangflowUnavailable"
