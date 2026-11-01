"""
api/routes/v1/health.py
------------------------
GET /api/v1/health       — system liveness (versioned)
GET /api/v1/health/deps  — dependency health check (DB, ML model, LLM providers, Langflow flows)

A-303: Langflow flow hashes are reported here so the ops team can verify
       that the correct flow version is deployed.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends

from api.auth.rbac import TokenData, require_roles, UserRole

router = APIRouter(prefix="/health", tags=["system"])

_STARTUP_TIME = datetime.now(timezone.utc)
API_VERSION = "1.2.0"


# ---------------------------------------------------------------------------
# GET /api/v1/health  (no auth — liveness probe)
# ---------------------------------------------------------------------------

@router.get("", summary="Liveness probe (v1)")
async def health_v1() -> Dict[str, Any]:
    """Liveness probe — fast, no external calls."""
    model_version = "unknown"
    rule_version = "unknown"

    try:
        with open("models/metadata.json", encoding="utf-8") as fh:
            meta = json.load(fh)
        model_version = meta.get("model_version", "unknown")
    except Exception:
        pass

    try:
        with open("configs/discrepancy_rules.json", encoding="utf-8") as fh:
            cfg = json.load(fh)
        rule_version = cfg.get("rule_version", "unknown")
    except Exception:
        pass

    uptime = (datetime.now(timezone.utc) - _STARTUP_TIME).total_seconds()

    db_status = "unknown"
    try:
        from api.database import get_db
        with get_db() as conn:
            conn.execute("SELECT 1")
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {type(exc).__name__}"

    return {
        "status": "ok",
        "api_version": API_VERSION,
        "model_version": model_version,
        "rule_version": rule_version,
        "db_status": db_status,
        "uptime_seconds": uptime,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /api/v1/health/deps  (auth required — reveals internal config)
# ---------------------------------------------------------------------------

@router.get("/deps", summary="Dependency health + Langflow flow hashes (A-303)")
async def health_deps(
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.ADMIN, UserRole.AUDITOR)
    ),
) -> Dict[str, Any]:
    """
    Detailed dependency health check:
    - Database connectivity
    - ML model presence + version
    - LLM provider availability (from llm_chain_service)
    - Langflow flow file hashes (A-303)
    - Guardrail version
    """
    result: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db": _check_db(),
        "ml_model": _check_ml_model(),
        "llm_providers": _check_llm_providers(),
        "langflow_flows": _check_langflow_flows(),
        "guardrail": _check_guardrail(),
        "knowledge_base": _check_knowledge_base(),
    }

    # Overall status: ok if db + at least one LLM or template works
    db_ok = result["db"]["status"] == "ok"
    llm_any = True  # template fallback selalu tersedia
    result["overall"] = "ok" if db_ok else "degraded"
    result["all_ok"] = db_ok and llm_any

    return result


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

def _check_db() -> Dict[str, Any]:
    """Check SQLAlchemy DB connectivity."""
    try:
        from api.db.session import session_scope
        with session_scope() as session:
            from sqlalchemy import text
            session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}


def _check_ml_model() -> Dict[str, Any]:
    """Check ML model file presence."""
    try:
        with open("models/metadata.json", encoding="utf-8") as fh:
            meta = json.load(fh)
        model_path = Path("models") / meta.get("model_filename", "")
        exists = model_path.exists()
        return {
            "status": "ok" if exists else "missing",
            "version": meta.get("model_version", "unknown"),
            "filename": meta.get("model_filename", "unknown"),
            "features": meta.get("feature_count", "unknown"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}


def _check_llm_providers() -> Dict[str, Any]:
    """Check LLM provider chain from llm_chain_service."""
    try:
        from api.services.llm_chain_service import health_check
        return health_check()
    except Exception as exc:
        return {"error": str(exc)[:200], "template": {"available": True}}


def _check_langflow_flows() -> Dict[str, Any]:
    """
    Compute SHA-256 hashes of deployed Langflow flow JSON files (A-303).
    This lets ops verify that the exact correct flow version is deployed.
    """
    langflow_dir = Path("langflow")
    flows: Dict[str, Any] = {}

    if not langflow_dir.exists():
        return {"status": "directory_missing"}

    for flow_file in sorted(langflow_dir.glob("*.json")):
        try:
            raw = flow_file.read_bytes()
            sha256 = hashlib.sha256(raw).hexdigest()
            # Also parse to get flow metadata if available
            try:
                data = json.loads(raw)
                name = data.get("name", flow_file.stem)
                flow_id = data.get("id", "unknown")
            except Exception:
                name = flow_file.stem
                flow_id = "unknown"
            flows[flow_file.name] = {
                "name": name,
                "flow_id": flow_id,
                "sha256": sha256,
                "size_bytes": len(raw),
                "status": "ok",
            }
        except Exception as exc:
            flows[flow_file.name] = {"status": "error", "error": str(exc)[:100]}

    # Check experimental/ subfolder too
    experimental = langflow_dir / "experimental"
    if experimental.exists():
        flows["_experimental"] = {
            "note": "Flows in experimental/ are RESEARCH ONLY — not deployed",
            "files": [f.name for f in experimental.glob("*.json")],
        }

    return flows if flows else {"status": "no_flows_found"}


def _check_guardrail() -> Dict[str, Any]:
    """Report guardrail version and metrics."""
    try:
        from api.services.guardrail_service import GUARDRAIL_VERSION, get_metrics
        return {
            "version": GUARDRAIL_VERSION,
            "metrics": get_metrics(),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:200]}


def _check_knowledge_base() -> Dict[str, Any]:
    """Check knowledge base files."""
    checks = {}
    files = {
        "drug_alias": "knowledge/drug_alias.csv",
        "interactions": "knowledge/interactions.json",
        "allergy_rules": "configs/allergy_rules.json",
        "discrepancy_rules": "configs/discrepancy_rules.json",
    }
    for name, path in files.items():
        p = Path(path)
        if p.exists():
            checks[name] = {"status": "ok", "size_bytes": p.stat().st_size}
        else:
            checks[name] = {"status": "missing"}
    return checks
