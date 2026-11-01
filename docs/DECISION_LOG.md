# Decision Log — PrioMed-Rec

This log records all non-trivial technical and data decisions made during the project. Every entry must have an ID, date, status, context, decision, and rationale. Decisions here are binding for downstream pipeline code.

**Format:** `DQI-XXX` = Data Quality decision | `ENG-XXX` = Engineering decision | `MDL-XXX` = Model decision | `CLN-XXX` = Clinical safety decision

---

## DQI-001 — `allergies.patient_id` is 100% null

**Date:** 2025  
**Status:** DECIDED  
**Severity:** High — blocks allergy-based features  

**Context:**  
`allergies.csv` contains 15,802 rows. The `patient_id` column is null for every single row, making it impossible to join allergy records to any patient or encounter.

**Decision:**  
Allergy data is **excluded** from the feature matrix (Sub-Task 4) and from the discrepancy engine (Sub-Task 6). Allergy-based features (`allergy_count`, `has_drug_allergy`) are set to `0` / `False` with a documented provenance flag.

**Rationale:**  
Using a column that is 100% null would introduce silent feature errors. The safest approach is to exclude rather than impute. If `patient_id` is recoverable from the raw Synthea FHIR export in a future iteration, this decision can be revisited.

**Impact:**  
- `src/features/clinical_features.py`: allergy features return constant 0
- `docs/feature_dictionary.md`: allergy features flagged as `data_unavailable`

---

## DQI-002 — `primedrec_master.csv` duplicate columns (`_x` / `_y`)

**Date:** 2025  
**Status:** DECIDED  

**Context:**  
`primedrec_master.csv` was created by a pandas merge in Colab. The join produced duplicate columns: `encounter_start_x`, `encounter_start_y`, `birth_date_x`, `birth_date_y`.

**Decision:**  
Use the `_x` variants as canonical. Drop `_y` variants in all downstream processing.

- `encounter_start` → `encounter_start_x`
- `birth_date` → `birth_date_x`

**Rationale:**  
The `_x` suffix indicates the left-join side, which originates from `primedrec_risk_features` (the primary feature table). Both variants contain identical values (confirmed by inspection), so either would work — `_x` is chosen for consistency.

**Impact:**  
- `src/data/admission_cohort.py`: rename `encounter_start_x` → `encounter_start` and drop `_y` columns on load.

---

## DQI-003 — `encounter_class_display` is 100% null

**Date:** 2025  
**Status:** DECIDED  

**Context:**  
`encounter_class_display` is null in both `encounters.csv` and `primedrec_master.csv` (100% null, all 488,422 rows).

**Decision:**  
Do not use `encounter_class_display`. Use `encounter_class` (FHIR code: `AMB`, `IMP`, `EMER`, `HH`, `VR`) directly for all encounter-type logic.

**Rationale:**  
`encounter_class` is fully populated and carries the same semantic information via FHIR coding.

---

## DQI-004 — `medication_requests` has 36.1% null medication names/codes

**Date:** 2025  
**Status:** DECIDED  

**Context:**  
319,329 of 885,606 rows in `medication_requests.csv` have null `medication_name`, `medication_code`, and `medication_system`. These rows appear to use a medication reference UUID not expanded in the export.

**Decision:**  
For medication identity matching and discrepancy detection, **prefer `medication_administrations.csv`** as the primary source (medication_name and medication_code are 100% populated there). When using `medication_requests`, filter to rows where `medication_name IS NOT NULL`.

**Rationale:**  
`medication_administrations` has complete medication identity data and is closer to actual clinical events. Medication requests with null names cannot be meaningfully reconciled.

---

## DQI-005 — `medication_requests` dose/route/frequency/timing fields are 100% null

**Date:** 2025  
**Status:** DECIDED  

**Context:**  
Columns `dose_unit`, `frequency`, `timing_text`, `route` in `medication_requests.csv` are 100% null across all 885,606 rows. `dose_value` is 67.5% null.

**Decision:**  
Dose-level, frequency-level, and route-level discrepancy checks (`POTENTIAL_DOSE_MISMATCH`, `POTENTIAL_FREQUENCY_MISMATCH`, `POTENTIAL_ROUTE_MISMATCH`) **cannot be computed from `medication_requests`**. These checks are deferred or marked as `UNRESOLVED` in the rule engine output.

**Rationale:**  
It is clinically safer to output `UNRESOLVED_MEDICATION_MATCH` than to silently skip a check that has no data. The pharmacist reviewer is informed of the data limitation.

**Impact:**  
- `configs/discrepancy_rules.json`: dose/route/freq rules set to `enabled: false` with `reason: "data_unavailable"`
- Rule engine outputs `UNRESOLVED` flags for these rule types

---

## DQI-006 — `medication_requests.encounter_id` has 50.9% orphan references

**Date:** 2025  
**Status:** DECIDED  

**Context:**  
450,480 of 885,606 rows in `medication_requests.csv` have an `encounter_id` that does not appear in `encounters.csv`. These are likely medication requests not associated with a specific encounter (e.g., long-term prescriptions, outpatient refills).

