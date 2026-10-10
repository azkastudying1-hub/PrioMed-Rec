# API Contract — PrioMed-Rec

**Version:** 1.1.0
**Base URL:** `http://localhost:8000`
**OpenAPI docs:** `http://localhost:8000/docs`

> ⚠️ **Decision support only.** All API responses are intended to assist pharmacist review — not to replace clinical judgment. Every discrepancy flag carries `verification_required: true`.
>
> **Terminology:** Use `predicted_discrepancy_likelihood` (not `risk_probability`) and `medication_review_priority` (not `priority` or `clinical risk`).

---

## Authentication

Currently no authentication (MVP prototype). Add API key auth before any production deployment.

---

## Changelog

| Version | Change |
|---|---|
| 1.1.0 | Added `GET /patient/{patient_id}`, `GET /patients/sample`. Added `POST /analyze` (patient_id-driven, no feature vector). `POST /review` response now includes `model_version` + `rule_version`. Revised terminology: `predicted_discrepancy_likelihood`. |
| 1.0.0 | Initial contract: `POST /prioritize`, `POST /discrepancies`, `POST /review`, `GET /health`. |

---

## Endpoints

### `GET /health`

Liveness check and version identifiers.

**Response 200:**
```json
{
  "status": "ok",
  "model_version": "model-0.3.0",
  "rule_version": "rules-0.1.0",
  "api_version": "1.1.0"
}
```

---

### `GET /patient/{patient_id}`

Retrieve patient context, encounter metadata, pre-admission and admission medication lists for a given patient ID. Used by Langflow and Streamlit to resolve a patient from a chat query.

**Path parameter:** `patient_id` — Synthea patient UUID

**Response 200:**
```json
{
  "patient_id": "0002f562-87d8-d5f3-0021-3ec2970fe161",
  "encounter_id": "enc-uuid-...",
  "encounter_start": "2020-03-15T08:30:00",
  "encounter_class": "IMP",
  "age": 72.5,
  "gender": "F",
  "active_condition_count": 4,
  "prior_encounter_count": 12,
  "pre_admission_meds": [
    { "medication_code": "316049", "medication_name": "warfarin 5 MG" }
  ],
  "admission_meds": [
    { "medication_code": "197591", "medication_name": "amlodipine 5 MG" }
  ],
  "feature_vector": {
    "age": 72.5,
    "age_65_plus": 1,
    "gender_encoded": 0,
    "pre_admission_medication_count": 6,
    "admission_medication_count": 7,
    "total_medication_count": 9,
    "new_medication_count": 3,
    "discontinued_medication_count": 2,
    "polypharmacy_flag": 1,
    "high_alert_flag": 1,
    "high_alert_count": 2,
    "potential_duplicate_candidates": 1,
    "active_condition_count": 4,
    "prior_encounter_count": 12,
    "allergy_count": 0,
    "has_drug_allergy": 0
  }
}
```

**Error responses:**

| Code | Condition |
|---|---|
| 404 | Patient not found in dataset |
| 503 | Data loading failure |

---

### `GET /patients/sample`

Return a list of sample patient IDs available in the dataset. Useful for demo/testing.

**Query parameter:** `n` (optional, default=5, max=50)

**Response 200:**
```json
{
  "patient_ids": [
    "0002f562-87d8-d5f3-0021-3ec2970fe161",
    "..."
  ],
  "count": 5
}
```

---

### `POST /analyze`

**Primary orchestration endpoint.** Accepts a patient identifier and returns a complete pharmacist-facing analysis: prioritization + discrepancy detection + SHAP explanation. Feature construction is entirely internal — callers never construct feature vectors.

**Request body (simple mode — recommended):**
```json
{
  "patient_id": "0002f562-87d8-d5f3-0021-3ec2970fe161"
}
```

**Request body (expert mode — for integration testing):**
```json
{
  "patient_id": "0002f562-87d8-d5f3-0021-3ec2970fe161",
  "encounter_id": "enc-uuid-...",
  "features": { ... },
  "pre_admission_meds": [ ... ],
  "admission_meds": [ ... ]
}
```

