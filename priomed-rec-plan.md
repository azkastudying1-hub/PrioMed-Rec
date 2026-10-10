# PrioMed-Rec: Revised Implementation Plan (v2)

> **Revised against:** Specification v2 (2025) — enforces Streamlit-first UX, grounded terminology, Langflow-as-orchestration, reproducible synthetic labels, multi-metric ML evaluation, and pharmacist-centric output.  
> **Principle:** Prioritize → Flag → Explain → Support → Pharmacist Decides  
> **Architecture:** Streamlit → Langflow → FastAPI → ML + Rule Engine → LLM → Pharmacist

---

## Ringkasan Eksekutif

| Property | Value |
|---|---|
| **System name** | PrioMed-Rec |
| **Correct positioning** | AI-assisted admission medication-reconciliation **prioritization** for clinical pharmacists |
| **Primary user** | Clinical pharmacist |
| **UI** | Streamlit — one chat input, pharmacist-friendly result |
| **Orchestration** | Langflow (2 flows) |
| **Backend** | FastAPI |
| **ML** | Admission medication review prioritization (binary classifier with ranked output) |
| **Rule engine** | Deterministic discrepancy detector |
| **LLM** | Gemini — explain / summarize / Q&A only |
| **SHAP** | Per-prediction explainability |
| **Human-in-the-loop** | APPROVE / REJECT / EDIT with audit trail — mandatory |
| **Data** | Synthea synthetic EHR (already processed) |
| **Scale** | 17,286 patients · 488,422 encounters · 885,606 medication requests |

---

## SECTION 1 — AUDIT FINDINGS: Current vs Revised Spec

### ✅ Already Correct

| Area | Current State |
|---|---|
| Two analytic functions (A + B) | Separated: `/prioritize` vs `/discrepancies` |
| Patient-level split | Implemented in `src/models/train.py` |
| 4-model benchmark | Rule Baseline + LR + RF + XGBoost |
| Config-driven rule engine | `configs/discrepancy_rules.json` |
| SHAP explainability | `src/explainability/shap_explainer.py` |
| Gemini LLM (explain only) | `src/llm/service.py` |
| LLM output guardrails | 6 checks in `src/llm/validators/output_validator.py` |
| Audit trail | `POST /review` captures APPROVE/REJECT/EDIT |
| Safety notice in README/MODEL_CARD | Present |
| High-alert medications config | `configs/high_alert_medications.json` |
| `POST /analyze` (orchestration endpoint) | Implemented in `api/routes/analyze.py` |
| `streamlit_app/` directory intention | `ui/app.py` exists |
| DOSE_DISCREPANCY requires valid dose_value | Implemented in `synthetic_case_generator.py` |
| FREQUENCY/ROUTE disabled when fields 100% null | Implemented and documented |

### ⚠️ Conflicts That MUST Be Resolved

| # | Conflict | Severity | Spec Reference |
|---|---|---|---|
| C-01 | **Streamlit UI (`ui/app.py`) requires user to manually enter 16 ML features in sidebar** — directly contradicts spec: "user must NOT manually enter the 16 ML features." | CRITICAL | §1 |
| C-02 | **`streamlit_app/` directory does not exist** — spec requires `streamlit_app/` in repo structure, file lives at `ui/app.py` | HIGH | §18 |
| C-03 | **Langflow is optional ("Opsional") in README** — spec requires Langflow as mandatory orchestration layer between Streamlit and FastAPI | HIGH | §2 |
| C-04 | **`has_discrepancy` label is random proxy (confirmed ROC-AUC ~0.50)** — spec explicitly says this is NOT acceptable as final ML training target. Must be replaced with reproducible synthetic MedRec labels derived from Synthea longitudinal medication data. | CRITICAL | §6 |
| C-05 | **`select_best_model()` in `evaluate.py` uses ROC-AUC alone** — spec requires multi-metric selection; ROC-AUC alone is prohibited | HIGH | §9 |
| C-06 | **README and MODEL_CARD use `risk_probability` / "AI-Powered Admission Risk Prioritization"** — spec mandates "Predicted discrepancy likelihood" and "Medication Review Priority" terminology | MEDIUM | §17 |
| C-07 | **Streamlit Q&A tab still manually constructs full feature vector** — same as C-01 | CRITICAL | §1 |
| C-08 | **`POST /prioritize` endpoint requires caller to supply 16 features directly** — spec: "Never expose model internals or require users to manually construct feature vectors" | HIGH | §15 |
| C-09 | **No `GET /patient/{patient_id}` endpoint** — spec requires patient data retrieval endpoint | MEDIUM | §15 |
| C-10 | **`streamlit_app/` module missing** — spec defines `streamlit_app/` as a top-level directory in the repo | MEDIUM | §18 |
| C-11 | **No `provenance` column in `synthetic_cases.csv` schema** — spec requires provenance in every synthetic case record | LOW | §6 |
| C-12 | **`allergy_count`, `has_drug_allergy` still in `/analyze` and Streamlit** — DQI-001 confirmed these are always 0; they inflate feature count and mislead users. Should be documented and either excluded from active features or clearly flagged as always-null | MEDIUM | §10 |
| C-13 | **`ui/app.py` Streamlit tab shows raw feature inputs instead of patient-ID-driven chat** — violates the one-chat-input UX requirement | CRITICAL | §1, §14 |
| C-14 | **Langflow `priomedrec_orchestrator.json` does not contain patient-resolution and auto feature-construction steps** — needs patient lookup → feature generation nodes | HIGH | §2, §3 |
| C-15 | **`run_training.py` selects model by ROC-AUC only; no multi-metric report printed** | MEDIUM | §8, §9 |
| C-16 | **`docs/MODEL_CARD.md` labels section still says random proxy is the final accepted label** — must be updated after label replacement | HIGH | §10 |
| C-17 | **No `test_streamlit.py`, `test_langflow_integration.py`** — spec adds these test requirements | MEDIUM | §19 |
| C-18 | **No `POST /analyze` accepting simple patient/case identifier** — current `/analyze` still requires 16 features + medication lists from caller | HIGH | §15 |

