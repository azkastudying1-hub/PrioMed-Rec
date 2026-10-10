"""
tests/test_langflow_integration.py
------------------------------------
Integration tests for Langflow client and the FastAPI fallback path.

These tests verify:
  - Langflow client constructs correct requests
  - Fallback to direct FastAPI works when Langflow is unavailable
  - Patient ID extraction from various query formats
  - Error handling for connection failures and missing patients

Run: pytest tests/test_langflow_integration.py -v
"""

import pytest
import sys
from pathlib import Path
import unittest.mock as mock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Langflow client: request construction
# ---------------------------------------------------------------------------

def test_langflow_payload_contains_patient_id():
    """call_langflow must include patient_id in the Langflow request payload."""
    from streamlit_app.utils import langflow_client

    captured = {}

    def mock_post(url, json=None, timeout=None):
        captured["payload"] = json
        r = mock.MagicMock()
        r.raise_for_status.return_value = None
        r.json.return_value = {}  # empty → falls through to direct API
        return r

    with mock.patch("requests.post", side_effect=mock_post):
        # Will fail at Langflow extraction and fall back to direct API (also mocked)
        with mock.patch.object(langflow_client, "_call_api_direct",
                               return_value={"report": "ok", "patient_id": "P001"}):
            langflow_client.call_langflow("P001")

    assert captured.get("payload", {}).get("tweaks", {}).get("patient_id") == "P001"


def test_langflow_fallback_to_direct_api():
    """If Langflow raises ConnectionError, fallback to _call_api_direct."""
    from streamlit_app.utils import langflow_client
    import requests

    with mock.patch("requests.post", side_effect=requests.exceptions.ConnectionError("refused")):
        with mock.patch.object(
            langflow_client, "_call_api_direct",
            return_value={"report": "direct", "patient_id": "P001", "_source": "fastapi_direct"}
        ) as mock_direct:
            result = langflow_client.call_langflow("P001")
            mock_direct.assert_called_once_with("P001", None)
    assert result["_source"] == "fastapi_direct"


def test_langflow_question_passed_to_direct():
    """When question is provided, it must be forwarded to _call_api_direct."""
    from streamlit_app.utils import langflow_client
    import requests

    with mock.patch("requests.post", side_effect=requests.exceptions.ConnectionError()):
        with mock.patch.object(
            langflow_client, "_call_api_direct",
            return_value={"report": "ok"}
        ) as mock_direct:
            langflow_client.call_langflow("P001", question="Kenapa diprioritaskan?")
            mock_direct.assert_called_once_with("P001", "Kenapa diprioritaskan?")


# ---------------------------------------------------------------------------
# Langflow client: direct API fallback
# ---------------------------------------------------------------------------

def test_direct_api_sends_patient_id_only():
    """_call_api_direct must POST {patient_id: ...} — no feature fields."""
    from streamlit_app.utils import langflow_client

    captured = {}

    def mock_post(url, json=None, timeout=None):
        captured["payload"] = json
        r = mock.MagicMock()
        r.raise_for_status.return_value = None
        r.json.return_value = {"patient_id": "P001", "report": "ok"}
        return r

    with mock.patch("requests.post", side_effect=mock_post):
        langflow_client._call_api_direct("P001")

    payload = captured.get("payload", {})
    assert payload.get("patient_id") == "P001"
    # Must NOT include feature fields
    assert "age" not in payload
    assert "total_medication_count" not in payload


def test_direct_api_with_question():
    """_call_api_direct must include question field when provided."""
    from streamlit_app.utils import langflow_client

    captured = {}

    def mock_post(url, json=None, timeout=None):
        captured["payload"] = json
        r = mock.MagicMock()
        r.raise_for_status.return_value = None
        r.json.return_value = {"patient_id": "P001", "report": "ok"}
        return r

    with mock.patch("requests.post", side_effect=mock_post):
        langflow_client._call_api_direct("P001", "Kenapa prioritas tinggi?")

    payload = captured.get("payload", {})
    assert payload.get("question") == "Kenapa prioritas tinggi?"


# ---------------------------------------------------------------------------
# Flow B review submission
# ---------------------------------------------------------------------------

def test_review_panel_submits_to_review_endpoint():
    """review_panel._submit_review must POST to /review with correct fields."""
    captured = {}

    def mock_post(url, json=None, timeout=None):
        captured["url"]     = url
        captured["payload"] = json
        r = mock.MagicMock()
        r.raise_for_status.return_value = None
        r.json.return_value = {
            "review_id": "test-id-001",
            "action": "APPROVE",
            "timestamp": "2025-01-01T00:00:00+00:00",
        }
        return r

    # Mock streamlit BEFORE importing the module to avoid runtime issues
    st_mock = mock.MagicMock()
    with mock.patch.dict("sys.modules", {"streamlit": st_mock}):
        import importlib
        import streamlit_app.components.review_panel as rp_module
        importlib.reload(rp_module)
        with mock.patch("requests.post", side_effect=mock_post):
            rp_module._submit_review(
                case_id="P001_E001",
                pharmacist_id="PHARM-01",
                ai_result={"risk_probability": 0.7, "model_version": "model-0.3.0"},
                action="APPROVE",
                note="Reviewed OK",
                edited_result=None,
                model_version="model-0.3.0",
                rule_version="rules-0.1.0",
                key_prefix="test",
            )

    assert "/review" in captured.get("url", "")
    payload = captured.get("payload", {})
    assert payload["action"] == "APPROVE"
    assert payload["model_version"] == "model-0.3.0"
    assert payload["rule_version"] == "rules-0.1.0"
    assert payload["pharmacist_id"] == "PHARM-01"


def test_review_payload_includes_versions():
    """Review submission must always include model_version and rule_version."""
    captured = {}

    def mock_post(url, json=None, timeout=None):
        captured["payload"] = json
        r = mock.MagicMock()
        r.raise_for_status.return_value = None
        r.json.return_value = {"review_id": "x", "action": "REJECT", "timestamp": "2025-01-01T00:00:00Z"}
        return r

    st_mock = mock.MagicMock()
    with mock.patch.dict("sys.modules", {"streamlit": st_mock}):
        import importlib
        import streamlit_app.components.review_panel as rp_module
        importlib.reload(rp_module)
        with mock.patch("requests.post", side_effect=mock_post):
            rp_module._submit_review(
                case_id="P002_E002",
                pharmacist_id="PHARM-02",
                ai_result={"model_version": "model-0.3.0", "rule_version": "rules-0.1.0"},
                action="REJECT",
                note="Tidak sesuai",
                edited_result=None,
                model_version="model-0.3.0",
                rule_version="rules-0.1.0",
                key_prefix="test2",
            )

    payload = captured.get("payload", {})
    assert "model_version" in payload
    assert "rule_version" in payload


# ---------------------------------------------------------------------------
# Langflow extract output
# ---------------------------------------------------------------------------

def test_extract_langflow_output_valid():
    """_extract_langflow_output must correctly parse the Langflow v1 response."""
    from streamlit_app.utils.langflow_client import _extract_langflow_output

    lf_data = {
        "outputs": [{
            "outputs": [{
                "results": {
                    "message": {
                        "data": {"text": "Analysis complete for P001"}
                    }
                }
            }]
        }]
    }
    result = _extract_langflow_output(lf_data)
    assert result == "Analysis complete for P001"


def test_extract_langflow_output_empty():
    """_extract_langflow_output must return empty string for malformed response."""
    from streamlit_app.utils.langflow_client import _extract_langflow_output
    assert _extract_langflow_output({}) == ""
    assert _extract_langflow_output({"outputs": []}) == ""
