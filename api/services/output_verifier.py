"""Defense-in-depth verification before a Langflow result may be persisted."""
from __future__ import annotations

from typing import Any

from priomedrec_core.contracts import AnalysisInput, AnalysisResult


class OutputVerificationError(ValueError):
    pass


def verify(result: dict[str, Any], request: AnalysisInput | dict[str, Any]) -> AnalysisResult:
    """Check schema, IDs, score bounds, version presence, and no new medicines.

    Deterministic facts are recomputed by the local fallback when this verifier
    rejects a remote response; callers must never persist an unverified result.
    """
    source = request if isinstance(request, AnalysisInput) else AnalysisInput.model_validate(request)
    parsed = AnalysisResult.model_validate(result)
    if parsed.patient_id != source.patient_id or parsed.encounter_id != source.encounter_id:
        raise OutputVerificationError("identitas hasil tidak cocok dengan request")
    score = parsed.phase_a.get("probability")
    if not isinstance(score, (int, float)) or not 0 <= score <= 1:
        raise OutputVerificationError("probabilitas di luar rentang 0..1")
    if not parsed.versions.get("model") or not parsed.versions.get("rules"):
        raise OutputVerificationError("versi model/rules wajib ada")
    inventory = {m.medication_name.lower().strip() for m in source.pre_admission_meds + source.admission_meds if m.medication_name}
    for finding in parsed.phase_b.get("findings", []):
        drug = str(finding.get("medication_name", finding.get("drug_name", ""))).lower().strip()
        if drug and inventory and drug not in inventory:
            raise OutputVerificationError("temuan menyebut obat di luar inventaris request")
    if any(f.get("severity_tier") == 1 or f.get("is_high_alert") for f in parsed.phase_b.get("findings", [])) and parsed.priority.get("final_tier") != "HIGH":
        raise OutputVerificationError("Tier-1/high-alert harus menghasilkan HIGH")
    return parsed