### 📋 Gaps — New Requirements Not Yet Implemented

| # | Gap | Spec Reference |
|---|---|---|
| G-01 | **`streamlit_app/` module** with one-chat-input interface: "Analisis pasien P001" → auto-resolve → full result | §1, §14 |
| G-02 | **Patient data resolver** — given `patient_id`, retrieve structured admission data and auto-construct ML features | §1, §15 |
| G-03 | **Synthetic label replacement** — deterministic MedRec case generator based on actual Synthea longitudinal med data (not random `np.random.choice`) | §6 |
| G-04 | **`GET /patient/{patient_id}` endpoint** — returns structured patient/encounter context | §15 |
| G-05 | **`POST /analyze` clean interface** — accepts `patient_id` + optional `encounter_id` + optional `question`; internal feature construction | §15 |
| G-06 | **Multi-metric model selection** — final model selection must consider Precision, Recall, F1, PR-AUC, calibration, Top-K recall | §8, §9 |
| G-07 | **Operational/hackathon metric** — simulate limited pharmacist capacity (top-10%, top-20% recall); this metric must be in eval report | §9 |
| G-08 | **Streamlit result view** — Patient Summary, Admission Summary, Medication Review Priority, Predicted Discrepancy Likelihood, Top Contributing Factors, Potential Medication Discrepancies, Model/Rule Explanation, Safety Notice, APPROVE/EDIT/REJECT | §14 |
| G-09 | **Langflow `priomedrec_orchestrator.json` updated** — chat → patient resolution → backend inference → structured result → grounded LLM | §3 |
| G-10 | **`test_streamlit.py`** and **`test_langflow_integration.py`** | §19 |
| G-11 | **`streamlit_app/` directory** with proper module structure | §18 |
| G-12 | **Correct terminology throughout** — "Medication Review Priority", "Predicted discrepancy likelihood" everywhere | §17 |
| G-13 | **Decision-support prototype disclaimer** visible in Streamlit UI | §17 |
| G-14 | **Audit record** must include `model_version` and `rule_version` alongside pharmacist action | §16 |

---

## SECTION 2 — CONFIRMED DESIGN DECISIONS (Unchanged)

| Aspect | Decision |
|---|---|
| Input data | CSV from `data/raw/synthea/` |
| `primedrec_master.csv` | Used as base admission dataset |
| `primedrec_risk_features.csv` | Starting point for feature matrix |
| ML modeling | Comparative: Rule baseline + LR + RF + XGBoost; ensemble only if justified |
| LLM role | Explain + Summarize + Q&A ONLY — cannot change score/label/medication |
| Rule engine | JSON configuration-driven, never hardcode in Python |
| Langflow flows | Exactly 2: `priomedrec_orchestrator.json` + `priomedrec_review.json` |
| IBM Bob | Development/coding agent — NOT runtime clinical decision-maker |
| No Hugging Face fine-tuning | Unless concrete task + evidence required |
| SHAP | Keeps explaining predictions, never modifies them |
| Human-in-the-loop | Mandatory: APPROVE/REJECT/EDIT with full audit trail |

---

## SECTION 3 — REVISED ARCHITECTURE

```
┌────────────────────────────────────────────────────────────────┐
│              PHARMACIST INTERFACE                               │
│              streamlit_app/app.py                               │
│  ONE CHAT INPUT: "Analisis pasien P001"                        │
│  Result: Patient Summary · Medication Review Priority          │
│          Predicted Discrepancy Likelihood · SHAP Factors       │
│          Potential Discrepancies · Pharmacist Actions          │
└───────────────────────┬────────────────────────────────────────┘
                        │ (Langflow API call)
                        ▼
┌────────────────────────────────────────────────────────────────┐
│              LANGFLOW ORCHESTRATION                             │
│  langflow/priomedrec_orchestrator.json                         │
│  Chat → Patient Resolution → Backend Inference                 │
│       → Structured Result → LLM Explanation → Response        │
└──────────┬─────────────────────────────┬───────────────────────┘
           │                             │
           ▼                             ▼
┌──────────────────────┐    ┌────────────────────────────┐
│  FASTAPI BACKEND     │    │  LLM SERVICE               │
│  GET  /health        │    │  src/llm/service.py        │
│  GET  /patient/{id}  │    │  generate_summary()        │
│  POST /prioritize    │    │  explain_risk()            │
│  POST /discrepancies │    │  explain_discrepancy()     │
│  POST /review        │    │  answer_query()            │
│  POST /analyze       │    │  + 6 guardrail checks      │
└──────────┬───────────┘    └────────────────────────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
┌─────────┐  ┌──────────┐
│ ML MODEL│  │RULE ENG. │
│ LAYER   │  │ LAYER    │
│+ SHAP   │  │ (config) │
└─────────┘  └──────────┘
```

**Runtime call chain:**
```
Streamlit → Langflow → FastAPI → ML + Rule Engine → Structured Result → LLM → Langflow → Streamlit
```

---

## SECTION 4 — REVISED REPO STRUCTURE