**Decision:**  
For the **admission cohort** (Sub-Task 3), only medication requests where `encounter_id` matches a known encounter are used. Unmatched requests are retained in a separate `orphan_med_requests` set and may be used for "pre-admission medication history" reconstruction.

**Rationale:**  
Admission reconciliation requires knowing which encounter the medication is tied to. Orphan requests may still represent the patient's chronic medication list — useful as context but not as admission-specific events.

**Impact:**  
- `src/data/admission_cohort.py`: join strategy documented
- `src/data/medication_timeline.py`: includes orphan requests as "background" meds with lower confidence

---

## ENG-001 — Use `utf-8-sig` encoding for all CSV reads

**Date:** 2025  
**Status:** DECIDED  

**Context:**  
All Synthea CSV files (except `validation_report.csv`) carry a UTF-8 BOM marker. Standard `utf-8` encoding does not strip this, causing phantom characters in column names.

**Decision:**  
All `pd.read_csv()` calls in this project use `encoding="utf-8-sig"`. This is enforced in `src/data/loaders.py`.

---

## ENG-002 — `primedrec_master.csv` is used as the starting point for the admission cohort

**Date:** 2025  
**Status:** DECIDED  

**Context:**  
`primedrec_master.csv` already contains 1 row per encounter with key demographic and medication summary fields, pre-joined in Colab. Reconstructing this join from scratch would be redundant.

**Decision:**  
Use `primedrec_master.csv` as the base for the admission cohort. Apply the canonical column cleanup (DQI-002, DQI-003) and augment with additional features in Sub-Task 4.

**Rationale:**  
Avoids re-running an expensive multi-table merge on 488K+ rows when the result already exists and has been validated (0 parser errors).


---

## ENG-003 — `has_discrepancy` Label Regeneration (model-0.2.0)

**Date:** 2025  
**Status:** DECIDED  
**Severity:** Critical — affected model validity

**Context:**  
The original `has_discrepancy` in `model_ready.csv` was computed as:
```python
label_per_enc = cases.groupby('encounter_id')['label'].max()
```
This mapped `has_discrepancy=1` to any encounter that had at least one non-NONE mutation case generated. Mutations were only generated if the encounter had pre-admission or admission medications. This created structural leakage: `has_discrepancy=1 iff total_medication_count > 0` (verified: a depth-2 decision tree on `total_medication_count` alone achieves accuracy=1.000).

**Decision:**  
Regenerate `has_discrepancy` as an independent random binary label:
```python
np.random.default_rng(42).choice([0, 1], size=n, p=[0.40, 0.60])
```
- 60% positive rate reflects literature estimates for high-risk inpatient admissions
- Completely independent of all 16 feature columns (max correlation < 0.01)
- Deterministic via fixed seed=42

**Rationale:**  
The purpose of the label is to give the ML model a target to learn from. A label that is a trivial function of a single feature yields F1=1.0 and provides no information about model quality. The random proxy is scientifically honest: on synthetic data without real clinical outcomes, a random label with a clinically plausible prevalence rate is the best available proxy.

**Impact:**  
- `data/processed/model_ready.csv`: `has_discrepancy` column regenerated
- `src/models/train.py`: `MODEL_VERSION` bumped to `model-0.2.0`, target default changed
- `models/metadata.json`, `models/eval_report.json`: retrained artifacts
- `docs/MODEL_CARD.md`, `docs/evaluation_protocol.md`: updated metrics

---

## LBL-001 — Replace random proxy label with longitudinal Synthea derivation (labels-2.0.0)

**Date:** 2025
**Status:** DECIDED
**Severity:** Critical — affected model validity

**Context:**
`model-0.2.0` used `has_discrepancy = np.random.default_rng(42).choice([0,1], p=[0.40, 0.60])` — completely random, independent of all features. This was scientifically honest (ROC-AUC ≈ 0.50, confirms no leakage) but provides no learnable signal. The ML model cannot demonstrate any operational value with random labels.

**Decision:**
Replace the random proxy with `labels-2.0.0` — a label derived from Synthea longitudinal medication gap analysis:

1. Compute OMISSION cases: medications in PAML absent from AML
2. Compute DUPLICATION cases: structural duplicate medication evidence
3. Mark every encounter that has at least one OMISSION or DUPLICATION case as a candidate positive

**Rationale:**
Longitudinal medication gaps are structurally informative features of medication reconciliation. Using them as the basis for labels produces a learnable target that reflects the actual pharmacist-relevant signal in the data.

**Impact:**
- `src/labels/synthetic_case_generator.py`: complete rewrite
- `data/processed/synthetic_cases.csv`: 65,637 rows, `provenance` column
- `data/processed/model_ready.csv`: labels-2.0.0
- `docs/label_definition.md`: updated to v2.0.0
- Model ROC-AUC improved from ~0.50 → 0.74

> ⚠️ Labels are controlled synthetic engineering targets. They are NOT clinical ground truth.

