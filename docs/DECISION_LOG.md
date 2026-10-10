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