```
priomed-rec/
│
├── configs/
│   ├── discrepancy_rules.json        ✓ exists
│   ├── high_alert_medications.json   ✓ exists
│   ├── feature_config.json           ✓ exists
│   └── model_thresholds.json         ✓ exists
│
├── data/
│   ├── raw/synthea/                  ✓ exists
│   ├── interim/                      ✓ exists
│   └── processed/                    ✓ exists
│
├── src/
│   ├── data/                         ✓ exists
│   │   ├── loaders.py
│   │   ├── validator.py
│   │   ├── admission_cohort.py
│   │   ├── medication_timeline.py
│   │   └── patient_resolver.py       ← NEW: given patient_id → structured context
│   │
│   ├── features/                     ✓ exists
│   │   ├── medication_features.py
│   │   ├── clinical_features.py
│   │   └── feature_pipeline.py
│   │
│   ├── labels/                       ✓ exists (needs replacement)
│   │   └── synthetic_case_generator.py  ← REVISED: replace random proxy
│   │
│   ├── models/                       ✓ exists (needs multi-metric selection)
│   │   ├── train.py
│   │   ├── evaluate.py               ← REVISED: multi-metric selection
│   │   └── predict.py
│   │
│   ├── rules/                        ✓ exists
│   │   ├── medication_normalizer.py
│   │   ├── discrepancy_engine.py
│   │   └── rule_evaluator.py
│   │
│   ├── explainability/               ✓ exists
│   │   └── shap_explainer.py
│   │
│   └── llm/                          ✓ exists
│       ├── service.py
│       ├── prompts/
│       ├── schemas/
│       └── validators/
│
├── api/
│   ├── main.py                       ✓ exists
│   ├── routes/
│   │   ├── health.py                 ✓ exists
│   │   ├── prioritization.py         ✓ exists
│   │   ├── discrepancy.py            ✓ exists
│   │   ├── review.py                 ✓ exists
│   │   ├── analyze.py                ✓ exists (REVISED: patient_id-driven)
│   │   └── patient.py                ← NEW: GET /patient/{patient_id}
│   └── services/
│       ├── prioritization_service.py ✓ exists
│       ├── discrepancy_service.py    ✓ exists
│       └── patient_service.py        ← NEW: patient data retrieval + feature construction
│
├── streamlit_app/                    ← NEW directory (replaces ui/)
│   ├── __init__.py
│   ├── app.py                        ← NEW: one-chat-input Streamlit UI
│   ├── components/
│   │   ├── result_view.py            ← NEW: pharmacist-friendly result renderer
│   │   ├── review_panel.py           ← NEW: APPROVE/REJECT/EDIT panel
│   │   └── chat_handler.py           ← NEW: chat input → Langflow → response
│   └── utils/
│       └── langflow_client.py        ← NEW: Langflow API client
│
├── models/                           ✓ exists
├── langflow/
│   ├── priomedrec_orchestrator.json  ← REVISED: add patient-resolution node
│   └── priomedrec_review.json        ✓ exists
│
├── bob/                              ✓ exists
│
├── notebooks/                        ✓ exists
│
├── tests/
│   ├── test_data.py                  ✓ exists
│   ├── test_features.py              ✓ exists
│   ├── test_labels.py                ✓ exists (needs new synthetic label tests)
│   ├── test_rules.py                 ✓ exists
│   ├── test_model.py                 ✓ exists (needs multi-metric tests)
│   ├── test_api.py                   ✓ exists (needs patient endpoint tests)
│   ├── test_llm.py                   ✓ exists
│   ├── test_guardrails.py            ✓ exists
│   ├── test_e2e.py                   ✓ exists
│   ├── test_streamlit.py             ← NEW
│   └── test_langflow_integration.py  ← NEW
│
└── docs/
    ├── architecture.md               ← REVISED: Streamlit-first diagram
    ├── data_dictionary.md            ✓ exists
    ├── feature_dictionary.md         ✓ exists
    ├── label_definition.md           ← REVISED: document label replacement
    ├── evaluation_protocol.md        ← REVISED: multi-metric, Top-K
    ├── API_contract.md               ← REVISED: add /patient/{id}, revised /analyze
    ├── RULEBOOK.md                   ✓ exists
    ├── MODEL_CARD.md                 ← REVISED: updated terminology + new labels
    ├── DECISION_LOG.md               ← REVISED: record label replacement decision
    └── data_provenance.md            ✓ exists
```

---

## SECTION 5 — REVISED SUB-TASKS

### Sub-Task 1 — Project Setup & Configuration
**Status:** `[x] done`  
No changes required. All configs and directory scaffolding are in place.

---

### Sub-Task 2 — Data Audit & Data Dictionary
**Status:** `[x] done`  
Confirmed: DQI-001 (allergy patient_id 100% null), DQI-005 (dose_unit, frequency, route 100% null), referential integrity documented. No changes required.

---

### Sub-Task 3 — Admission Cohort & Medication Timeline
**Status:** `[x] done`  
Admission cohort definition, temporal ordering, pre-admission/admission windows implemented. No changes required.

---

### Sub-Task 4 — Feature Engineering
**Status:** `[x] done`  
16 features implemented. `allergy_count` and `has_drug_allergy` are confirmed always-0 (DQI-001) and are documented as non-informative. They may remain in the feature vector for reproducibility but must be flagged in `docs/feature_dictionary.md` and the MODEL_CARD.

---

### Sub-Task 5 — Synthetic MedRec Label Generation ← REVISED

**Status:** `[~] partial — random proxy must be replaced`

#### Problem with Current State
`has_discrepancy` is assigned via `np.random.choice([0,1], p=[0.40, 0.60])` — completely random. This produces ROC-AUC ~0.50. The spec explicitly rejects this as an acceptable final training target.