---

## LBL-002 — Probabilistic 65% sampling to break feature-label identity

**Date:** 2025
**Status:** DECIDED
**Severity:** Critical — prevented target leakage

**Context:**
The initial LBL-001 implementation set `has_discrepancy = 1` for every encounter with at least one OMISSION or DUPLICATION case. This created a near-perfect identity: `has_discrepancy = 1 iff discontinued_medication_count > 0`, because `discontinued_medication_count` was computed from the same medication gap logic. A depth-2 decision tree on `discontinued_medication_count` alone achieved ROC-AUC = 1.000 — pure target leakage.

**Decision:**
Apply probabilistic 65% sampling of the structurally positive pool (deterministic via seed=42):

```python
rng = np.random.default_rng(42)
positive_encounters = set(
    rng.choice(list(eligible_positive),
               size=int(len(eligible_positive) * 0.65),
               replace=False)
)
```

This means 35% of structurally positive encounters are labeled 0 — breaking the perfect identity while retaining structural signal.

**Rationale:**
65% retention rate is sufficient to preserve structural signal (ROC-AUC = 0.74 on test set). The broken identity prevents a trivial 1-feature classifier from dominating training.

**Impact:**
- `src/labels/synthetic_case_generator.py`: `build_model_ready()` function
- `data/processed/model_ready.csv`: regenerated
- `models/eval_report.json`: ROC-AUC 0.74, label_version = labels-2.0.0

---

## UI-001 — Streamlit as primary user interface; one chat input only

**Date:** 2025
**Status:** DECIDED

**Context:**
The original `ui/app.py` required pharmacists to manually enter 16 ML feature fields + medication lists in a form. This is developer-oriented, not pharmacist-friendly. The revised specification requires ONE CHAT INPUT.

**Decision:**
Create `streamlit_app/app.py` as the primary user interface. User interaction is a single chat input (e.g., "Analisis pasien P001"). The system internally resolves the patient, constructs features, runs ML + rule engine, and returns a structured result. Pharmacists never construct feature vectors.

`ui/app.py` is retained with a deprecation header pointing to `streamlit_app/app.py`.

**Rationale:**
Pharmacists are the end users — not developers. A chat interface is operationally appropriate and matches how pharmacists describe their workflow ("check patient X").

**Impact:**
- `streamlit_app/app.py`, `streamlit_app/components/`, `streamlit_app/utils/`: new files
- `ui/app.py`: deprecated (header added)
- `api/routes/patient.py`, `src/data/patient_resolver.py`: new files enabling patient-id-driven lookup

---

## MDL-001 — Model selection by top_20pct_recall + F1, not ROC-AUC alone

**Date:** 2025
**Status:** DECIDED

**Context:**
`model-0.2.0` selected the best model using ROC-AUC on the validation set. With random labels, ROC-AUC was the only viable discriminant (all models ≈ 0.50). With labels-2.0.0, multiple metrics are meaningful and operationally relevant.

**Decision:**
Primary selection metric: `top_20pct_recall` on validation set.
Tiebreaker: `F1` on validation set.
Rationale: PrioMed-Rec's core operational claim is capacity-constrained prioritization. `top_20pct_recall` directly measures "if a pharmacist reviews only 20% of admissions, what fraction of discrepancy-likely cases are captured?" — the hackathon-relevant operational metric.

Selected model: **RandomForest** (top_20pct_recall = 0.2508, F1 = 0.7893) over XGBoost (0.2442, 0.7849).

**Impact:**
- `src/models/evaluate.py`: `select_best_model()` rewritten
- `src/models/train.py`: MODEL_VERSION = "model-0.3.0"
- `run_training.py`: updated selection logic
- `models/eval_report.json`: selection_metric documented
- `docs/evaluation_protocol.md`: model selection section updated

---

## LBL-003 — Remove 65% probabilistic downsampling (labels-3.0.0)

**Date:** 2025
**Status:** DECIDED
**Severity:** Critical — affected label integrity and model performance

**Context:**
The 65% probabilistic sampling in labels-2.0.0 (LBL-002) was designed to break feature-label identity. However, auditing revealed a better solution: exclude the leaky features from inference entirely (FORBIDDEN_FEATURES + InferenceGuard). The downsampling introduced a 35% false-negative rate on structurally positive encounters — mislabeling encounters that genuinely have OMISSION or DUPLICATION candidates as `has_discrepancy=0`. This contradicts the core label semantics.

**Decision:**
Remove the 65% probabilistic sampling. `has_discrepancy=1` for every encounter with ≥1 OMISSION or DUPLICATION case in `synthetic_cases.csv`. Feature-label leakage is prevented by FTR-001 (SAFE_FEATURES / FORBIDDEN_FEATURES split + InferenceGuard) — not by label corruption.

**Rationale:**
Label integrity is more important than feature-label distance. The correct way to prevent leakage is to exclude leaky features from inference, not to mislabel real positive cases.

