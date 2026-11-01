"""Service-to-service deterministic boundary used by Langflow."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def test_internal_priority_requires_service_key(monkeypatch):
    monkeypatch.setenv("SERVICE_API_KEY_LANGFLOW", "test-service-key")
    client = TestClient(app)

    denied = client.post("/internal/v1/priority", json={"ml_score": 0.8})
    assert denied.status_code == 401


def test_internal_priority_returns_composite_tier(monkeypatch):
    monkeypatch.setenv("SERVICE_API_KEY_LANGFLOW", "test-service-key")
    client = TestClient(app)

    response = client.post(
        "/internal/v1/priority",
        headers={"X-Service-Key": "test-service-key"},
        json={"ml_score": 0.2, "discrepancies": [{"severity_tier": 1}]},
    )
    assert response.status_code == 200
    assert response.json()["final_tier"] == "HIGH"


def test_internal_analysis_run_never_calls_langflow(monkeypatch):
    monkeypatch.setenv("SERVICE_API_KEY_LANGFLOW", "test-service-key")
    client = TestClient(app)

    payload = {
        "patient_id": "SYNTHETIC-001",
        "encounter_id": "ENC-001",
        "features": {},
        "pre_admission_meds": [],
        "admission_meds": [],
    }
    response = client.post(
        "/internal/v1/analysis/run",
        headers={"X-Service-Key": "test-service-key"},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["patient_id"] == payload["patient_id"]
    assert "phase_a" in body and "phase_b" in body
    assert "execution" not in body
