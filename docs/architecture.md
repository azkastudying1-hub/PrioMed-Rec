# Architecture — PrioMed-Rec

> **STATUS: SUPERSEDED.** Dokumen ini mendeskripsikan arsitektur legacy Streamlit-first.
> Arsitektur aktual: **React/Vite → FastAPI → Langflow → internal deterministic API → verifier**.
> Lihat `docs/WEBSITE_RUNBOOK.md` dan `docs/PANDUAN_MENJALANKAN_DAN_MENGGUNAKAN_APLIKASI.md`.

**Version:** 3.0.0 (Langflow-first)
**Last updated:** See `docs/DECISION_LOG.md`

---

## System Overview

PrioMed-Rec is an AI-assisted Admission Medication Reconciliation Prioritization system for clinical pharmacists. It determines the ORDER in which admitted patients should receive intensive pharmacist medication-reconciliation review when pharmacist capacity is limited.

**Core principle:** Prioritize the right patient → Flag the right discrepancy → Explain the evidence → Support pharmacist workflow → Pharmacist decides.

> ⚠️ **Terminology:** PrioMed-Rec does NOT triage patients for emergency medical treatment. It determines **Medication Review Priority** and outputs **Predicted Discrepancy Likelihood** — not clinical risk probability.

---

## Component Roles

| Component | Role | Constraint |
|---|---|---|
| **Streamlit** | User interface — ONE chat input | Primary pharmacist-facing UI. No feature-vector forms. |
| **Langflow** | Orchestration layer | Mandatory. Routes chat → FastAPI → LLM → response. Never optional. |
| **FastAPI** | Backend / service layer | Pydantic contracts. Never exposes raw feature vectors to callers. |
| **ML model** | Prediction layer | Binary classification. Outputs `predicted_discrepancy_likelihood`. |
| **Rule Engine** | Deterministic discrepancy detection | Config-driven. Transparent baseline. Safety layer. |
| **SHAP** | Model explainability | Explains prediction. Cannot modify model output. |
| **LLM (Gemini)** | Explanation / summarization only | Cannot change scores, labels, medications. Guardrail-enforced. |
| **Pharmacist** | Final decision maker | APPROVE / REJECT / EDIT. Mandatory. |

---

## High-Level Runtime Flow

```
Pharmacist chat input (Streamlit)
    │
    ▼
Streamlit → Langflow (priomedrec_orchestrator.json)
    │
    ├── GET /patient/{patient_id}    ← resolve patient from chat query
    │
    ├── POST /analyze                ← patient_id only; features constructed internally
    │       │
    │       ├── Patient Resolver (src/data/patient_resolver.py)
    │       │       → feature_vector + medication lists
    │       │
    │       ├── ML Model → predicted_discrepancy_likelihood + medication_review_priority
    │       │
    │       ├── SHAP Explainer → top_features
    │       │
    │       └── Rule Engine → discrepancy_flags[]
    │
    ├── LLM (Gemini) → grounded explanation + structured result
    │       └── Output Validator (6 guardrail checks)
    │
    └── Structured response → Streamlit
            │
            ▼
    Pharmacist reviews result
            │
            ▼
    Streamlit → Langflow (priomedrec_review.json)
            │
            └── POST /review → APPROVE | REJECT | EDIT → audit_trail
```

---

## Component Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PHARMACIST INTERFACE                             │
│              Streamlit (streamlit_app/app.py)                           │
│              ONE CHAT INPUT — no feature-vector forms                   │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        LANGFLOW ORCHESTRATOR                            │
│   Flow A: langflow/priomedrec_orchestrator.json                        │
│           chat → patient resolution → analyze → LLM → response         │
│   Flow B: langflow/priomedrec_review.json                              │
│           AI result → pharmacist action → POST /review → audit trail    │
└──────┬─────────────────────────┬──────────────────────────────┬────────┘
       │                         │                              │
       ▼                         ▼                              ▼