#### Revised Objective
Replace the random proxy with a **reproducible, longitudinal-data-driven** synthetic MedRec case generator. Labels must be derived from actual Synthea medication patterns (presence/absence of medications across encounters), not from a random coin flip.

#### Revised Label Logic

| Label | Trigger condition (derived from Synthea data) |
|---|---|
| `NONE` | Pre-admission and admission medication lists are concordant (no mutation introduced) |
| `OMISSION` | A medication active in pre-admission window (authored_on < encounter_start) is absent from the admission medication list (encounter window). RxNorm code used as primary key. |
| `DUPLICATION` | Same RxNorm code appears ≥2 times in the admission medication list |
| `DOSE_DISCREPANCY` | Same medication appears in both windows with different `dose_value` — ONLY if `dose_value` is non-null in both records |
| `FREQUENCY_DISCREPANCY` | DISABLED — `frequency` field is 100% null (DQI-005). Must not be generated. |
| `ROUTE_DISCREPANCY` | DISABLED — `route` field is 100% null (DQI-005). Must not be generated. |

#### Revised Schema — `synthetic_cases.csv`

```
case_id, patient_id, encounter_id, mutation_type, source_medication_code,
source_medication_name, random_seed, label, mutation_description, provenance
```

Note: `provenance` column added per spec §6. Value: human-readable description of what Synthea data observation triggered the label (e.g., `"omission_from_synthea_longitudinal_gap"`).

#### Required Classification of "Natural" vs "Artificial" Cases

The revised generator should distinguish:
- **Natural OMISSION**: medication was genuinely in pre-admission records and absent from admission records per actual Synthea data — label naturally derived, no mutation needed
- **Artificial OMISSION**: medication was present in both windows; generator removed it from the admission copy to create a training case
- Both count as `OMISSION` label, but `mutation_description` must differentiate

#### Acceptance Criteria (Revised)
- Every label is traceable to a specific Synthea medication record (not a random number)
- `random_seed` stored per case; identical seed → identical output
- `case_id` globally unique
- `provenance` column populated for every row
- Leakage assessment updated in `docs/label_definition.md`: document which features correlate with the new labels (OMISSION should correlate with `discontinued_medication_count`, DUPLICATION should correlate with `potential_duplicate_candidates`)
- Document explicitly: "These are controlled synthetic engineering targets. They are NOT clinical ground truth."
- Distribution of label types documented (NONE / OMISSION / DUPLICATION / DOSE_DISCREPANCY counts)
- ROC-AUC with new labels should exceed 0.50 if label construction is valid (signals are structurally present in features)

#### Files to Change
- `src/labels/synthetic_case_generator.py` — REVISED (remove random proxy, add longitudinal derivation)
- `data/processed/synthetic_cases.csv` — regenerated
- `data/processed/model_ready.csv` — regenerated after new labels
- `docs/label_definition.md` — updated with new label logic
- `docs/DECISION_LOG.md` — record the decision

---

### Sub-Task 6 — Rule Engine
**Status:** `[x] done`  
Config-driven rule engine with OMISSION and DUPLICATION rules active. DOSE/FREQ/ROUTE rules disabled per DQI-005. No changes required to the rule engine itself.

---

### Sub-Task 7 — ML Prioritizer ← REVISED

**Status:** `[~] partial — multi-metric selection required after new labels`

#### What Changes
1. Labels will change (Sub-Task 5 revised). Model must be retrained after new `model_ready.csv` is generated.
2. Model selection must be multi-metric, not ROC-AUC-alone.
3. Ensemble (Voting) should be added as a 5th candidate for comparison only.

#### Revised Model Selection Criteria

Do NOT select the best model using a single metric. Selection must consider:

| Metric | Minimum acceptable |
|---|---|
| ROC-AUC | Used for ranking but not sole criterion |
| PR-AUC | Required — useful under class imbalance |
| F1 | Required |
| Calibration (Brier) | Lower = better; calibrated probabilities matter for threshold-based prioritization |
| Top-K Recall (10%, 20%) | **Primary operational metric** — model that captures more discrepancy-positive encounters in top-10/20% is preferred |

**Recommended selection logic:**  
Select the model with the best `top_20pct_recall` on the validation set. If tied within 0.02, prefer higher F1. Document the selection rationale in `docs/DECISION_LOG.md`.

#### Revised Output Terminology

| Old term | New term |
|---|---|
| `risk_probability` | `discrepancy_likelihood` (or keep `risk_probability` internally, but label it "Predicted Discrepancy Likelihood" in all user-facing output) |
| `priority` | `review_priority` or "Medication Review Priority" in user-facing text |
| "HIGH risk" | "HIGH priority for medication review" |

Note: internal API field names (`risk_probability`, `priority`) may remain for backward compatibility. Terminology change is required in all documentation, Streamlit UI, LLM prompts, and MODEL_CARD.

#### Top-K Recall — Hackathon Metric
The evaluation report must include a simulation section:
- 100 admissions → model ranks all patients → pharmacist reviews top 10% (10 patients) and top 20% (20 patients)
- Report: how many discrepancy-positive cases are captured in the top-K
- This metric demonstrates operational value of PrioMed-Rec under limited pharmacist capacity

#### Acceptance Criteria (Revised)
- All 4 (or 5 with ensemble) models benchmarked
- Model selected by multi-metric evidence, not ROC-AUC alone
- `eval_report.json` contains all metrics: precision, recall, F1, ROC-AUC, PR-AUC, Brier, confusion matrix, top_k_recall
- Top-K recall simulation included and described in hackathon-friendly language in docs
- MODEL_CARD updated to reflect new labels and new selection rationale
- Tests pass: `test_model.py` asserts that `eval_report.json` contains top_k_recall keys

