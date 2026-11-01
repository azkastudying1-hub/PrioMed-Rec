"""Smoke test for the imported Langflow master flow."""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

PAYLOAD = {
    "patient_id": "SYNTHETIC-001",
    "encounter_id": "ENC-001",
    "features": {},
    "pre_admission_meds": [],
    "admission_meds": [],
}


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def main() -> None:
    base_url = (_env("LANGFLOW_BASE_URL") or _env("LANGFLOW_URL", "http://localhost:7860")).rstrip("/")
    flow_id = _env("LANGFLOW_MASTER_FLOW_ID")
    api_key = _env("LANGFLOW_API_KEY")
    if not flow_id:
        raise SystemExit("LANGFLOW_MASTER_FLOW_ID belum diisi")

    headers = {"x-api-key": api_key} if api_key else {}
    request = {"input_value": json.dumps(PAYLOAD), "output_type": "chat", "input_type": "chat"}
    with httpx.Client(timeout=60.0) as client:
        response = client.post(f"{base_url}/api/v1/run/{flow_id}", headers=headers, json=request)
        response.raise_for_status()
        body = response.json()

    print(json.dumps(body, indent=2, ensure_ascii=False)[:2000])
    assert isinstance(body, dict)
    print("SMOKE TEST OK")


if __name__ == "__main__":
    main()