**Impact:**
- `src/labels/synthetic_case_generator.py`: `build_model_ready()` — removed 65% sampling
- `data/processed/model_ready.csv`: regenerated, encounter positive rate = 76.3%
- `models/eval_report.json`: ROC-AUC improved 0.74 → 0.897, label_version = labels-3.0.0
- `docs/label_definition.md`: updated to v3.0.0
- Triggered FTR-001 (feature split) and STAB-001 (stabilization)

---

## FTR-001 — Split features into SAFE_FEATURES and FORBIDDEN_FEATURES (features-0.3.0)

**Date:** 2025
**Status:** DECIDED
**Severity:** Critical — prevents feature leakage in inference

**Context:**
After labels-3.0.0 removed the 65% sampling, full-feature (16-feature) evaluation showed ROC-AUC = 1.000 (complete leakage). Audit confirmed that 6 features mirror the label construction logic:
- `discontinued_medication_count` = direct count of OMISSION candidates (corr with label = near-perfect)
- `potential_duplicate_candidates` = direct count of DUPLICATION candidates (same)
- `pre_admission_medication_count`, `admission_medication_count`, `new_medication_count`, `total_medication_count` = label-adjacent aggregates

**Decision:**
Define two named feature sets:
1. `SAFE_FEATURES` (10): demographic + clinical complexity + risk indicators — max |corr| = 0.379
2. `FORBIDDEN_FEATURES` (6): label-adjacent features — rejected at inference by `InferenceGuard`

Add `InferenceGuard` class in `src/models/inference_guard.py`. Guard raises `InferenceGuardError` if any FORBIDDEN feature is present in the inference input. Guard is applied at:
- API level: `api/routes/analyze.py`
- Model level: before `predict_proba()`

Publish `models/feature_manifest.json` as the authoritative registry.

**Rationale:**
A runtime guard is more robust than a documentation note. Forbidden features must be mechanically excluded, not just documented.

**Impact:**
- `src/models/inference_guard.py`: NEW — InferenceGuard + InferenceGuardError
- `src/features/feature_pipeline.py`: SAFE_FEATURES, LEAKAGE_SAFE_FEATURE_COLUMNS, FORBIDDEN_FEATURES
- `models/feature_manifest.json`: authoritative feature manifest
- `src/models/train.py`: retrained on SAFE_FEATURES only
- `docs/feature_provenance.md`: NEW — full leakage analysis
- SAFE_FEATURES ROC-AUC = 0.897 (valid signal); full-feature ROC-AUC = 1.000 (leakage)

---

## MDL-002 — Select XGBoost over RandomForest (labels-3.0.0, features-0.3.0)

**Date:** 2025
**Status:** DECIDED

**Context:**
With labels-3.0.0 and SAFE_FEATURES, model re-evaluation shows XGBoost achieves ROC-AUC = 0.8938 and PR-AUC = 0.9705 on the validation set vs RandomForest ROC-AUC = 0.8891, PR-AUC = 0.9696. All three models achieve identical Top-20% Recall (0.2545) — tied on the primary selection metric.

**Decision:**
Select XGBoost. Tiebreaker: PR-AUC (0.9705 > 0.9696 > 0.9576). PR-AUC is preferred over ROC-AUC as tiebreaker because it is more informative at high positive prevalence (76.3%).

Supersedes MDL-001 (which selected RandomForest under labels-2.0.0).

**Impact:**
- `src/models/train.py`: MODEL_VERSION stays "model-0.3.0"; selected model = XGBoost
- `models/priomed_prioritization_model.pkl`: XGBoost artifact
- `models/priomed_prioritization_model_calibrated.pkl`: isotonic-calibrated XGBoost
- `docs/MODEL_CARD.md`, `docs/evaluation_protocol.md`: updated

---

## STAB-001 — Full stabilization pipeline (run_stabilization.py)

**Date:** 2025
**Status:** DECIDED

**Context:**
After labels-3.0.0 and features-0.3.0 were finalized, a comprehensive stabilization run was performed to confirm:
1. Labels carry genuine signal (not label-engineering artifact)
2. Cross-validation stability
3. Model calibration quality

**Decision:**
Run `run_stabilization.py` which executes:
1. Patient-level split (seed=42)
2. Train LogReg / RF / XGBoost on SAFE_FEATURES
3. Evaluate all models on val + test
4. Isotonic calibration of all models
5. Repeated 5×5 CV (25 CV evaluations per model)
6. 1000-seed permutation test on XGBoost
7. Write `models/eval_report.json` with full v4 schema (top10_rec, top20_rec, top30_rec flat keys)
8. Write `models/priomed_prioritization_model_calibrated.pkl`

**Results:**
- XGBoost test ROC-AUC = 0.8967
- CV ROC-AUC = 0.887 ± 0.012 (stable)
- 1000-seed permutation test: p = 0.0000, 11.72σ above mean
- Isotonic calibration MACE < 0.010 (GOOD)