#### Files to Change
- `src/models/evaluate.py` — add/verify multi-metric `select_best_model()` logic
- `src/models/train.py` — add ensemble candidate (optional)
- `run_training.py` — print all metrics, document selection
- `models/eval_report.json` — regenerated with new metrics
- `models/metadata.json` — updated model_version to `model-0.3.0` after retraining
- `docs/MODEL_CARD.md` — update metrics, terminology, label section

---

### Sub-Task 8 — SHAP Explainability
**Status:** `[x] done`  
SHAP explainer implemented. Returns top-5 features with direction. No changes required to the explainer. Terminology in output should use "Predicted Discrepancy Likelihood" in user-facing text.

---

### Sub-Task 9 — FastAPI Backend ← REVISED

**Status:** `[~] partial — new endpoints and revised /analyze required`

#### What Changes

1. **`POST /analyze` must accept patient_id-driven input** — the current implementation still requires 16 feature fields from the caller. The revised `/analyze` must:
   - Accept: `{ patient_id, encounter_id (optional), question (optional) }`
   - Internally: call `patient_service.py` to resolve patient data → build feature vector → run ML → run rule engine → LLM
   - Never expose the feature vector construction to the caller

2. **`GET /patient/{patient_id}`** — new endpoint returning structured patient/admission context

3. **Terminology** — `risk_probability` field may stay (internal), but response descriptions must say "Predicted Discrepancy Likelihood"

#### Revised Endpoint Contract

**`GET /health`** — unchanged  
```json
{ "status": "ok", "model_version": "...", "rule_version": "...", "api_version": "..." }
```

**`GET /patient/{patient_id}`** — NEW  
```json
{
  "patient_id": "...",
  "encounters": [ { "encounter_id": "...", "encounter_start": "...", "encounter_class": "IMP" } ],
  "latest_admission": { "encounter_id": "...", ... }
}
```

**`POST /prioritize`** — unchanged (expert/developer use)  
Input: feature dict  
Output: `{ risk_probability, priority, model_version, threshold_version, top_features[] }`

**`POST /discrepancies`** — unchanged (expert/developer use)  
Input: `{ patient_id, encounter_id, pre_admission_meds[], admission_meds[] }`  
Output: `{ patient_id, encounter_id, rule_version, flags[] }`

**`POST /review`** — add `model_version` + `rule_version` to audit record  
Input: `{ case_id, pharmacist_id, ai_result, action, pharmacist_note, edited_result? }`  
Output: `{ review_id, case_id, action, timestamp, pharmacist_id, model_version, rule_version, final_result }`

**`POST /analyze`** — REVISED signature  
```json
// Minimal call (patient-id-driven):
{ "patient_id": "P001" }
// Full call with encounter + question:
{ "patient_id": "P001", "encounter_id": "E123", "question": "Kenapa prioritas tinggi?" }
```
Output: `{ patient_id, encounter_id, discrepancy_likelihood, review_priority, model_version, top_features[], flags[], rule_version, report, report_available }`

#### New File: `api/routes/patient.py`
- `GET /patient/{patient_id}` — delegates to `api/services/patient_service.py`

#### New File: `api/services/patient_service.py`
- `get_patient_context(patient_id, encounter_id)` — loads admission data, builds feature vector
- `resolve_latest_admission(patient_id)` — finds most recent IMP encounter
- Calls `src/features/feature_pipeline.py` and `src/data/patient_resolver.py`

#### New File: `src/data/patient_resolver.py`
- `resolve_patient(patient_id, encounter_id=None)` → structured admission context dict
- Reads from `data/processed/` and `data/interim/`
- Returns: demographic, admission, pre_meds, admission_meds, feature_vector

#### Acceptance Criteria (Revised)
- `/analyze` accepts `patient_id` only — feature construction is internal
- `/patient/{patient_id}` returns valid response for known patient
- `/review` audit record includes `model_version` and `rule_version`
- Pydantic schemas updated for all new/changed endpoints
- Old 16-feature `/analyze` signature deprecated or schema-guarded with clear error

---

### Sub-Task 10 — LLM Module
**Status:** `[x] done`  
LLM module, prompts, validators implemented. Minor revision needed:
- System prompt and task prompts must use revised terminology ("Medication Review Priority", "Predicted Discrepancy Likelihood")
- Guardrail check must explicitly block output containing "risk" used as "clinical risk probability"

---

### Sub-Task 11 — Langflow Orchestration ← REVISED

**Status:** `[~] partial — orchestrator needs patient-resolution node`

#### Exactly 2 flows (no third flow)

**A. `langflow/priomedrec_orchestrator.json`** ← REVISED  
```
Chat Input (pharmacist: "Analisis pasien P001")
    ↓
Intent Parser (PATIENT_ANALYSIS / RISK_EXPLANATION / DISCREPANCY_QUERY / RANKING / UNKNOWN)
    ↓
Patient ID Extractor (from chat text)
    ↓
FastAPI Patient Lookup Tool (GET /patient/{patient_id})
    ↓
FastAPI Analyze Tool (POST /analyze with patient_id — feature construction internal)
    ↓
Structured Result (risk + discrepancies + top_features)
    ↓
LLM Node (Gemini — explain result in pharmacist language)
    ↓
Output Validator Node
    ↓
Structured Output to Streamlit
```

**B. `langflow/priomedrec_review.json`** — unchanged  
```
AI Result Input
    ↓
Display to Pharmacist
    ↓
Pharmacist Action (APPROVE / REJECT / EDIT)
    ↓
Review Capture (POST /review)
    ↓
Final Reviewed Result
```

