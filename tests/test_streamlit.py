"""
tests/test_streamlit.py
------------------------
Tests for streamlit_app components (non-rendering unit tests).

Tests import correctness, chat handler logic, and result_view schema handling.
Does NOT call Streamlit's st.* functions (those require a running runtime).

Run: pytest tests/test_streamlit.py -v
"""

import pytest
import sys
from pathlib import Path

# Ensure project root on sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Import tests (verify no syntax / import errors)
# ---------------------------------------------------------------------------

def test_chat_handler_imports():
    """chat_handler must import without error."""
    from streamlit_app.components.chat_handler import (
        handle_chat,
        extract_patient_id,
        is_question,
    )
    assert callable(handle_chat)
    assert callable(extract_patient_id)
    assert callable(is_question)


def test_langflow_client_imports():
    """langflow_client must import without error."""
    from streamlit_app.utils.langflow_client import (
        call_langflow,
        check_api_health,
        _call_api_direct,
    )
    assert callable(call_langflow)
    assert callable(check_api_health)


def test_result_view_imports():
    """result_view must import without error (does not call st.*)."""
    # Patch streamlit before import to avoid runtime errors
    import unittest.mock as mock
    with mock.patch.dict("sys.modules", {"streamlit": mock.MagicMock()}):
        import importlib
        import streamlit_app.components.result_view as rv
        importlib.reload(rv)
        assert callable(rv.render_result)


def test_review_panel_imports():
    """review_panel must import without error."""
    import unittest.mock as mock
    with mock.patch.dict("sys.modules", {"streamlit": mock.MagicMock()}):
        import importlib
        import streamlit_app.components.review_panel as rp
        importlib.reload(rp)
        assert callable(rp.render_review_panel)


# ---------------------------------------------------------------------------
# chat_handler: extract_patient_id
# ---------------------------------------------------------------------------

def test_extract_patient_id_basic():
    from streamlit_app.components.chat_handler import extract_patient_id
    assert extract_patient_id("Analisis pasien P001") == "P001"
    assert extract_patient_id("analisis PASIEN abc-123") == "abc-123"


def test_extract_patient_id_question_form():
    from streamlit_app.components.chat_handler import extract_patient_id
    assert extract_patient_id("Kenapa pasien P001 diprioritaskan?") == "P001"
    assert extract_patient_id("patient P007") == "P007"


def test_extract_patient_id_bare_id():
    from streamlit_app.components.chat_handler import extract_patient_id
    # Bare alphanumeric+dash that looks like an ID
    result = extract_patient_id("P001")
    assert result == "P001"


def test_extract_patient_id_not_found():
    from streamlit_app.components.chat_handler import extract_patient_id
    # Gibberish text with no extractable ID
    result = extract_patient_id("hello world this is a sentence with no patient id")
    assert result is None


def test_is_question_true():
    from streamlit_app.components.chat_handler import is_question
    assert is_question("Kenapa pasien P001 diprioritaskan?")
    assert is_question("apa potensi discrepancy?")
    assert is_question("bagaimana cara kerja sistem ini?")


def test_is_question_false():
    from streamlit_app.components.chat_handler import is_question
    assert not is_question("Analisis pasien P001")
    assert not is_question("P001")


# ---------------------------------------------------------------------------
# chat_handler: handle_chat error cases
# ---------------------------------------------------------------------------

def test_handle_chat_empty_input():
    from streamlit_app.components.chat_handler import handle_chat
    result = handle_chat("")
    assert result["error"] == "empty_input"
    assert "report" in result


def test_handle_chat_no_patient_id():
    from streamlit_app.components.chat_handler import handle_chat
    result = handle_chat("this text contains no patient id at all here")
    assert result["error"] == "no_patient_id"
    assert "report" in result


def test_handle_chat_extracts_patient_and_calls_backend(monkeypatch):
    """handle_chat should extract patient_id and call call_langflow."""
    from streamlit_app.components import chat_handler
    import unittest.mock as mock

    mock_response = {
        "patient_id": "P001",
        "review_priority": "HIGH",
        "discrepancy_likelihood": 0.8,
        "report": "Test report",
        "report_available": True,
        "_source": "fastapi_direct",
    }

    with mock.patch.object(chat_handler, "call_langflow", return_value=mock_response) as mock_lf:
        result = chat_handler.handle_chat("Analisis pasien P001")
        mock_lf.assert_called_once_with("P001", question=None)
        assert result["patient_id"] == "P001"


def test_handle_chat_question_mode(monkeypatch):
    """Question-type input should pass question kwarg to call_langflow."""
    from streamlit_app.components import chat_handler
    import unittest.mock as mock

    with mock.patch.object(chat_handler, "call_langflow", return_value={"report": "ok"}) as mock_lf:
        chat_handler.handle_chat("Kenapa pasien P001 diprioritaskan?")
        args, kwargs = mock_lf.call_args
        assert args[0] == "P001"
        assert kwargs.get("question") is not None


# ---------------------------------------------------------------------------
# langflow_client: _call_api_direct connection failure
# ---------------------------------------------------------------------------

def test_call_api_direct_connection_error():
    from streamlit_app.utils import langflow_client
    import unittest.mock as mock
    import requests

    with mock.patch("requests.post", side_effect=requests.exceptions.ConnectionError("refused")):
        result = langflow_client._call_api_direct("P001")
    assert result["error"] == "connection_failed"
    assert "report" in result


def test_call_api_direct_404():
    from streamlit_app.utils import langflow_client
    import unittest.mock as mock
    import requests

    mock_resp = mock.MagicMock()
    mock_resp.status_code = 404
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_resp)

    with mock.patch("requests.post", return_value=mock_resp):
        result = langflow_client._call_api_direct("P999")
    assert result["error"] == "patient_not_found"


# ---------------------------------------------------------------------------
# Safety terminology check
# ---------------------------------------------------------------------------

def test_no_clinical_risk_probability_in_app_source():
    """streamlit_app/app.py must not contain 'clinical risk probability'."""
    app_src = open("streamlit_app/app.py", encoding="utf-8").read()
    assert "clinical risk probability" not in app_src.lower()


def test_safety_notice_in_app_source():
    """streamlit_app/app.py must contain safety notice text."""
    app_src = open("streamlit_app/app.py", encoding="utf-8").read()
    assert "decision-support prototype" in app_src.lower() or "decision support" in app_src.lower()


def test_medication_review_priority_in_result_view():
    """result_view.py must use 'Medication Review Priority' terminology."""
    src = open("streamlit_app/components/result_view.py", encoding="utf-8").read()
    assert "Medication Review Priority" in src


def test_predicted_discrepancy_likelihood_in_result_view():
    """result_view.py must use 'Predicted Discrepancy Likelihood' terminology."""
    src = open("streamlit_app/components/result_view.py", encoding="utf-8").read()
    assert "Predicted Discrepancy Likelihood" in src
