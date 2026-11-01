"""Regenerate deterministic Langflow flow JSON skeletons."""
from __future__ import annotations

import json
import uuid
import hashlib
from pathlib import Path

FLOWS_DIR = Path("langflow/flows")
FLOWS_DIR.mkdir(parents=True, exist_ok=True)

FLOWS = [
    ("00_master_analysis", "Jalur utama analisis Langflow-first", "master"),
    ("01_triage", "Phase A + threshold mapper", "auxiliary"),
    ("02_clinical_reconciliation", "Phase B + safety flags + interaction/allergy", "auxiliary"),
    ("03_safety_review", "Normalizer + high-alert/NTI/Beers + DDI", "auxiliary"),
    ("04_priority_queuing", "Phase A+B -> priority composer", "auxiliary"),
    ("05_narrative_guardrail", "LLM SBAR + guardrail + fallback", "auxiliary"),
    ("06_review_hitl", "DRAFT_REVIEW; tidak pernah APPROVE otomatis", "auxiliary"),
]

entries = []
for name, desc, role in FLOWS:
    flow_id = str(uuid.uuid4())
    payload = {
        "name": name,
        "description": desc,
        "id": flow_id,
        "is_component": False,
        "last_tested_version": "1.13.0",
        "locked": False,
        "endpoint_name": None,
        "tags": ["priomedrec", "deterministic"],
        "data": {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    (FLOWS_DIR / f"{name}.json").write_text(text, encoding="utf-8")
    entries.append({
        "file": f"{name}.json",
        "name": name,
        "flow_id": flow_id,
        "role": role,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "imported_at": None,
    })

manifest = {"version": 1, "flows": entries}
(FLOWS_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print("Flows regenerated")