> `features`, `pre_admission_meds`, `admission_meds` are optional. When omitted, the API constructs them internally from `patient_id`.

**Response 200:**
```json
{
  "patient_id": "0002f562-87d8-d5f3-0021-3ec2970fe161",
  "encounter_id": "enc-uuid-...",
  "medication_review_priority": "HIGH",
  "predicted_discrepancy_likelihood": 0.7123,
  "model_version": "model-0.3.0",
  "threshold_version": "thresholds-0.1.0",
  "top_features": [
    {
      "feature": "total_medication_count",
      "value": 9.0,
      "shap_value": 0.12,
      "direction": "increases_likelihood"
    },
    {
      "feature": "high_alert_flag",
      "value": 1.0,
      "shap_value": 0.09,
      "direction": "increases_likelihood"
    }
  ],
  "discrepancy_flags": [
    {
      "flag_type": "POTENTIAL_OMISSION",
      "severity": "REVIEW",
      "medication_code": "316049",
      "medication_name": "warfarin 5 MG",
      "evidence": "Medication present in pre-admission list but absent from admission list",
      "verification_required": true,
      "rule_id": "omission.v0.1.0"
    }
  ],
  "rule_version": "rules-0.1.0",
  "safety_notice": "PrioMed-Rec is a decision-support prototype. Every potential discrepancy requires pharmacist verification. This output does not replace pharmacist judgment."
}
```

**Error responses:**

| Code | Condition |
|---|---|
| 404 | Patient not found |
| 422 | Invalid expert-mode feature values |
| 503 | Model or rule engine failure |

---

### `POST /prioritize`

Predict medication discrepancy likelihood for a single admission encounter using an explicit feature vector. For direct integration or testing purposes. **Users should prefer `POST /analyze` with `patient_id` only.**

**Request body:**
```json
{
  "age": 72.5,
  "age_65_plus": 1,
  "gender_encoded": 0,
  "pre_admission_medication_count": 6,
  "admission_medication_count": 7,
  "total_medication_count": 9,
  "new_medication_count": 3,
  "discontinued_medication_count": 2,
  "polypharmacy_flag": 1,
  "high_alert_flag": 1,
  "high_alert_count": 2,
  "potential_duplicate_candidates": 1,
  "active_condition_count": 5,
  "prior_encounter_count": 14,
  "allergy_count": 0,
  "has_drug_allergy": 0
}
```

**Validation rules:**
- `age` must be `>= 0`
- All count fields must be `>= 0`
- All flag fields must be `0` or `1`

**Response 200:**
```json
{
  "predicted_discrepancy_likelihood": 0.7123,
  "medication_review_priority": "HIGH",
  "model_version": "model-0.3.0",
  "threshold_version": "thresholds-0.1.0",
  "top_features": [
    {
      "feature": "total_medication_count",
      "value": 9.0,
      "shap_value": 0.12,
      "direction": "increases_likelihood"
    },
    {
      "feature": "high_alert_flag",
      "value": 1.0,
      "shap_value": 0.09,
      "direction": "increases_likelihood"
    }
  ]
}
```

**Error responses:**

| Code | Condition |
|---|---|
| 422 | Invalid input (age < 0, count < 0, missing required field) |
| 503 | Model artifact missing or inference failure |

---

### `POST /discrepancies`

Run the medication discrepancy rule engine for one encounter.

**Request body:**
```json
{
  "patient_id": "PAT-001",
  "encounter_id": "ENC-001",
  "pre_admission_meds": [
    { "medication_code": "316049", "medication_name": "warfarin 5 MG", "dose_value": 5.0 }
  ],
  "admission_meds": [
    { "medication_code": "197591", "medication_name": "amlodipine 5 MG" }
  ]
}
```

**Response 200:**
```json
{
  "patient_id": "PAT-001",
  "encounter_id": "ENC-001",
  "rule_version": "rules-0.1.0",
  "flags": [
    {
      "flag_type": "POTENTIAL_OMISSION",
      "severity": "REVIEW",
      "medication_code": "316049",
      "medication_name": "warfarin 5 MG",
      "evidence": "Medication present in pre-admission list but absent from admission list",
      "verification_required": true,
      "rule_id": "omission.v0.1.0"
    }
  ]
}
```

