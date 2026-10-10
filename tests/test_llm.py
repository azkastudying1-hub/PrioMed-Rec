"""
tests/test_llm.py
------------------
Unit tests for Sub-Task 10: LLM module.

Tests prompts, schemas, and service layer (mocked — no real API calls).

Run: pytest tests/test_llm.py -v
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock

from src.llm.prompts.task_prompts import (
    patient_summary_prompt,
    risk_explanation_prompt,
    discrepancy_explanation_prompt,
    pharmacist_qa_prompt,
    _system_prompt,
)
from src.llm.schemas.llm_output import LLMOutput, DiscrepancyItem
from src.llm.validators.output_validator import validate_output, GuardrailViolation


# ---------------------------------------------------------------------------
# Sample context fixture
# ---------------------------------------------------------------------------

def _sample_context() -> dict:
    return {
        "patient": {
            "patient_id": "P001",
            "encounter_id": "E001",
            "age": 72,
            "sex": "F",
        },
        "medications": {
            "previous": [{"medication_name": "warfarin 5 MG"}],
            "admission": [{"medication_name": "amlodipine 5 MG"}],
        },
        "clinical_context": {
            "conditions": ["Atrial fibrillation"],
            "comorbidity_count": 4,
        },
        "risk_model": {
            "risk_probability": 0.87,
            "priority": "HIGH",
            "model_version": "model-0.2.0",
        },
        "discrepancy_engine": {
            "flags": [
                {
                    "flag_type": "POTENTIAL_OMISSION",
                    "medication_name": "warfarin 5 MG",
                    "verification_required": True,
                }
            ]
        },
        "explainability": {
            "top_features": [
                {"feature": "total_medication_count", "shap_value": 0.12, "direction": "increases_risk"}
            ]
        },
    }


# ---------------------------------------------------------------------------
# Prompt construction tests
# ---------------------------------------------------------------------------

class TestTaskPrompts:

    def test_system_prompt_not_empty(self):
        sp = _system_prompt()
        assert len(sp) > 100

    def test_system_prompt_contains_key_phrase(self):
        sp = _system_prompt()
        assert "pharmacist" in sp.lower()
        assert "must never" in sp.lower()

    def test_patient_summary_prompt_contains_context(self):
        ctx = _sample_context()
        prompt = patient_summary_prompt(ctx)
        assert "P001" in prompt
        assert "summarize" in prompt.lower()

    def test_risk_explanation_prompt_structure(self):
        ctx = _sample_context()
        prompt = risk_explanation_prompt(ctx)
        assert "risk probability" in prompt.lower()
        assert "do not recalculate" in prompt.lower()

    def test_discrepancy_explanation_prompt_structure(self):
        ctx = _sample_context()
        prompt = discrepancy_explanation_prompt(ctx)
        assert "discrepancy" in prompt.lower()
        assert "verification" in prompt.lower()

    def test_qa_prompt_includes_question(self):
        ctx = _sample_context()
        question = "Why is this patient HIGH priority?"
        prompt = pharmacist_qa_prompt(question, ctx)
        assert question in prompt

    def test_qa_prompt_context_included(self):
        ctx = _sample_context()
        prompt = pharmacist_qa_prompt("What are the flags?", ctx)
        assert "P001" in prompt


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestLLMOutputSchema:

    def test_valid_output_parses(self):
        data = {
            "patient_id": "P001",
            "encounter_id": "E001",
            "priority": "HIGH",
            "risk_probability": 0.87,
            "summary": "Patient is at high risk.",
            "key_risk_factors": ["polypharmacy", "high_alert_medication"],
            "potential_discrepancies": [
                {"type": "POTENTIAL_OMISSION", "medication": "warfarin", "verification_required": True}
            ],
            "recommended_review_focus": ["Verify warfarin history"],
            "verification_required": True,
            "limitations": ["Synthetic data only"],
        }
        out = LLMOutput(**data)
        assert out.patient_id == "P001"
        assert out.verification_required is True

    def test_risk_probability_range(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            LLMOutput(
                patient_id="P001", encounter_id="E001",
                priority="HIGH", risk_probability=1.5,
                summary="test",
            )

    def test_verification_required_defaults_true(self):
        out = LLMOutput(
            patient_id="P001", encounter_id="E001",
            priority="HIGH", risk_probability=0.8,
            summary="test",
        )
        assert out.verification_required is True

    def test_discrepancy_item_verification_required(self):
        item = DiscrepancyItem(type="POTENTIAL_OMISSION", medication="warfarin")
        assert item.verification_required is True


# ---------------------------------------------------------------------------
# Service layer tests (mocked)
# ---------------------------------------------------------------------------

class TestLLMService:

    def _mock_llm(self, response_text: str):
        """Patch _call_llm to return a fixed response."""
        return patch("src.llm.service._call_llm", return_value=response_text)

    def test_generate_summary_returns_string(self):
        ctx = _sample_context()
        with self._mock_llm("Patient P001 is HIGH priority. Verify warfarin omission."):
            from src.llm.service import generate_summary
            result = generate_summary(ctx)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_explain_risk_returns_string(self):
        ctx = _sample_context()
        with self._mock_llm("HIGH priority due to total_medication_count and high_alert_flag."):
            from src.llm.service import explain_risk
            result = explain_risk(ctx)
        assert isinstance(result, str)

    def test_explain_discrepancy_returns_string(self):
        ctx = _sample_context()
        with self._mock_llm("Potential omission of warfarin. Requires verification."):
            from src.llm.service import explain_discrepancy
            result = explain_discrepancy(ctx)
        assert isinstance(result, str)

    def test_answer_query_returns_string(self):
        ctx = _sample_context()
        with self._mock_llm("The patient is HIGH because of medication burden."):
            from src.llm.service import answer_query
            result = answer_query("Why is this patient HIGH?", ctx)
        assert isinstance(result, str)

    def test_service_returns_fallback_on_api_error(self):
        ctx = _sample_context()
        with patch("src.llm.service._call_llm", side_effect=RuntimeError("API down")):
            from src.llm.service import generate_summary
            result = generate_summary(ctx)
        assert "unavailable" in result.lower() or "pharmacist" in result.lower()

    def test_service_blocks_guardrail_violation(self):
        ctx = _sample_context()
        # Response tries to tell the user to stop medication
        bad_response = "The patient should stop medication warfarin immediately."
        with self._mock_llm(bad_response):
            from src.llm.service import generate_summary
            result = generate_summary(ctx)
        assert "guardrail" in result.lower() or "blocked" in result.lower()
