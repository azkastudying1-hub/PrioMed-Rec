import asyncio
import pytest

from api.services.analysis_orchestrator import run_analysis
from api.services.langflow_client import LangflowUnavailable


class FailingClient:
    async def run_master(self, payload):
        raise LangflowUnavailable("simulated outage")


def _make_result(request):
    from priomedrec_core.contracts import AnalysisResult
    return AnalysisResult(
        patient_id=request.patient_id,
        encounter_id=request.encounter_id,
        phase_a={"probability": 0.1, "model_version": "m"},
        phase_b={"findings": [], "rule_version": "r"},
        priority={"final_tier": "LOW"},
        versions={"model": "m", "rules": "r"},
    )


def test_orchestrator_falls_back_to_local(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "langflow_first")
    monkeypatch.setattr("api.services.analysis_orchestrator.run_full", _make_result)
    result = asyncio.run(
        run_analysis({"patient_id": "SYNTHETIC-1", "encounter_id": "ENC-1"}, FailingClient())
    )
    assert result["execution"]["path"] == "local_fallback"
    assert result["execution"]["fallback_reason"] == "LangflowUnavailable"
