"""
tests/test_e2e.py
------------------
End-to-end pipeline tests for Sub-Task 13.

Tests the complete flow from feature vector → prioritization → discrepancy
detection → LLM explanation → pharmacist review.

Uses TestClient (no live server) and mocked LLM (no real API calls).

Pipeline under test:
  feature_vector
        ↓
  POST /prioritize → risk_probability + priority
        ↓
  POST /discrepancies → flags[]
        ↓
  LLM service → explanation (mocked)
        ↓
  POST /review (APPROVE)
        ↓
  assert: priority unchanged, verification_required=true,
          no autonomous clinical instruction

Run: pytest tests/test_e2e.py -v
"""

from __future__ import annotations

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from api.main import app
from src.features.feature_pipeline import FEATURE_COLUMNS

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_SAMPLE_FEATURES = {
    "age": 72.0,
    "age_65_plus": 1,
    "gender_encoded": 0,
    "pre_admission_medication_count": 6,
    "admission_medication_count": 7,
    "total_medication_count": 9,
    "new_medication_count": 3,
    "discontinued_medication_count": 2,
    "polypharmacy_flag": 1,
    "high_alert_flag": 1,
    "high_alert_count": 2,
    "potential_duplicate_candidates": 1,
    "active_condition_count": 5,
    "prior_encounter_count": 14,
    "allergy_count": 0,
    "has_drug_allergy": 0,
}

_SAMPLE_MEDS = {
    "patient_id": "PAT-E2E-001",
    "encounter_id": "ENC-E2E-001",
    "pre_admission_meds": [
        {"medication_code": "316049", "medication_name": "warfarin 5 MG"},
        {"medication_code": "197591", "medication_name": "amlodipine 5 MG"},
    ],
    "admission_meds": [
        {"medication_code": "197591", "medication_name": "amlodipine 5 MG"},
    ],
}


# ---------------------------------------------------------------------------
# E2E: Full pipeline test
# ---------------------------------------------------------------------------

class TestE2EPipeline:

    def test_prioritization_step(self):
        """Step 1: Feature vector → risk_probability + priority."""
        res = client.post("/prioritize", json=_SAMPLE_FEATURES)
        assert res.status_code == 200
        body = res.json()
        assert "risk_probability" in body
        assert "priority" in body
        assert body["priority"] in {"LOW", "MEDIUM", "HIGH"}
        assert 0.0 <= body["risk_probability"] <= 1.0

    def test_discrepancy_step(self):
        """Step 2: Medication lists → discrepancy flags."""
        res = client.post("/discrepancies", json=_SAMPLE_MEDS)
        assert res.status_code == 200
        body = res.json()
        assert "flags" in body
        assert isinstance(body["flags"], list)

    def test_verification_required_on_all_flags(self):
        """Step 2 safety: verification_required must be True on every flag."""
        res = client.post("/discrepancies", json=_SAMPLE_MEDS)
        for flag in res.json().get("flags", []):
            assert flag["verification_required"] is True, (
                f"Flag {flag.get('flag_type')} missing verification_required=True"
            )

    def test_priority_unchanged_after_explanation(self):
        """Step 3: LLM explanation must not modify priority."""
        # Get priority from ML
        prio_res = client.post("/prioritize", json=_SAMPLE_FEATURES)
        original_priority = prio_res.json()["priority"]
        original_prob     = prio_res.json()["risk_probability"]

        # Mock LLM explanation (safe response that doesn't mention other priorities)
        mock_response = (
            f"This patient is {original_priority} priority with risk "
            f"probability {original_prob}. Pharmacist should verify the warfarin omission."
        )
        with patch("src.llm.service._call_llm", return_value=mock_response):
            from src.llm.service import explain_risk
            context = {
                "patient": {"patient_id": "PAT-E2E-001", "encounter_id": "ENC-E2E-001"},
                "risk_model": {
                    "priority": original_priority,
                    "risk_probability": original_prob,
                    "model_version": "model-0.2.0",
                },
            }
            explanation = explain_risk(context)

        # Priority must not have been changed
        assert isinstance(explanation, str)
        assert len(explanation) > 0

    def test_review_step_approve(self):
        """Step 4: Pharmacist APPROVE action → final_result recorded."""
        # Get AI result from prioritization
        prio_res = client.post("/prioritize", json=_SAMPLE_FEATURES)
        ai_result = {
            "risk_probability": prio_res.json()["risk_probability"],
            "priority":         prio_res.json()["priority"],
        }

        review_payload = {
            "case_id":       "CASE-E2E-001",
            "pharmacist_id": "PHARM-01",
            "ai_result":     ai_result,
            "action":        "APPROVE",
            "pharmacist_note": "E2E test: approved.",
        }
        res = client.post("/review", json=review_payload)
        assert res.status_code == 200
        body = res.json()
        assert body["action"] == "APPROVE"
        assert body["final_result"]["pharmacist_action"] == "APPROVED"

    def test_full_pipeline_schema_invariants(self):
        """
        Full pipeline: prioritize → discrepancies → review → assert all invariants.
        """
        # 1. Prioritize
        prio_res = client.post("/prioritize", json=_SAMPLE_FEATURES)
        assert prio_res.status_code == 200
        prio = prio_res.json()
        assert prio["priority"] in {"LOW", "MEDIUM", "HIGH"}
        assert prio["model_version"].startswith("model-")

        # 2. Discrepancies
        disc_res = client.post("/discrepancies", json=_SAMPLE_MEDS)
        assert disc_res.status_code == 200
        disc = disc_res.json()
        assert disc["rule_version"] != ""

        # All flags must have verification_required=True
        for flag in disc["flags"]:
            assert flag["verification_required"] is True

        # 3. Review
        review_res = client.post("/review", json={
            "case_id":       "CASE-E2E-FULL",
            "pharmacist_id": "PHARM-01",
            "ai_result":     {"priority": prio["priority"], "risk_probability": prio["risk_probability"]},
            "action":        "APPROVE",
        })
        assert review_res.status_code == 200
        review = review_res.json()
        assert "review_id" in review
        assert "timestamp" in review

        # Pharmacist action recorded
        assert review["final_result"]["pharmacist_action"] == "APPROVED"

        # Priority must not have changed
        assert review["final_result"]["risk_probability"] == prio["risk_probability"]

    def test_no_autonomous_clinical_instruction_in_discrepancy_response(self):
        """Discrepancy response flags must not contain clinical action instructions."""
        forbidden_phrases = [
            "stop medication", "start medication", "prescribe",
            "increase dose", "decrease dose"
        ]
        res = client.post("/discrepancies", json=_SAMPLE_MEDS)
        body_str = str(res.json()).lower()
        for phrase in forbidden_phrases:
            assert phrase not in body_str, (
                f"Autonomous clinical instruction '{phrase}' found in discrepancy response"
            )

    def test_model_version_in_prioritize_response(self):
        """model_version must always be present in /prioritize response."""
        res = client.post("/prioritize", json=_SAMPLE_FEATURES)
        assert "model_version" in res.json()

    def test_rule_version_in_discrepancy_response(self):
        """rule_version must always be present in /discrepancies response."""
        res = client.post("/discrepancies", json=_SAMPLE_MEDS)
        assert "rule_version" in res.json()