**Impact:**
- `run_stabilization.py`: NEW stabilization script
- `models/eval_report.json`: v4 schema
- `models/eval_report_v4.json`: v4 schema copy
- `models/priomed_prioritization_model_calibrated.pkl`: calibrated artifact
- `docs/ML_AUDIT_REPORT.md`, `docs/MODEL_CARD.md`, `docs/evaluation_protocol.md`: updated


---

## ARCHITECTURE DECISION RECORDS (ADR-01 … ADR-12)
> Diadopsi dari `PRIOMEDREC_STRATEGIC_DEVELOPMENT_PLAN.md` Bagian 4.3 pada Fase 0.
> Setiap perubahan terhadap ADR ini harus dicatat sebagai entri baru di dokumen ini.

### ADR-01 — FastAPI = Inti Deterministik; Langflow = Lapisan Orkestrasi Narasi

**Tanggal:** Fase 0
**Status:** SUPERSEDED BY ADR-01b untuk orkestrasi Langflow.

**Keputusan:**
FastAPI adalah inti deterministik yang bertanggung jawab atas semua auth, data, ML, rules, SLA, audit, dan guardrail. Langflow diposisikan sebagai lapisan orkestrasi narasi dan copilot (tampil sebagai "otak orkestrasi AI" untuk juri hackathon), bukan sebagai gerbang keselamatan.

**Alasan:**
Keselamatan tidak boleh bergantung pada tool visual/eksternal yang bisa berubah. Langflow tetap tampil sebagai komponen AI penting untuk narasi hackathon.

**Implikasi:**
- Rule engine, ML inference, dan guardrail selalu dijalankan di FastAPI
- Langflow boleh gagal tanpa mematikan fungsi inti

---

### ADR-02 — Browser TIDAK Pernah Memanggil Langflow/LLM Langsung

**Tanggal:** Fase 0
**Status:** DECIDED — ditegaskan kembali dan diperjelas oleh ADR-02b.

**Keputusan:**
Alur wajib: UI → `POST /api/v1/ai/sbar` → FastAPI → Langflow (atau fallback LLM) → guardrail → response. Browser tidak boleh memanggil endpoint Langflow secara langsung.

**Alasan:**
Menjamin auth, audit, guardrail wajib, dan kunci API tidak terpapar ke browser.

**Gap yang ditemukan:**
`web/src/api/langflow.ts` saat ini **melanggar ADR-02** — memanggil Langflow dari browser. Harus diperbaiki di A-301.

**Implikasi:**
- `web/src/api/langflow.ts` perlu direfaktor ke hanya memanggil `/api/v1/ai/*`
- Variabel `VITE_LANGFLOW_*` tidak boleh mengekspos API key Langflow ke browser

---

### ADR-03 — Prioritas Final = max(ML, Aturan, SLA); Aturan & SLA Hanya Bisa Menaikkan

**Tanggal:** Fase 0
**Status:** DECIDED

**Keputusan:**
`tier_final = max(tier_ML, tier_floor_dari_aturan, tier_floor_dari_SLA)`. Aturan klinis dan SLA hanya boleh menaikkan prioritas, tidak pernah menurunkan. Urutan dalam tier: sisa SLA terkecil dulu, lalu probabilitas ML tertinggi.

**Alasan:**
Mencegah ML menurunkan prioritas pasien yang jelas berbahaya. Keselamatan ditegakkan oleh aturan deterministik.

---

### ADR-04 — Label UI: "Prioritas Telaah Farmasi"

**Tanggal:** Fase 0
**Status:** DECIDED

**Keputusan:**
Semua label UI menggunakan "Prioritas Telaah Farmasi" (bukan "Risiko Pasien" atau "Triase"). Skor ditampilkan sebagai "Kemungkinan ada diskrepansi obat".

**Alasan:**
Menghindari klaim triase klinis yang dapat menimbulkan masalah medikolegal.

---

### ADR-05 — SQLAlchemy 2.x + Alembic; SQLite (demo) → PostgreSQL (pilot)

**Tanggal:** Fase 0
**Status:** DECIDED

**Keputusan:**
Database menggunakan SQLAlchemy 2.x sebagai ORM dan Alembic untuk migrasi skema. Demo menggunakan SQLite; pilot menggunakan PostgreSQL. Kode bisnis tidak dikunci ke salah satu database.

**Alasan:**
Migrasi bersih dan portabel tanpa mengubah kode aplikasi.

**Gap yang ditemukan:**
Saat ini `api/database.py` menggunakan `sqlite3` raw tanpa SQLAlchemy. Harus diperbaiki di B-101.

---

### ADR-06 — Auth JWT (access+refresh) + RBAC; API Key Hanya Untuk Layanan

**Tanggal:** Fase 0
**Status:** DECIDED

**Keputusan:**
Login pengguna menggunakan JWT (access token 15 mnt + refresh token). API key (X-API-Key) hanya untuk layanan antar-server (Langflow, MCP) dengan `actor_type` yang dicatat di audit. Identitas aktor selalu dari token, bukan dari body request.

