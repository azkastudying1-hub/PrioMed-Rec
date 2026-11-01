"""
api/services/llm_service.py
-----------------------------
Thin wrapper around src.llm.service that forces a fresh import on every
call using importlib.import_module + exec-based isolation.

This is necessary because uvicorn caches Python modules at startup and
--reload only reloads modules whose source files change. By spawning the
call in a subprocess we guarantee the latest .env and latest src/llm/service.py
are always used without depending on module cache invalidation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


_SCRIPT = """\
import sys, os, json
sys.path.insert(0, {root!r})

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path({root!r}) / ".env", override=True)

import src.llm.service as svc

context = json.loads(sys.stdin.read())
question = context.pop("__question__", None)

try:
    if question:
        result = svc.generate_summary.__module__ and svc.answer_query(question, context)
    else:
        result = svc.generate_summary(context)
    out = {{"ok": True, "text": result}}
except Exception as exc:
    out = {{"ok": False, "error": f"{{type(exc).__name__}}: {{exc}}"}}

print(json.dumps(out))
"""


def call_llm_fresh(context: dict, question: str | None = None) -> tuple[bool, str]:
    """
    Call the LLM in a fresh subprocess so module cache issues never interfere.

    Returns
    -------
    (success: bool, text: str)
      success=True  → text is the LLM report
      success=False → text is the error message
    """
    root = str(Path(__file__).resolve().parent.parent.parent)
    script = _SCRIPT.format(root=root)

    try:
        from src.llm.anonymizer import anonymize_context, should_call_llm
        if not should_call_llm():
            return False, "LLM_DATA_MODE is blocked. Structured fallback report provided."
        context_to_send = anonymize_context(context)
    except Exception as anon_exc:
        print(f"[llm_service] Anonymization warning: {anon_exc}")
        context_to_send = context

    payload = dict(context_to_send)
    if question:
        payload["__question__"] = question

    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            return False, f"LLM subprocess error: {stderr[-500:] if stderr else 'unknown'}"

        stdout = result.stdout.strip()
        if not stdout:
            return False, "LLM subprocess returned empty output."

        out = json.loads(stdout)
        if out.get("ok"):
            return True, out["text"]
        return False, out.get("error", "Unknown LLM error")

    except subprocess.TimeoutExpired:
        return False, "LLM call timed out after 90 seconds."
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