┌────────────────┐  ┌────────────────────────┐  ┌──────────────────────┐
│    FASTAPI     │  │      LLM SERVICE       │  │  PHARMACIST REVIEW   │
│  api/main.py   │  │  src/llm/service.py    │  │  POST /review        │
│                │  │                        │  │  APPROVE|REJECT|EDIT │
│ GET  /health   │  │  generate_summary()    │  │  audit_trail record  │
│ GET  /patient/ │  │  explain_risk()        │  │  model_version       │
│ GET  /patients/│  │  explain_discrepancy() │  │  rule_version        │
│ POST /analyze  │  │  answer_query()        │  └──────────────────────┘
│ POST /priorit  │  │                        │
│ POST /discr    │  │  Output Validator      │
│ POST /review   │  │  (6 guardrail checks)  │
└──────┬─────────┘  └────────────────────────┘
       │
       ├────────────────────────────┐
       ▼                            ▼
┌──────────────────┐  ┌────────────────────────────────┐
│   ML MODEL       │  │   RULE ENGINE                  │
│  src/models/     │  │   src/rules/                   │
│                  │  │                                │
│  RandomForest    │  │   discrepancy_engine.py        │
│  (model-0.3.0)   │  │   medication_normalizer.py     │
│                  │  │   rule_evaluator.py            │
│  Target:         │  │                                │
│  has_discrepancy │  │   Enabled rules:               │
│  (binary 0/1)    │  │   - OMISSION                   │
│                  │  │   - DUPLICATION                │
│  labels-2.0.0    │  │   Disabled (DQI-005):          │
└────────┬─────────┘  │   - DOSE_MISMATCH              │
         │            │   - FREQ_MISMATCH               │
         ▼            │   - ROUTE_MISMATCH              │
┌──────────────────┐  └────────────────────────────────┘
│  SHAP EXPLAINER  │
│  src/explainab./ │
│                  │
│  TreeExplainer   │
│  LinearExplainer │
│  Fallback(rules) │
└──────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────┐
│                     DATA LAYER                         │
│                                                        │
│  data/raw/synthea/         ← Synthea EHR CSVs          │
│  data/interim/             ← Cohort, medication lists  │
│  data/processed/           ← Feature matrix, labels    │
│  models/                   ← Trained model, metadata   │
│  configs/                  ← Rule config, thresholds   │
└────────────────────────────────────────────────────────┘
```

---

## Data Flow (Pipeline)

```
Synthea CSVs (data/raw/synthea/)
        ↓
Admission Cohort Builder (src/data/admission_cohort.py)
  → admission_cohort.csv (IMP + EMER + HH encounters only)
        ↓
Medication Timeline (src/data/medication_timeline.py)
  ├── pre_admission_meds.csv  (event_datetime < encounter_start)
  └── admission_meds.csv      (event_datetime ∈ [start, end])
        ↓
Feature Engineering (src/features/)
  → feature_matrix.csv (31,625 × 16)
        ↓
Label Generation (src/labels/synthetic_case_generator.py)
  → synthetic_cases.csv  (65,637 rows, provenance column)
  → model_ready.csv      (31,625 × 19, labels-2.0.0)
        ↓
Model Training (src/models/train.py)
  → priomed_prioritization_model.pkl (RandomForest, model-0.3.0)
  → metadata.json + eval_report.json
```

---

## Two Langflow Flows (Exactly Two)

| Flow | File | Purpose |
|---|---|---|
| **Orchestrator** | `langflow/priomedrec_orchestrator.json` | Chat → patient resolution → GET /patient → POST /analyze → LLM grounded explanation → response to Streamlit |
| **Review** | `langflow/priomedrec_review.json` | AI result → pharmacist APPROVE/REJECT/EDIT → POST /review → audit trail |

> No third flow should be created unless implementation strictly requires it. LLM explanation is embedded in the Orchestrator flow — it does not require a separate flow.

---

## Streamlit UI Structure

```
streamlit_app/
├── app.py                    ← entry point, ONE chat input
├── components/
│   ├── chat_handler.py       ← extract patient_id → call Langflow/FastAPI
│   ├── result_view.py        ← 8-section pharmacist result display
│   └── review_panel.py       ← APPROVE/REJECT/EDIT → POST /review
└── utils/
    └── langflow_client.py    ← Langflow HTTP client + FastAPI fallback