**Alasan:**
Audit dapat dipercaya hanya jika identitas pengguna diverifikasi oleh server, bukan oleh klien.

**Gap yang ditemukan:**
Saat ini tidak ada JWT, `pharmacist_id` dikirim dari body. Harus diperbaiki di B-103.

---

### ADR-07 — Tool Tulis MCP Hanya Membuat DRAFT_REVIEW

**Tanggal:** Fase 0
**Status:** DECIDED

**Keputusan:**
Tool `draft_pharmacist_review` di MCP hanya membuat entri `DRAFT_REVIEW`. Konfirmasi final wajib dari UI oleh apoteker. Tool MCP tidak boleh membuat entri review final.

**Alasan:**
Menjaga HITL (Human-in-the-Loop) walau interaksi dilakukan via percakapan dengan IBM Bob.

**Gap yang ditemukan:**
`mcp_server.py` saat ini memiliki `record_pharmacist_review` yang langsung menyimpan ke `/review` (final). Harus diubah ke draft di A-307.

---

### ADR-08 — medrec_xgboost/ Dibekukan Sebagai Riset

**Tanggal:** Fase 0
**Status:** DECIDED

**Keputusan:**
`medrec_xgboost/` hanya berisi notebook riset. Promosi model ke `models/` hanya via `scripts/promote_model.py` dengan gerbang evaluasi otomatis. Dilarang menyalin file pkl langsung dari `medrec_xgboost/`.

**Alasan:**
Mencegah schema mismatch antara model riset dan model produksi.

---

### ADR-09 — Setiap Fitur ML Memiliki Availability Stage

**Tanggal:** Fase 0
**Status:** DECIDED

**Keputusan:**
Setiap fitur ML diberi label kapan tersedia: `registrasi` / `setelah_bpmh` / `setelah_order`. Inferensi tidak boleh menggunakan fitur yang belum tersedia pada saat permintaan dibuat.

**Alasan:**
Mencegah fitur dari masa depan (temporal leakage) masuk ke inferensi.

**Detail:**
- Tersedia saat registrasi: `age`, `age_65_plus`, `gender_encoded`, `active_condition_count`, `prior_encounter_count`, `allergy_count`, `has_drug_allergy`
- Tersedia setelah BPMH/daftar obat diketahui: `polypharmacy_flag`, `high_alert_flag`, `high_alert_count`

---

### ADR-10 — Nama Model LLM dan Urutan Fallback dari Konfigurasi

**Tanggal:** Fase 0
**Status:** DECIDED

**Keputusan:**
`LLM_MODEL_NAME`, `LLM_FALLBACK_MODEL`, urutan chain, dan timeout dibaca dari `.env` / DB, tidak pernah hardcoded. Health check berkala memverifikasi ketersediaan model.

**Alasan:**
Model dapat dipensiunkan oleh penyedia tanpa mengubah kode.

**Status implementasi:**
Sudah sebagian diimplementasikan di `src/llm/service.py` — perlu penambahan health check proaktif dan penyedia Ollama/watsonx (A-306).

---

### ADR-11 — Guardrail Dijalankan di Backend

**Tanggal:** Fase 0
**Status:** SUPERSEDED BY ADR-11b untuk guardrail pada orkestrasi Langflow.

**Keputusan:**
Guardrail LLM dijalankan sebagai paket Python bersama di backend. Langflow memanggil endpoint guardrail atau mengimpor paket tersebut. Guardrail tidak boleh hanya ada di frontend atau di Langflow saja.

**Alasan:**
Satu sumber kebenaran; versi guardrail tercatat di setiap entri audit.

---

### ADR-12 — Audit Append-Only dengan Rantai Hash

**Tanggal:** Fase 0
**Status:** DECIDED

**Keputusan:**
`audit_entries` append-only dengan kolom `seq`, `prev_hash`, `hash = SHA256(prev_hash ‖ canonical_json(payload))`. Trigger menolak UPDATE dan DELETE. Job verifikasi harian. Koreksi dilakukan via entri baru (amendment), bukan mengubah entri lama.

**Alasan:**
Medikolegal dan akreditasi RS membutuhkan audit trail yang tidak dapat diubah.

**Gap yang ditemukan:**
Saat ini `audit_entries` menggunakan `INSERT OR REPLACE` tanpa hash. Harus diperbaiki di B-107.

---

## ADR Langflow-first (LF-001, 2026-10-29)

### ADR-01b — Langflow-first; FastAPI sebagai gerbang dan cadangan

**Status:** DECIDED — menggantikan ADR-01 untuk orkestrasi Langflow.
Master flow Langflow menjadi jalur utama analisis. FastAPI tetap pemilik auth, state, persistensi, audit, output verifier, dan fallback lokal agar keselamatan klinis tidak bergantung pada Langflow.

### ADR-02b — Browser → FastAPI → Langflow

**Status:** DECIDED — memperjelas ADR-02.
Browser tidak memegang API key atau memanggil Langflow/LLM langsung. FastAPI meneruskan REST/SSE terautentikasi. Gap lama sudah tertutup oleh `web/src/api/langflow.ts` dan kontrak ini tetap wajib.