#### Acceptance Criteria (Revised)
- Flow A accepts "Analisis pasien P001" and returns full pharmacist result
- Flow A does NOT require user to enter feature values
- API keys not stored in flow JSON
- Flow JSON importable to fresh Langflow instance

---

### Sub-Task 12 — IBM Bob Agent Configuration
**Status:** `[x] done`  
No changes required. Bob is development-only agent, separate from Langflow flows.

---

### Sub-Task 13 — Streamlit UI ← NEW (replaces old `ui/app.py`)

**Status:** `[ ] not started`

#### Objective
Replace the current `ui/app.py` (manual 16-feature sidebar form) with a pharmacist-friendly one-chat-input Streamlit application in `streamlit_app/`.

#### Architecture
```
streamlit_app/
├── app.py                    # Main Streamlit entry point
├── components/
│   ├── chat_handler.py       # Chat input → Langflow → raw response
│   ├── result_view.py        # Pharmacist-friendly result renderer
│   └── review_panel.py       # APPROVE / REJECT / EDIT action panel
└── utils/
    └── langflow_client.py    # HTTP client for Langflow API
```

#### Primary UX Flow

User types in ONE chat input field:
```
"Analisis pasien P001"
"Kenapa pasien P001 diprioritaskan?"
"Apa potensi medication discrepancy pasien P001?"
"Berikan ringkasan medication reconciliation P001"
```

The system:
1. Sends chat text to Langflow orchestrator via `langflow_client.py`
2. Langflow resolves patient, calls FastAPI `/analyze`, gets LLM explanation
3. Streamlit receives structured response and renders it

#### Result View Requirements
The pharmacist result view must contain exactly:

| Section | Content |
|---|---|
| **Patient Summary** | patient_id, age, gender, admission date |
| **Admission Summary** | encounter_id, encounter_class, medication counts |
| **Medication Review Priority** | HIGH / MEDIUM / LOW (color-coded badge) |
| **Predicted Discrepancy Likelihood** | Percentage display (not "risk probability") |
| **Top Contributing Factors** | SHAP feature table (feature, value, direction) |
| **Potential Medication Discrepancies** | Flag cards (type, medication, severity, verification_required) |
| **Model/Rule Explanation** | LLM-generated natural language summary |
| **Safety Notice** | "PrioMed-Rec is a decision-support prototype. It does not replace pharmacists." |
| **Pharmacist Actions** | APPROVE / EDIT / REJECT buttons → POST /review |

Raw feature vector must NOT be visible by default. Optional developer/debug expander is acceptable.

#### Fallback (No Langflow)
If Langflow is not running, Streamlit should fall back to direct FastAPI `/analyze` call with a visible warning.

#### Acceptance Criteria
- Typing "Analisis pasien P001" produces a complete result view without any manual feature entry
- "Medication Review Priority" and "Predicted Discrepancy Likelihood" terminology used throughout
- APPROVE/REJECT/EDIT buttons call `/review` and display confirmation
- Safety notice always visible at bottom
- No raw feature vector exposed in default view
- `streamlit run streamlit_app/app.py` starts without error

---

### Sub-Task 14 — Testing Additions ← NEW

**Status:** `[ ] not started`

#### New Test Files Required

**`tests/test_streamlit.py`**
- Test that `streamlit_app/app.py` imports without error
- Test that `chat_handler.py` constructs correct Langflow payload
- Test that `result_view.py` renders correct sections from mock API response
- Test safety notice is present in rendered output

**`tests/test_langflow_integration.py`**
- Test that Langflow client correctly formats request to orchestrator
- Test fallback behavior when Langflow is unavailable
- Test that Flow B review submission reaches `/review`

#### Additions to Existing Test Files

**`tests/test_labels.py`** — add:
- Test that new synthetic labels are derived from medication data (not random)
- Test that FREQUENCY_DISCREPANCY and ROUTE_DISCREPANCY are never generated
- Test `provenance` column exists in output
- Test that OMISSION label correlates with `discontinued_medication_count` feature

**`tests/test_model.py`** — add:
- Test that `eval_report.json` contains `top_k_recall` keys
- Test that `select_best_model()` considers multiple metrics, not ROC-AUC alone

**`tests/test_api.py`** — add:
- Test `GET /patient/{patient_id}` returns valid response
- Test `POST /analyze` with only `patient_id` (no feature fields) returns valid result
- Test that `/review` response includes `model_version` and `rule_version`

---

### Sub-Task 15 — Documentation Revisions ← NEW

**Status:** `[ ] not started`

#### Files to Update

**`README.md`** — revise:
- Replace "AI-Powered Admission Risk Prioritization" → "AI-assisted admission medication-reconciliation prioritization"
- Replace all `risk_probability` user-facing mentions → "Predicted Discrepancy Likelihood"
- Replace "priority" → "Medication Review Priority" in user-facing sections
- Add Streamlit as primary interface in architecture diagram and quickstart
- Mark Langflow as mandatory orchestration layer, not "opsional"
- Revise "How to run" to `streamlit run streamlit_app/app.py` as primary command
- Update test count and sub-task statuses
- Clearly state: "167 tests passing proves software correctness for the tested cases — not clinical validity or predictive performance"

**`docs/MODEL_CARD.md`** — revise:
- Label section: replace random proxy description with new longitudinal label derivation
- Performance section: update after retraining with new labels
- Terminology: replace "risk_probability" with "Predicted Discrepancy Likelihood"
- Add section: "Software Validation vs ML Validation vs Clinical Validation" distinction
- Add Operational Metric section with Top-K recall simulation description

