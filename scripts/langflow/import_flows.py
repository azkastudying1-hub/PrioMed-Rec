"""Import PrioMed-Rec Langflow flows and write langflow/flows/manifest.json."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

FLOWS_DIR = Path("langflow/flows")
MANIFEST = FLOWS_DIR / "manifest.json"


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _login(client: httpx.Client, base_url: str) -> str:
    username = _env("LANGFLOW_SUPERUSER", "langflow-admin")
    password = _env("LANGFLOW_SUPERUSER_PASSWORD")
    if not password:
        raise RuntimeError("LANGFLOW_SUPERUSER_PASSWORD belum diisi")
    response = client.post(
        f"{base_url}/api/v1/login",
        data={"username": username, "password": password},
    )
    response.raise_for_status()
    body = response.json()
    token = body.get("access_token") or body.get("token")
    if not token:
        raise RuntimeError("Login Langflow tidak mengembalikan token")
    return str(token)


def main() -> None:
    base_url = (_env("LANGFLOW_BASE_URL") or _env("LANGFLOW_URL", "http://localhost:7860")).rstrip("/")
    api_key = _env("LANGFLOW_API_KEY")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"flows": []}
    entries = manifest.setdefault("flows", [])

    with httpx.Client(timeout=60.0) as client:
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key
        else:
            token = _login(client, base_url)
            headers["Authorization"] = f"Bearer {token}"

        for entry in entries:
            flow_file = FLOWS_DIR / entry["file"]
            if not flow_file.exists():
                print(f"SKIP {flow_file} (tidak ada)")
                continue
            payload = json.loads(flow_file.read_text(encoding="utf-8"))
            response = client.post(f"{base_url}/api/v1/flows/", headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
            imported_id = body.get("id") or body.get("flow_id") or entry.get("flow_id")
            entry["flow_id"] = imported_id
            entry["imported_at"] = datetime.now(timezone.utc).isoformat()
            print(f"IMPORTED {entry['name']} -> {imported_id}")

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    master = next((f for f in entries if f.get("role") == "master"), None)
    if master:
        print(f"LANGFLOW_MASTER_FLOW_ID={master.get('flow_id')}")
        print(f"LANGFLOW_MASTER_FLOW_HASH={master.get('sha256')}")


if __name__ == "__main__":
    main()