**Invariant:** `verification_required` is always `true` for every flag — pharmacist must review.

**Error responses:**

| Code | Condition |
|---|---|
| 503 | Rule config missing or engine failure |

---

### `POST /review`

Capture pharmacist review action for an AI-generated result. Mandatory human-in-the-loop step.

**Request body:**
```json
{
  "case_id": "CASE-001",
  "pharmacist_id": "PHARM-01",
  "ai_result": {
    "predicted_discrepancy_likelihood": 0.75,
    "medication_review_priority": "HIGH"
  },
  "action": "APPROVE",
  "pharmacist_note": "Reviewed — warfarin omission confirmed.",
  "edited_result": null,
  "model_version": "model-0.3.0"
}
```

**Action values:** `APPROVE` | `REJECT` | `EDIT`

- `APPROVE` → `final_result` = `ai_result` + `pharmacist_action: "APPROVED"`
- `REJECT`  → `final_result` = `ai_result` + `pharmacist_action: "REJECTED"` + note
- `EDIT`    → `final_result` = `edited_result` (must be provided) + `pharmacist_action: "EDITED"`

**Response 200:**
```json
{
  "review_id": "a1b2c3d4-...",
  "case_id": "CASE-001",
  "action": "APPROVE",
  "timestamp": "2025-01-01T12:00:00+00:00",
  "pharmacist_id": "PHARM-01",
  "model_version": "model-0.3.0",
  "rule_version": "rules-0.1.0",
  "final_result": {
    "predicted_discrepancy_likelihood": 0.75,
    "medication_review_priority": "HIGH",
    "pharmacist_action": "APPROVED",
    "pharmacist_note": "Reviewed — warfarin omission confirmed."
  }
}
```

**Audit record fields:**

| Field | Description |
|---|---|
| `review_id` | UUID — unique audit trail identifier |
| `case_id` | Patient/encounter identifier |
| `action` | APPROVE / REJECT / EDIT |
| `timestamp` | ISO 8601 UTC |
| `pharmacist_id` | Reviewer identifier |
| `model_version` | Model version that produced the AI result |
| `rule_version` | Rule engine version that produced the flags |
| `final_result` | The result after pharmacist action |

**Error responses:**

| Code | Condition |
|---|---|
| 422 | Invalid action value, EDIT without edited_result |

---

## Priority Thresholds

| Priority | Condition |
|---|---|
| HIGH   | `predicted_discrepancy_likelihood >= 0.70` |
| MEDIUM | `predicted_discrepancy_likelihood >= 0.40` |
| LOW    | `predicted_discrepancy_likelihood < 0.40` |

Thresholds are stored in `models/thresholds.json`. **Must not be modified by LLM or any automated system.**

---

## Clinical Safety Constraints

| Constraint | Enforcement |
|---|---|
| No autonomous clinical instruction in responses | Validated in output schema + LLM output_validator.py |
| `verification_required: true` on all flags | Hardcoded in discrepancy service |
| Model failure → 503, not fabricated prediction | Exception handler in routes |
| Rule engine failure → 503, not silent "no flags" | Exception handler in discrepancy route |
| `medication_review_priority` only LOW/MEDIUM/HIGH | Pydantic enum |
| `model_version` and `rule_version` always present | Required fields in response schemas |
| LLM cannot change `predicted_discrepancy_likelihood` | Guardrail check in output_validator.py |
| LLM cannot change `medication_review_priority` | Guardrail check in output_validator.py |

---

## LLM Constraints

The LLM (Gemini via `src/llm/service.py`) is permitted to:
- Explain and summarize the structured API response
- Answer grounded pharmacist questions about the result
- Translate structured output to natural language

The LLM is **explicitly prohibited** from:
- Changing `predicted_discrepancy_likelihood`
- Changing `medication_review_priority`
- Adding or removing discrepancy flags
- Adding or removing medications
- Making autonomous treatment recommendations

Enforcement: `src/llm/validators/output_validator.py` — 6 guardrail checks applied to every LLM response.