**`docs/label_definition.md`** — revise:
- Document new label derivation logic (longitudinal)
- Add `provenance` field definition
- Update leakage assessment for new labels
- Confirm FREQUENCY/ROUTE disabled

**`docs/evaluation_protocol.md`** — revise:
- Add multi-metric selection rationale
- Add Hackathon Metric: Top-K recall simulation

**`docs/API_contract.md`** — revise:
- Add `GET /patient/{patient_id}`
- Update `POST /analyze` request schema
- Update `POST /review` response to include `model_version` and `rule_version`

**`docs/architecture.md`** — revise:
- Update to Streamlit-first diagram
- Show Langflow as mandatory orchestration layer
- Remove "user manually enters 16 features" from flow

---

## SECTION 6 — DEPENDENCY GRAPH (Revised)

```
Sub-Task 1: Setup [DONE]
      ↓
Sub-Task 2: Data Audit [DONE]
      ↓
Sub-Task 3: Admission Cohort + Medication Timeline [DONE]
      ↓
      ├────────────────────────┬──────────────────────────────┐
      ↓                        ↓                              ↓
Sub-Task 4: Feature Eng.  Sub-Task 5: Labels (REVISED)   Sub-Task 6: Rule Engine [DONE]
[DONE]                         ↓                              │
      └──────────────┐         ↓                              │
                     └──→ Sub-Task 7: ML Prioritizer ←────────┘
                           (REVISED — retrain after new labels)
                                │
                           Sub-Task 8: SHAP [DONE]
                                │
                           Sub-Task 9: FastAPI (REVISED + new endpoints)
                                │
                ┌───────────────┴────────────────┐
                ↓                                ↓
         Sub-Task 10: LLM [DONE]    Sub-Task 11: Langflow (REVISED)
                │                                │
                └──────────────┬─────────────────┘
                               ↓
                    Sub-Task 13: Streamlit UI (NEW)
                               │
                    Sub-Task 14: Test Additions (NEW)
                               │
                    Sub-Task 15: Documentation Revisions (NEW)
                               │
                    Sub-Task 12: IBM Bob [DONE — final verification only]
```

**Parallelism opportunities:**
| Track | Can run in parallel with |
|---|---|
| Sub-Task 5 (label revision) | Sub-Task 13 (Streamlit skeleton), Sub-Task 15 (doc revisions) |
| Sub-Task 9 (new FastAPI endpoints) | Sub-Task 13 (Streamlit skeleton using mock data) |
| Sub-Task 7 (retrain) | Sub-Task 14 (test additions for non-model tests) |
| Sub-Task 11 (Langflow revision) | Sub-Task 13 (Streamlit — can start with direct API fallback) |

---

## SECTION 7 — CHANGED / NEW FILES

### New (TO CREATE)

```
# Streamlit app (replaces ui/app.py for production use)
streamlit_app/__init__.py
streamlit_app/app.py
streamlit_app/components/__init__.py
streamlit_app/components/chat_handler.py
streamlit_app/components/result_view.py
streamlit_app/components/review_panel.py
streamlit_app/utils/__init__.py
streamlit_app/utils/langflow_client.py

# New API layer
api/routes/patient.py
api/services/patient_service.py

# New data resolver
src/data/patient_resolver.py

# New tests
tests/test_streamlit.py
tests/test_langflow_integration.py
```

### Revised (TO UPDATE)

```
# Labels — remove random proxy, add longitudinal derivation
src/labels/synthetic_case_generator.py

# Model evaluation — multi-metric selection
src/models/evaluate.py          (add multi-metric select_best_model)
run_training.py                 (print all metrics, update model version)

# API — revised /analyze + new /patient
api/routes/analyze.py           (patient_id-driven, internal feature construction)
api/schemas.py                  (add new request/response schemas)

# Langflow — add patient resolution node
langflow/priomedrec_orchestrator.json

# Prompts — updated terminology
src/llm/prompts/system_prompt.txt
src/llm/prompts/task_prompts.py

# Documentation
README.md
docs/MODEL_CARD.md
docs/label_definition.md
docs/evaluation_protocol.md
docs/API_contract.md
docs/architecture.md
docs/DECISION_LOG.md            (record label replacement + UI change)

# Tests — additions
tests/test_labels.py            (new longitudinal label tests)
tests/test_model.py             (multi-metric eval tests)
tests/test_api.py               (new endpoint tests)
```

### Deprecated (SOFT DEPRECATED — keep for compatibility)

```
ui/app.py    → superseded by streamlit_app/app.py
              (keep ui/app.py temporarily as fallback; mark deprecated in file header)
```

---

## SECTION 8 — ACCEPTANCE CRITERIA (Revised per Spec)

### UX / Streamlit

| # | Criterion |
|---|---|
| AC-UX-01 | `streamlit run streamlit_app/app.py` starts without error |
| AC-UX-02 | User can type "Analisis pasien P001" and receive a complete result without entering any feature fields |
| AC-UX-03 | Result view shows all 8 required sections (Patient Summary through Pharmacist Actions) |
| AC-UX-04 | "Medication Review Priority" terminology used (not "risk" or "clinical risk probability") |
| AC-UX-05 | "Predicted Discrepancy Likelihood" used instead of "risk_probability" in all user-visible text |
| AC-UX-06 | Safety notice always visible at bottom of result |
| AC-UX-07 | APPROVE/REJECT/EDIT buttons call `/review` and show confirmation |
| AC-UX-08 | Raw feature vector not visible in default view |
| AC-UX-09 | Falls back gracefully when Langflow is unavailable |

### Labels / ML

