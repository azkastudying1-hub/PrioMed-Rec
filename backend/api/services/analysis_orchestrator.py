"""Langflow-first analysis with a mandatory deterministic local fallback."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any

from priomedrec_core.contracts import AnalysisInput, AnalysisResult
from priomedrec_core.pipeline import run_full

from .langflow_client import LangflowClient, LangflowUnavailable
from .output_verifier import OutputVerificationError, verify


async def run_analysis(payload: AnalysisInput | dict[str, Any], client: LangflowClient | None = None) -> dict[str, Any]:
    request = payload if isinstance(payload, AnalysisInput) else AnalysisInput.model_validate(payload)
    started = time.perf_counter()
    mode = os.getenv("EXECUTION_MODE", "langflow_first")
    if mode not in {"local_only", "langflow_only", "langflow_first"}:
        mode = "langflow_first"
    if mode != "local_only":
        try:
            raw = await (client or LangflowClient()).run_master(request.model_dump(mode="json"))
            result = verify(raw, request)
            return _decorate(result, "langflow", started, raw.get("execution", {}).get("trace_id"))
        except (LangflowUnavailable, OutputVerificationError, ValueError) as exc:
            if mode == "langflow_only":
                raise
            fallback_reason = type(exc).__name__
    else:
        fallback_reason = "local_only"
    return _decorate(run_full(request), "local_fallback", started, None, fallback_reason)


def _resolve_flow_hash() -> str:
    configured = os.getenv("LANGFLOW_MASTER_FLOW_HASH", "").strip()
    if configured:
        return configured
    manifest_path = Path("langflow/flows/manifest.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for flow in manifest.get("flows", []):
            if flow.get("role") == "master" or flow.get("name") == "00_master_analysis":
                if flow.get("sha256"):
                    return str(flow["sha256"])
    except (OSError, ValueError, TypeError):
        pass
    flow_path = Path("langflow/flows/00_master_analysis.json")
    try:
        return hashlib.sha256(flow_path.read_bytes()).hexdigest()
    except OSError:
        return "unknown"


def _decorate(result: AnalysisResult, path: str, started: float, trace_id: str | None, fallback_reason: str | None = None) -> dict[str, Any]:
    payload = result.model_dump(mode="json")
    payload["execution"] = {"path": path, "trace_id": trace_id, "flow_version_hash": _resolve_flow_hash(),
                            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                            "fallback_reason": fallback_reason}
    return payload
