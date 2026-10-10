"""
tests/test_api.py
------------------
Unit tests for Sub-Task 9: FastAPI backend.

Uses FastAPI TestClient — no live server required.
Tests happy paths, invalid inputs, error handling, and schema contracts.

Run: pytest tests/test_api.py -v
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from api.main import app
from src.features.feature_pipeline import FEATURE_COLUMNS

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Fixture: valid feature payload
# ---------------------------------------------------------------------------

def _valid_prioritize_payload() -> dict:
    return {
        "age": 65.0,
        "age_65_plus": 1,
        "gender_encoded": 0,
        "pre_admission_medication_count": 5,
        "admission_medication_count": 6,
        "total_medication_count": 8,
        "new_medication_count": 3,
        "discontinued_medication_count": 2,
        "polypharmacy_flag": 1,
        "high_alert_flag": 1,
        "high_alert_count": 2,
        "potential_duplicate_candidates": 1,
        "active_condition_count": 4,
        "prior_encounter_count": 12,
        "allergy_count": 0,
        "has_drug_allergy": 0,
    }


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:

    def test_health_status_ok(self):
        res = client.get("/health")
        assert res.status_code == 200

    def test_health_response_schema(self):
        res = client.get("/health")
        body = res.json()
        for key in ["status", "model_version", "rule_version", "api_version"]:
            assert key in body, f"Missing key: {key}"

    def test_health_status_value(self):
        res = client.get("/health")
        assert res.json()["status"] == "ok"

    def test_health_api_version_format(self):
        res = client.get("/health")
        assert res.json()["api_version"] != ""


# ---------------------------------------------------------------------------
# POST /prioritize
# ---------------------------------------------------------------------------

class TestPrioritizeEndpoint:

    def test_happy_path_200(self):
        res = client.post("/prioritize", json=_valid_prioritize_payload())
        assert res.status_code == 200

    def test_response_schema(self):
        res = client.post("/prioritize", json=_valid_prioritize_payload())
        body = res.json()
        for key in ["risk_probability", "priority", "model_version", "threshold_version"]:
            assert key in body, f"Missing key: {key}"

    def test_priority_values(self):
        res = client.post("/prioritize", json=_valid_prioritize_payload())
        assert res.json()["priority"] in {"LOW", "MEDIUM", "HIGH"}

    def test_risk_probability_range(self):
        res = client.post("/prioritize", json=_valid_prioritize_payload())
        prob = res.json()["risk_probability"]
        assert 0.0 <= prob <= 1.0

    def test_model_version_present(self):
        res = client.post("/prioritize", json=_valid_prioritize_payload())
        assert res.json()["model_version"].startswith("model-")

    def test_top_features_list(self):
        res = client.post("/prioritize", json=_valid_prioritize_payload())
        top = res.json().get("top_features", [])
        assert isinstance(top, list)

    def test_top_features_schema(self):
        res = client.post("/prioritize", json=_valid_prioritize_payload())
        for feat in res.json().get("top_features", []):
            assert "feature" in feat
            assert "shap_value" in feat
            assert "direction" in feat

    def test_negative_age_returns_422(self):
        payload = _valid_prioritize_payload()
        payload["age"] = -1
        res = client.post("/prioritize", json=payload)
        assert res.status_code == 422

    def test_negative_medication_count_returns_422(self):
        payload = _valid_prioritize_payload()
        payload["total_medication_count"] = -5
        res = client.post("/prioritize", json=payload)
        assert res.status_code == 422

    def test_missing_required_field_returns_422(self):
        payload = _valid_prioritize_payload()
        del payload["age"]
        res = client.post("/prioritize", json=payload)
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# POST /discrepancies
# ---------------------------------------------------------------------------

class TestDiscrepancyEndpoint:

    def _base_request(self) -> dict:
        return {
            "patient_id":   "PAT-001",
            "encounter_id": "ENC-001",
            "pre_admission_meds": [
                {"medication_code": "316049", "medication_name": "warfarin 5 MG"}
            ],
            "admission_meds": [],
        }

    def test_happy_path_200(self):
        res = client.post("/discrepancies", json=self._base_request())
        assert res.status_code == 200

    def test_response_schema(self):
        res = client.post("/discrepancies", json=self._base_request())
        body = res.json()
        for key in ["patient_id", "encounter_id", "rule_version", "flags"]:
            assert key in body

    def test_flags_is_list(self):
        res = client.post("/discrepancies", json=self._base_request())
        assert isinstance(res.json()["flags"], list)

    def test_empty_meds_returns_empty_flags(self):
        payload = {
            "patient_id": "PAT-002",
            "encounter_id": "ENC-002",
            "pre_admission_meds": [],
            "admission_meds": [],
        }
        res = client.post("/discrepancies", json=payload)
        assert res.status_code == 200
        assert res.json()["flags"] == []

    def test_verification_required_true_on_flags(self):
        res = client.post("/discrepancies", json=self._base_request())
        for flag in res.json().get("flags", []):
            assert flag["verification_required"] is True

    def test_rule_version_present(self):
        res = client.post("/discrepancies", json=self._base_request())
        assert res.json()["rule_version"] != ""


# ---------------------------------------------------------------------------
# POST /review
# ---------------------------------------------------------------------------

class TestReviewEndpoint:

    def _base_review(self, action: str = "APPROVE") -> dict:
        return {
            "case_id":       "CASE-001",
            "pharmacist_id": "PHARM-01",
            "ai_result":     {"risk_probability": 0.75, "priority": "HIGH"},
            "action":        action,
            "pharmacist_note": "Reviewed and confirmed.",
        }

    def test_approve_200(self):
        res = client.post("/review", json=self._base_review("APPROVE"))
        assert res.status_code == 200

    def test_reject_200(self):
        res = client.post("/review", json=self._base_review("REJECT"))
        assert res.status_code == 200

    def test_edit_200(self):
        payload = self._base_review("EDIT")
        payload["edited_result"] = {"risk_probability": 0.90, "priority": "HIGH"}
        res = client.post("/review", json=payload)
        assert res.status_code == 200

    def test_edit_without_edited_result_returns_422(self):
        payload = self._base_review("EDIT")
        # no edited_result
        res = client.post("/review", json=payload)
        assert res.status_code == 422

    def test_invalid_action_returns_422(self):
        payload = self._base_review("PRESCRIBE")
        res = client.post("/review", json=payload)
        assert res.status_code == 422

    def test_response_schema(self):
        res = client.post("/review", json=self._base_review("APPROVE"))
        body = res.json()
        for key in ["review_id", "case_id", "action", "timestamp", "pharmacist_id", "final_result"]:
            assert key in body

    def test_approve_action_recorded(self):
        res = client.post("/review", json=self._base_review("APPROVE"))
        assert res.json()["action"] == "APPROVE"

    def test_final_result_has_pharmacist_action(self):
        res = client.post("/review", json=self._base_review("APPROVE"))
        assert "pharmacist_action" in res.json()["final_result"]


# ---------------------------------------------------------------------------
# GET /patient/{patient_id}  — new endpoint (Sub-Task 9)
# ---------------------------------------------------------------------------

_KNOWN_PATIENT_ID = "0002f562-87d8-d5f3-0021-3ec2970fe161"
_KNOWN_ENCOUNTER_ID = "0002f562-87d8-d5f3-0d5e-213d59d21eac"


class TestPatientEndpoint:
    """Tests for GET /patient/{patient_id}."""

    def test_known_patient_returns_200(self):
        resp = client.get(f"/patient/{_KNOWN_PATIENT_ID}")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["patient_id"] == _KNOWN_PATIENT_ID
        assert isinstance(data["encounters"], list)
        assert data["encounter_count"] >= 1

    def test_unknown_patient_returns_404(self):
        resp = client.get("/patient/NONEXISTENT-PATIENT-XYZ")
        assert resp.status_code == 404

    def test_patient_response_has_latest_admission(self):
        resp = client.get(f"/patient/{_KNOWN_PATIENT_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["latest_admission"] is not None
        latest = data["latest_admission"]
        assert "encounter_id" in latest
        assert "encounter_start" in latest
        assert "encounter_class" in latest

    def test_sample_patients_endpoint(self):
        resp = client.get("/patients/sample?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "patient_ids" in data
        assert len(data["patient_ids"]) <= 5
        assert data["count"] == len(data["patient_ids"])

    def test_sample_patients_limit_validation(self):
        resp = client.get("/patients/sample?limit=200")
        assert resp.status_code == 422


class TestAnalyzePatientIdMode:
    """Tests for POST /analyze in patient_id-driven simple mode."""

    def test_analyze_with_patient_id_only(self):
        """POST /analyze with only patient_id should return a full result."""
        resp = client.post("/analyze", json={"patient_id": _KNOWN_PATIENT_ID})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["patient_id"] == _KNOWN_PATIENT_ID
        assert "discrepancy_likelihood" in data
        assert "review_priority" in data
        assert data["review_priority"] in {"HIGH", "MEDIUM", "LOW"}
        assert 0.0 <= data["discrepancy_likelihood"] <= 1.0

    def test_analyze_unknown_patient_returns_404(self):
        resp = client.post("/analyze", json={"patient_id": "NONEXISTENT-XYZ"})
        assert resp.status_code == 404

    def test_analyze_with_question(self):
        resp = client.post("/analyze", json={
            "patient_id": _KNOWN_PATIENT_ID,
            "question": "Kenapa diprioritaskan?",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "report" in data

    def test_analyze_response_has_backward_compat_fields(self):
        """risk_probability and priority aliases must exist for backward compat."""
        resp = client.post("/analyze", json={"patient_id": _KNOWN_PATIENT_ID})
        assert resp.status_code == 200
        data = resp.json()
        assert "risk_probability" in data  # backward compat alias
        assert "priority" in data          # backward compat alias
        # Must equal the new canonical fields
        assert data["risk_probability"] == data["discrepancy_likelihood"]
        assert data["priority"] == data["review_priority"]

    def test_analyze_response_has_no_feature_vector_exposed(self):
        """Feature vector must NOT appear in /analyze response."""
        resp = client.post("/analyze", json={"patient_id": _KNOWN_PATIENT_ID})
        assert resp.status_code == 200
        data = resp.json()
        # These raw feature fields must not appear in the user-facing response
        assert "age" not in data
        assert "total_medication_count" not in data
        assert "discontinued_medication_count" not in data


class TestReviewVersionAudit:
    """Tests that /review response includes model_version and rule_version."""

    def _submit(self, extra: dict = None) -> dict:
        payload = {
            "case_id": "CASE-TEST-001",
            "pharmacist_id": "PHARM-TEST",
            "ai_result": {
                "risk_probability": 0.7,
                "priority": "HIGH",
                "model_version": "model-0.3.0",
                "rule_version": "rules-0.1.0",
            },
            "action": "APPROVE",
            "pharmacist_note": "OK",
        }
        if extra:
            payload.update(extra)
        resp = client.post("/review", json=payload)
        assert resp.status_code == 200, resp.text
        return resp.json()

    def test_review_response_has_model_version(self):
        data = self._submit()
        assert "model_version" in data
        assert data["model_version"] != ""

    def test_review_response_has_rule_version(self):
        data = self._submit()
        assert "rule_version" in data
        assert data["rule_version"] != ""

    def test_review_version_from_ai_result(self):
        """model_version pulled from ai_result when not in request directly."""
        data = self._submit()
        assert data["model_version"] == "model-0.3.0"
        assert data["rule_version"] == "rules-0.1.0"

    def test_review_explicit_version_overrides(self):
        """Explicit model_version in request overrides ai_result value."""
        data = self._submit({
            "model_version": "model-custom",
            "rule_version":  "rules-custom",
        })
        assert data["model_version"] == "model-custom"
        assert data["rule_version"] == "rules-custom"


# ---------------------------------------------------------------------------
# POST /prioritize/batch
# ---------------------------------------------------------------------------

class TestBatchPrioritization:

    def test_batch_prioritize_default(self):
        res = client.post("/prioritize/batch", json={"limit": 10})
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["total_analyzed"] == 10
        assert "ranked_patients" in data
        assert len(data["ranked_patients"]) == 10
        # Verify rank ordering
        ranks = [p["rank"] for p in data["ranked_patients"]]
        assert ranks == list(range(1, 11))
        # Verify likelihood is sorted descending
        prob_list = [p["discrepancy_likelihood"] for p in data["ranked_patients"]]
        assert prob_list == sorted(prob_list, reverse=True)

    def test_batch_prioritize_filter(self):
        res = client.post("/prioritize/batch", json={"limit": 20, "priority_filter": "HIGH"})
        assert res.status_code == 200
        data = res.json()
        for item in data["ranked_patients"]:
            assert item["review_priority"] == "HIGH"

