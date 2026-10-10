"""
streamlit_app/utils/langflow_client.py
----------------------------------------
HTTP client for calling the Langflow orchestration API.

Streamlit → Langflow → FastAPI → ML + Rule Engine → LLM → response

When Langflow is unavailable, falls back to direct FastAPI /analyze call.
"""

from __future__ import annotations

import os
import requests
from typing import Optional

LANGFLOW_URL = os.getenv("LANGFLOW_URL", "http://localhost:7860")
API_URL      = os.getenv("PRIOMEDREC_API_URL", "http://localhost:8000")
TIMEOUT      = int(os.getenv("PRIOMEDREC_TIMEOUT", "60"))

# Langflow flow endpoint — set to your deployed flow's /api/v1/run/{flow_id}
FLOW_ID      = os.getenv("LANGFLOW_FLOW_ID", "priomedrec-orchestrator")


def call_langflow(patient_id: str, question: Optional[str] = None) -> dict:
    """
    Send a chat message to the Langflow orchestrator and return the response.

    Returns a dict that mirrors the /analyze response schema:
      { patient_id, encounter_id, discrepancy_likelihood, review_priority,
        top_features, flags, report, report_available, ... }

    Falls back to direct /analyze if Langflow is unavailable.
    """
    # Build the input message
    message = question if question else f"Analisis pasien {patient_id}"

    # Try Langflow first
    try:
        url = f"{LANGFLOW_URL}/api/v1/run/{FLOW_ID}"
        payload = {
            "input_value": message,
            "input_type": "chat",
            "output_type": "chat",
            "tweaks": {
                "patient_id": patient_id,
            },
        }
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        lf_data = resp.json()
        # Extract the structured output from Langflow response
        # Langflow wraps output in outputs[0].outputs[0].results.message.data.text
        text = _extract_langflow_output(lf_data)
        if text:
            return {"report": text, "report_available": True, "_source": "langflow",
                    "patient_id": patient_id, "encounter_id": ""}
    except Exception:
        pass  # fall through to direct API

    # Fallback: call FastAPI /analyze directly
    return _call_api_direct(patient_id, question)


def _extract_langflow_output(lf_data: dict) -> str:
    """Extract text output from Langflow response envelope."""
    try:
        # v1 Langflow output path
        return (
            lf_data["outputs"][0]["outputs"][0]["results"]["message"]["data"]["text"]
        )
    except (KeyError, IndexError, TypeError):
        pass
    try:
        # Alternate path
        return lf_data["outputs"][0]["outputs"][0]["artifacts"]["message"]
    except (KeyError, IndexError, TypeError):
        pass
    return ""


def _call_api_direct(patient_id: str, question: Optional[str] = None) -> dict:
    """
    Direct fallback: call POST /analyze on FastAPI with patient_id-driven mode.
    Used when Langflow is not running.
    """
    payload: dict = {"patient_id": patient_id}
    if question:
        payload["question"] = question

    try:
        resp = requests.post(f"{API_URL}/analyze", json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        data["_source"] = "fastapi_direct"
        return data
    except requests.exceptions.ConnectionError:
        return {
            "error":   "connection_failed",
            "message": f"Cannot connect to FastAPI at {API_URL}. Is the server running?",
            "report":  (
                "❌ **Server tidak tersedia.** Pastikan FastAPI sudah berjalan:\n"
                "```\nuvicorn api.main:app --host 0.0.0.0 --port 8000 --reload\n```"
            ),
            "report_available": False,
            "patient_id": patient_id,
            "encounter_id": "",
        }
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "?"
        if status == 404:
            return {
                "error":   "patient_not_found",
                "message": f"Patient '{patient_id}' not found in dataset.",
                "report":  f"❌ **Pasien `{patient_id}` tidak ditemukan** dalam dataset.",
                "report_available": False,
                "patient_id": patient_id,
                "encounter_id": "",
            }
        return {
            "error":   "api_error",
            "message": str(e),
            "report":  f"❌ **API error {status}:** {e}",
            "report_available": False,
            "patient_id": patient_id,
            "encounter_id": "",
        }
    except Exception as e:
        return {
            "error":   "unknown",
            "message": str(e),
            "report":  f"❌ **Error:** {e}",
            "report_available": False,
            "patient_id": patient_id,
            "encounter_id": "",
        }


def check_api_health() -> tuple[bool, str]:
    """Check if FastAPI is reachable. Returns (is_healthy, message)."""
    try:
        resp = requests.get(f"{API_URL}/health", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return True, f"API OK — model={data.get('model_version','?')} rules={data.get('rule_version','?')}"
    except Exception as e:
        return False, f"API tidak tersedia ({API_URL}): {e}"