| # | Criterion |
|---|---|
| AC-ML-01 | New synthetic labels derived from Synthea medication data — no random `np.random.choice` for `has_discrepancy` |
| AC-ML-02 | FREQUENCY_DISCREPANCY and ROUTE_DISCREPANCY never generated (DQI-005) |
| AC-ML-03 | `provenance` column present in `synthetic_cases.csv` |
| AC-ML-04 | Label generation deterministic: same seed → identical output |
| AC-ML-05 | `eval_report.json` contains: precision, recall, f1, roc_auc, pr_auc, brier, confusion_matrix, top_k_recall (10%, 20%) |
| AC-ML-06 | Model selection rationale documented in `DECISION_LOG.md` with multi-metric evidence |
| AC-ML-07 | Top-K recall simulation included in eval report and explained in plain language |
| AC-ML-08 | `has_discrepancy` label correlates measurably with at least one feature (confirms non-random signal) |

### API

| # | Criterion |
|---|---|
| AC-API-01 | `GET /patient/{patient_id}` returns valid structured response for a known patient |
| AC-API-02 | `POST /analyze` accepts `{ patient_id }` only and returns complete result (internal feature construction) |
| AC-API-03 | `POST /review` response includes `model_version` and `rule_version` |
| AC-API-04 | `/analyze` never returns `risk_probability` in user-facing labels (field may exist internally, labeled "Predicted Discrepancy Likelihood" in docs/Streamlit) |
| AC-API-05 | All original endpoints still pass existing 167 tests |

### Safety / Terminology

| # | Criterion |
|---|---|
| AC-SAF-01 | No occurrence of "clinical risk probability" anywhere in codebase, docs, or UI |
| AC-SAF-02 | "PrioMed-Rec is a decision-support prototype" visible in Streamlit |
| AC-SAF-03 | LLM cannot change `risk_probability`, `priority`, discrepancy labels, or medication lists (verified by existing guardrail tests) |
| AC-SAF-04 | MODEL_CARD clearly states: software validation ≠ ML validation ≠ clinical validation |
| AC-SAF-05 | README states: "167 tests passing proves software correctness, not clinical validity" |

### Langflow

| # | Criterion |
|---|---|
| AC-LF-01 | Flow A accepts free-text patient query and returns full pharmacist result |
| AC-LF-02 | Flow A does not require user to enter feature values |
| AC-LF-03 | API keys not stored in flow JSON |
| AC-LF-04 | Flow B captures pharmacist action and calls `/review` |
| AC-LF-05 | Both flows importable to a fresh Langflow instance |

---

## SECTION 9 — CLINICAL SAFETY GUARDRAILS (Non-Negotiable)

| Component | MAY | MUST NOT |
|---|---|---|
| ML (Prioritizer) | Produce `discrepancy_likelihood` + `review_priority` | Diagnose, prescribe, make treatment decisions |
| Rule Engine | Flag potential discrepancies with `verification_required: true` | Confirm medication errors |
| SHAP/XAI | Explain contributing features | Change prediction values |
| FastAPI | Serve structured results | Expose feature construction internals to callers; autonomous clinical logic |
| LLM | Explain, summarize, format, Q&A | Calculate risk, change score/label/priority, add/remove medications, prescribe |
| Langflow | Orchestrate workflow | Make clinical decisions |
| Streamlit | Present results, capture pharmacist action | Override pharmacist judgment |
| IBM Bob | Call tools, display results | Invent data, override output, make clinical decisions |
| Pharmacist | ALL final clinical decisions | — |

---

## SECTION 10 — HACKATHON POSITIONING

**Tagline:** "AI-assisted admission medication-reconciliation prioritization for clinical pharmacists."

**Core value proposition:**
```
Prioritize the right patient
    → Flag the right discrepancy
        → Explain the evidence
            → Support pharmacist workflow
                → Pharmacist decides
```

**Key demonstration metrics:**
1. **Operational value under limited capacity**: Model ranks 100 admissions; pharmacist reviews top 20% (20 patients); system captures X% of discrepancy-positive cases vs. Y% for random ordering.
2. **Explainability**: Every prediction comes with top-5 SHAP factors and plain-language LLM explanation.
3. **Human-in-the-loop**: Every AI result is APPROVE/REJECT/EDIT-able with full audit trail.
4. **End-to-end demo**: "Analisis pasien P001" → one chat input → complete pharmacist-ready result.

---

## SECTION 11 — EXECUTION ORDER

This plan must not be implemented all at once. Proceed in this order:

1. **Sub-Task 5 (Labels)** — replace random proxy with longitudinal derivation. BLOCKING for Sub-Task 7.
2. **Sub-Task 7 (ML retrain)** — retrain after new labels. Update eval report with all metrics.
3. **Sub-Task 9 (API extensions)** — add `GET /patient/{patient_id}`, revise `POST /analyze`, add `patient_service.py`.
4. **Sub-Task 13 (Streamlit)** — build `streamlit_app/` with one-chat-input UI (can start with direct API fallback before Langflow is ready).
5. **Sub-Task 11 (Langflow)** — update orchestrator with patient-resolution node.
6. **Sub-Task 14 (Tests)** — add new test files and extend existing ones.
7. **Sub-Task 15 (Docs)** — update README, MODEL_CARD, API contract, architecture.

**Parallel tracks after Step 1 is complete:**
- Steps 2 + 3 can proceed in parallel (different files)
- Steps 4 + 5 can start in parallel after Step 3 (Streamlit can use mock data initially)
- Step 6 runs continuously alongside all steps

Only after Steps 1–7 are complete and all acceptance criteria pass should the project be considered ready for hackathon presentation.