### ADR-11b — Guardrail dalam flow dan verifikasi ulang API

**Status:** DECIDED — menggantikan ADR-11 untuk orkestrasi Langflow.
Guardrail deterministik berjalan dalam Flow 03/04 dan Output Verifier FastAPI memeriksa ulang hasil sebelum penyimpanan.

### ADR-13 — `priomedrec_core` sebagai sumber tunggal deterministik

**Status:** DECIDED.
Komponen PMR hanyalah adaptor tipis ke paket pure Python; jalur Langflow dan lokal harus memakai kode yang sama.

### ADR-14 — Paritas Langflow↔lokal adalah gerbang CI

**Status:** DECIDED.
Golden set harus identik untuk temuan/tier dan skor dalam toleransi `1e-6`; kegagalan menolak rilis.

### ADR-15 — HITL Langflow melengkapi audit review FastAPI

**Status:** DECIDED.
Resume checkpoint eksternal diuji melalui Workflow API v2. Bila tidak layak, review UI→FastAPI tetap pencatatan resmi dan Flow 05 hanya jalur Playground/Bob/MCP.

### ADR-16 — Policies beta adalah lapisan tambahan

**Status:** DECIDED.
Kode guard hasil generate wajib direview, dites adversarial, dan dikomit; tidak menggantikan guardrail, RBAC, atau HITL.

### ADR-17 — Trace Langflow masuk audit resmi

**Status:** DECIDED.
`trace_id`, hash flow, execution path, durasi, dan ringkasan langkah disimpan di `analysis_runs` dan audit entry.

### ADR-18 — Pin dan allow-list runtime Langflow

**Status:** DECIDED (runtime verification pending).
Image dipin `1.13.0`, rilis stabil terbaru yang tercatat di rilis resmi pada tanggal audit; tag image Docker aktif. Virtualenv lokal masih 1.12.5 dan bukan bukti versi image. Auto-login nonaktif; kredensial environment wajib; komponen operator-installed di `LANGFLOW_COMPONENTS_PATH` read-only. `docker compose config --quiet` lulus; health/spike BLOCKED sampai Docker tersedia.

---

## ADR-19 — Dua Antrean (A: BPMH, B: Telaah) + Pull-based + Lease 15 Menit

**Tanggal:** Fase Q0  
**Status:** DECIDED  
**Referensi:** PRIOMEDREC_QUEUE_MANAGEMENT_PLAN.md §3.1, §3.2, D1  

**Konteks:**
Satu antrean tunggal mencampur TTK (mengisi BPMH) dan apoteker (menelaah), menyebabkan aksi yang salah aktor, antarmuka yang membingungkan, dan metriklagi yang tidak bisa dibedakan.

**Keputusan:**
1. **Dua antrean terpisah:** Antrean A (BPMH) untuk TTK/magang, Antrean B (Telaah) untuk apoteker klinis, dengan urutan berbeda.
2. **Pull-based:** `POST /queue/next` — sistem menarikkan entri teratas yang sesuai cakupan dan menguncinya atomik. Tidak ada "browsing ribuan baris".
3. **Lease 15 menit:** Klaim kedaluwarsa otomatis setelah 15 menit tanpa heartbeat; entri kembali ke antrean dengan usia menunggu tetap (tidak mulai dari nol).
4. **Antrean `PARKED_DPJP`** terpisah dari antrean B — tidak menghukum SLA apoteker saat menunggu DPJP.

**Alasan:**
- Pull-based adalah satu-satunya model yang berfungsi pada ratusan–ribuan entri tanpa membebani apoteker dengan scrolling.
- Dua antrean memungkinkan metrik terpisah (waktu BPMH vs waktu telaah) dan penugasan berbasis peran.
- Lease dengan TTL mencegah kasus "menggantung" saat apoteker tutup tab atau ganti shift.

**Implikasi:**
- Tabel `queue_entries` diperlukan (Q-001).
- `priomedrec_core/queue_engine.py` diperlukan (Q-002).
- State machine perlu transisi ADMIT → A dan BPMH_SUBMIT → B (Q-003).

---

## ADR-20 — Jalur Antrean Bebas LLM/Langflow per Pasien

**Tanggal:** Fase Q0  
**Status:** DECIDED  
**Referensi:** PRIOMEDREC_QUEUE_MANAGEMENT_PLAN.md §12, Q5 aturan antrean  

**Konteks:**
Antrean mengelola ratusan–ribuan entri dengan tick setiap 60 detik. Memanggil LLM per pasien saat tick akan menghabiskan biaya API dan menimbulkan latensi yang tak dapat diterima (target tick < 800 ms untuk 5.000 entri).

**Keputusan:**
Semua fungsi jalur antrean — skor Fase A massal, aging, kuota, SLA tick, klaim/release, lease cleanup — **dijalankan oleh `priomedrec_core` (batch, deterministik) tanpa panggilan LLM/Langflow per pasien per tick**.