```

**Result view sections:**
1. Patient Summary
2. Admission Summary
3. Medication Review Priority
4. Predicted Discrepancy Likelihood
5. Top Contributing Factors (SHAP)
6. Potential Medication Discrepancies (Rule Engine)
7. Model/Rule Explanation (LLM)
8. Safety Notice + Pharmacist Actions (APPROVE/EDIT/REJECT)

---

## Sub-Task to Component Mapping

| Sub-Task | Component | Key Files |
|---|---|---|
| ST1 | Project Setup | `requirements.txt`, `.env.example`, `README.md` |
| ST2 | Data Audit | `src/data/loaders.py`, `src/data/validator.py`, `data/interim/dqi_report.json` |
| ST3 | Admission Cohort | `src/data/admission_cohort.py`, `src/data/medication_timeline.py` |
| ST4 | Feature Engineering | `src/features/feature_pipeline.py`, `data/processed/feature_matrix.csv` |
| ST5 | Label Generation (v2) | `src/labels/synthetic_case_generator.py`, `data/processed/synthetic_cases.csv`, `data/processed/model_ready.csv` |
| ST6 | Rule Engine | `src/rules/discrepancy_engine.py`, `configs/discrepancy_rules.json` |
| ST7 | ML Model (v3) | `src/models/train.py`, `src/models/evaluate.py`, `models/priomed_prioritization_model.pkl` |
| ST8 | SHAP/XAI | `src/explainability/shap_explainer.py` |
| ST9 | FastAPI (v1.1) | `api/main.py`, `api/routes/`, `api/services/`, `src/data/patient_resolver.py` |
| ST10 | LLM Module | `src/llm/service.py`, `src/llm/validators/output_validator.py` |
| ST11 | Langflow (v2) | `langflow/priomedrec_orchestrator.json`, `langflow/priomedrec_review.json` |
| ST12 | IBM Bob | `bob/mcp_settings.example.json`, `bob/agent_instructions.md` |
| ST13 | Streamlit UI | `streamlit_app/app.py`, `streamlit_app/components/`, `streamlit_app/utils/` |
| ST14 | Testing | `tests/` — 231 tests |
| ST15 | Documentation | `docs/` — MODEL_CARD, label_definition, evaluation_protocol, API_contract, architecture, DECISION_LOG |

---

## Clinical Safety Architecture

| Layer | Safety Mechanism |
|---|---|
| Input validation | Pydantic schemas — age < 0, count < 0 → 422 |
| Patient resolver | 404 on unknown patient, never fabricates data |
| Model output | `medication_review_priority` only LOW/MEDIUM/HIGH; `model_version` always present |
| Rule engine output | `verification_required=True` on every flag |
| LLM output | 6 guardrail checks (`output_validator.py`) — cannot change scores or labels |
| Review loop | Pharmacist must APPROVE/REJECT/EDIT before result is final |
| Audit trail | `review_id`, `model_version`, `rule_version`, `timestamp` on every review |
| No autonomous action | System never modifies therapy; pharmacist decides |

---

## Key Design Decisions

See `docs/DECISION_LOG.md` for full entries.

| ID | Decision |
|---|---|
| DQI-001 | `allergies.patient_id` 100% null → allergy features = 0 constant |
| DQI-005 | `dose_unit/frequency/route` 100% null → dose/freq/route rules disabled |
| LBL-001 | Labels replaced with longitudinal Synthea derivation (labels-2.0.0) |
| LBL-002 | Probabilistic 65% sampling breaks feature-label identity (leakage fix) |
| UI-001 | Streamlit as primary UI — one chat input, no feature-vector form |
| MDL-001 | Best model selected by top_20pct_recall (primary) + F1 (tiebreaker) — not ROC-AUC alone |

---

## Versions

| Component | Version |
|---|---|
| Model | `model-0.3.0` |
| Labels | `labels-2.0.0` |
| Features | `features-0.1.0` |
| Rules | `rules-0.1.0` |
| Thresholds | `thresholds-0.1.0` |
| API | `1.1.0` |
| Langflow flows | `v2` |