Langflow dipakai untuk:
- Analisis per kasus (Fase B, SBAR, guardrail) — dipanggil saat BPMH submit atau kasus dibuka
- Copilot (penjelasan posisi, ringkasan antrean) — baca-saja, per permintaan pengguna
- Notifikasi narasi (webhook opsional) — hanya ringkasan teks

**Alasan:**
- Kehandalan: antrean harus tetap bergerak walau Langflow/LLM mati (G7).
- Biaya: 5.000 entri × tick per menit × harga token LLM = tidak berkelanjutan.
- Deterministik: skor antrean harus reproducible dan dapat diaudit tanpa ambiguitas LLM.

**Implikasi:**
- `queue_engine.py` tidak boleh mengimpor LLM client.
- Uji ketahanan wajib: matikan Langflow → antrean tetap bergerak (G7).

---

## ADR-21 — Kuota HIGH-ML ≤ 25% per Bangsal; Lantai Aturan Klinis Tidak Pernah Turun

**Tanggal:** Fase Q0  
**Status:** DECIDED  
**Referensi:** PRIOMEDREC_QUEUE_MANAGEMENT_PLAN.md §4.2, Q1 aturan antrean; ADR-03  

**Konteks:**
Jika semua entri dengan ML score ≥ 0.65 diberi tier HIGH tanpa batas, antrean bisa penuh dengan HIGH yang kehilangan makna klinis. Sebaliknya, kasus dengan temuan Tier-1 atau obat high-alert harus selalu HIGH tanpa pengecualian.

**Keputusan:**
1. **Kuota HIGH-ML:** Entri yang naik HIGH *hanya* karena skor ML dibatasi ≤ 25% dari antrean aktif per bangsal (default, dapat dikonfigurasi). Sisanya dikelompokkan MEDIUM.
2. **Lantai aturan klinis tidak dikuota:** `tier_source = RULE` (temuan Tier-1, obat high-alert, konflik alergi) selalu HIGH, tidak dibatasi kuota, tidak dapat diturunkan oleh mode lonjakan, kepadatan, atau faktor apapun.
3. **Histeresis:** Perubahan tier akibat ML hanya berlaku jika selisih skor melampaui margin (mencegah baris melompat-loncat).
4. **UI transparan:** Badge "HIGH (aturan)" vs "HIGH (ML)" dan persentil ML ditampilkan.

**Alasan:**
Mengacu Q1 (aturan antrean): "Lantai aturan klinis … TIDAK PERNAH diturunkan oleh kuota, mode lonjakan, histeresis, atau kepadatan." Kuota ML hanya berlaku untuk klaim ML yang belum terkonfirmasi aturan.

**Implikasi:**
- `queue_engine.apply_ml_quota()` wajib mengecualikan entri dengan `tier_source=RULE`.
- Uji properti P2 & P3 (lantai aturan tidak turun, tier tidak turun tanpa re-triage).
- Kebijakan ini butuh konfirmasi apoteker untuk nilai 25% (CRQ-091).

---

## ADR-22 — Hospital Simulator Memanggil API Asli; Semua Output Berlabel "Data Simulasi"

**Tanggal:** Fase Q0  
**Status:** DECIDED  
**Referensi:** PRIOMEDREC_QUEUE_MANAGEMENT_PLAN.md §9, Q6 aturan antrean, D5  

**Konteks:**
Demo statis (10 pasien) tidak meyakinkan juri atau kepala instalasi farmasi. Simulator tiruan (data palsu langsung di UI) tidak menguji sistem secara end-to-end.

**Keputusan:**
1. **Simulator memanggil API asli** (`POST /queue/{id}/admit`, `POST /queue/next`, dll.) menggunakan JWT akun demo per peran (apoteker1, ttk1, koordinator1). Seluruh sistem — auth, antrean, SLA, SSE, audit, Langflow — benar-benar dipakai.
2. **Ukuran default demo: M** (300 entri terbuka, 3/2/1 apoteker per shift). Ukuran L/XL hanya untuk uji beban.
3. **Seed reprodusibel:** `--seed 42` menjamin dua jalankan menghasilkan laporan identik.
4. **Label wajib di semua output:** `"Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS"` — tidak boleh dihilangkan.
5. **Skenario:** `evening_surge` (default demo), `staff_shortage`, `llm_outage`, `ml_outage`.

**Alasan:**
Simulator yang memanggil API asli membuktikan bahwa sistem berfungsi end-to-end di bawah beban realistis, bukan sekadar mockup. Label wajib melindungi dari klaim palsu bahwa angka simulasi adalah data RS nyata (Q6).

**Implikasi:**
- `simulator/` paket baru (Q-007).
- Simulator harus punya akun demo dengan JWT yang valid.
- Laporan akhir simulasi (`docs/SIMULATION_REPORT.md`) digunakan untuk kalibrasi bobot/kuota di Q-002.
- Angka simulasi **tidak boleh** dikutip sebagai hasil RS nyata dalam presentasi.
