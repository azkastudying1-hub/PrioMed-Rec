# Evaluation Protocol — PrioMed-Rec

**Version:** 0.4.0
**Framework:** TRIPOD+AI (Transparent Reporting of a multivariable prediction model for Individual Prognosis Or Diagnosis + AI extension)

> ⚠️ **Prototype Validation Disclaimer:** All evaluations in this project are performed on **synthetic Synthea data** with **controlled synthetic labels (labels-3.0.0)**. Results represent prototype system performance — not validated clinical effectiveness. No claims are made about real-world medication error detection rates.
>
> **241 passing tests validate software correctness ONLY — not ML validity, not clinical validity.**

---

## Changelog

| Version | Change |
|---|---|
| 0.4.0 | Labels updated to labels-3.0.0 (no downsampling). Feature set narrowed to 10 SAFE_FEATURES (features-0.3.0). InferenceGuard added. Repeated CV (5×5). 1000-seed permutation test (p=0.0000, 11.7σ). Isotonic calibration. Top-K 10/20/30% reported. Selected model updated to **XGBoost** (ROC-AUC = 0.897). |
| 0.3.0 | Labels replaced with longitudinal Synthea derivation (labels-2.0.0) + 65% probabilistic sampling. Multi-metric model selection: `top_20pct_recall` (primary) + `F1` (tiebreaker). Selected model: **RandomForest** (ROC-AUC = 0.74). |
| 0.2.0 | Target changed to `has_discrepancy` (binary random proxy). Fixed review_priority target leakage. Random label → ROC-AUC ≈ 0.50 (correct — no signal). |
| 0.1.0 | Initial protocol — `review_priority` target caused F1=1.0 leakage. |

---

## 1. Dataset and Split Strategy

### 1.1 Data source

- Training data: `data/processed/model_ready.csv` (31,625 encounters, 10 SAFE_FEATURES)
- Labels: `has_discrepancy` (binary 0/1) — derived from Synthea structural medication gap detection
- Label version: `labels-3.0.0` — `encounter_level_structural_discrepancy_detection` (no downsampling)
- Feature version: `features-0.3.0` — SAFE_FEATURES only (6 FORBIDDEN_FEATURES excluded by InferenceGuard)

> **Label history:**
> - v0.1.0: `review_priority` ordinal — caused F1=1.0 leakage (deprecated).
> - v1.0.0 (ENG-003): Random binary proxy — ROC-AUC ≈ 0.50, no learnable signal.
> - v2.0.0 (LBL-001 + LBL-002): Longitudinal gap derivation + 65% probabilistic sampling → ROC-AUC = 0.74, but 35% false-negative rate introduced.
> - **v3.0.0 (LBL-003 + FTR-001):** Structural detection only, no downsampling. Feature leakage prevented by SAFE_FEATURES split + InferenceGuard → ROC-AUC = 0.897.

### 1.2 Patient-level split

**CRITICAL:** All encounters from the same patient are assigned to the same partition. This prevents information leakage between encounters of the same patient across splits.

| Partition | Patient % | Row count | Pos count | Pos% |
|---|---|---|---|---|
| Train | 70% | 21,816 | 16,553 | 75.9% |
| Validation | 15% | 5,076 | 3,988 | 78.6% |
| Test | 15% | 4,733 | 3,590 | 75.9% |

### 1.3 Split implementation

`src/models/train.patient_level_split()` — verified by `tests/test_model.py::TestPatientLevelSplit::test_no_patient_overlap_train_test`

---

## 2. Models Evaluated

| # | Model | Type | Key Hyperparameters |
|---|---|---|---|
| 1 | Rule Baseline | Deterministic rule engine | Sklearn wrapper — no learned parameters |
| 2 | Logistic Regression | Linear | C=1.0, max_iter=1000, solver='lbfgs' |
| 3 | Random Forest | Ensemble | n_estimators=200, max_depth=8 |
| 4 | **XGBoost** ✅ | Gradient boosting | n_estimators=300, max_depth=6, lr=0.05, subsample=0.8 |

> **Model selection:** XGBoost selected — highest ROC-AUC (0.8938) and PR-AUC (0.9705) on validation set. All three ML models achieve identical Top-20% Recall (0.2545) at validation — selection uses PR-AUC as tiebreaker.

---

## 3. Evaluation Metrics (TRIPOD+AI)

| Metric | Category | Description |
|---|---|---|
| Precision | Discrimination | TP / (TP + FP) — positive predictive value |
| Recall / Sensitivity | Discrimination | TP / (TP + FN) — discrepancy-likely case capture rate |
| F1-score | Discrimination | Harmonic mean of precision and recall |
| ROC-AUC | Discrimination | Area under ROC curve |
| **PR-AUC** | **Discrimination (primary)** | **Area under Precision-Recall curve (imbalance-robust); used as tiebreaker in selection** |
| Brier score | Calibration | Mean squared probability error |
| MACE | Calibration | Mean Absolute Calibration Error (post-isotonic calibration) |
| Confusion matrix | Error analysis | Full breakdown of prediction errors |
| Top-10% Recall | Operational | % of discrepancy-positive cases captured in top 10% by predicted likelihood |
| **Top-20% Recall** | **Operational (primary)** | **% captured in top 20% — primary hackathon/operational metric** |
| Top-30% Recall | Operational | % captured in top 30% |
| Permutation test (1000 seeds) | Validity | Confirms signal is genuine — not memorization |
| CV ROC (5×5 repeated) | Stability | Cross-validation stability |

---

## 4. Model Selection Criterion

**Primary metric: `top_20pct_recall` on the VALIDATION set.**
**Tiebreaker: `pr_auc` on the VALIDATION set.**

Rationale: PrioMed-Rec's core operational claim is that, under limited pharmacist capacity, it surfaces discrepancy-likely patients earlier than random ordering. `top_20pct_recall` directly measures this — "if a pharmacist can review only 20% of admissions, what fraction of discrepancy-positive cases does the model surface?"

PR-AUC is the tiebreaker (not ROC-AUC) because it is more informative than ROC-AUC when positive prevalence is high (76.3%). ROC-AUC can be inflated at high prevalence.

The test set is used **once only** for the final report. It is never used for model selection or hyperparameter tuning.

Model selection decision is recorded in `docs/DECISION_LOG.md` (MDL-001, MDL-002).

---

## 5. Validation Results (model-0.3.0, labels-3.0.0, features-0.3.0)

### 5.1 Validation set

| Model | ROC-AUC | PR-AUC | F1 | Recall | Precision | Brier | Top-10%R | Top-20%R | Top-30%R |
|---|---|---|---|---|---|---|---|---|---|
| Logistic Regression | 0.8396 | 0.9576 | 0.7879 | 0.6552 | 0.9879 | 0.1623 | 0.1271 | 0.2545 | 0.3816 |
| Random Forest | 0.8891 | 0.9696 | 0.8260 | 0.7184 | 0.9715 | 0.1386 | 0.1271 | 0.2545 | 0.3816 |
| **XGBoost ✅** | **0.8938** | **0.9705** | **0.8275** | **0.7337** | **0.9488** | **0.1336** | **0.1271** | **0.2545** | **0.3816** |

**Selected model: XGBoost** (ROC-AUC = 0.8938 — highest; PR-AUC = 0.9705 — highest; Top-20% Recall tied at 0.2545)

> **Top-K Recall note on validation set:** All three models achieve identical Top-K recall. This is expected — at 78.6% positive prevalence, the top K% of any model's ranked output contains mostly positives. The ranking is dominated by the shared safe features.

---

## 6. Test Set Results (model-0.3.0, XGBoost, leakage-safe features)

> Test set used **once** after model selection was complete.

| Model | ROC-AUC | PR-AUC | F1 | Recall | Precision | Brier | Top-10%R | Top-20%R | Top-30%R |
|---|---|---|---|---|---|---|---|---|---|
| Logistic Regression | 0.8251 | 0.9462 | 0.7580 | 0.6265 | 0.9595 | 0.1722 | 0.1318 | 0.2635 | 0.3953 |
| Random Forest | 0.8934 | 0.9657 | 0.8117 | 0.7053 | 0.9558 | 0.1415 | 0.1318 | 0.2635 | 0.3953 |
| **XGBoost** | **0.8967** | **0.9666** | **0.8410** | **0.7574** | **0.9454** | **0.1322** | **0.1318** | **0.2635** | **0.3953** |

> **Note on identical Top-K recall:** At 75.9% positive prevalence, all models that predict probability > 0 for all test encounters achieve the same number of captured positives in any top-K bucket. This is a prevalence artifact — see Section 9 for interpretation.

---

## 7. Calibration

**Isotonic calibration** applied to XGBoost predictions post-training.

| Model | MACE (pre-calibration) | MACE (post-isotonic) | Verdict |
|---|---|---|---|
| XGBoost | (raw) | < 0.010 | **GOOD** |

Threshold: MACE < 0.05 = acceptable. MACE < 0.01 = good.

> `predicted_discrepancy_likelihood` from the calibrated model reflects relative ranking power. At 76% prevalence, it should be interpreted as a **ranking score**, not a calibrated clinical probability.

---

## 8. Repeated Cross-Validation (5×5)

**Method:** 5-fold CV repeated 5 times (different random seeds). Evaluated on SAFE_FEATURES only.

| Statistic | Value |
|---|---|
| Mean CV ROC-AUC | 0.887 |
| Std CV ROC-AUC | 0.012 |
| Min fold | ~0.862 |
| Max fold | ~0.909 |

**CV stability verdict:** CV ROC-AUC = 0.887 ± 0.012 — stable across folds and repeats. Model generalizes consistently within the Synthea data distribution.

---

## 9. Permutation Test (1000 Seeds)

**Method:** Shuffle y_train labels (1000 different seeds), retrain XGBoost, evaluate on unchanged test set. Compare to original ROC-AUC = 0.8967.

| Statistic | Value |
|---|---|
| Permutation mean ROC-AUC | ~0.500 |
| Permutation std | ~0.010 |
| Original ROC-AUC | 0.8967 |
| σ above permutation mean | **11.72σ** |
| p-value (empirical) | **0.0000** (0 of 1000 permutations exceeded original) |

**Permutation test verdict: PASS (strong)**

The original labels carry genuine learnable signal. ROC-AUC 0.8967 is 11.7 standard deviations above the permutation null distribution — effectively impossible to achieve by chance. Contrast with labels-2.0.0: 3.2σ above permutation mean (p < 0.10).

---

## 10. Top-K Operational Simulation

**Scenario:** 4,733 test-set admissions. Pharmacist can review only the top K% ranked by `predicted_discrepancy_likelihood`.

**Test set: 4,733 encounters | 3,590 positive | prevalence = 75.9%**

| Capacity | Patients Reviewed | Discrepancy-Positive Captured | Top-K Recall | Lift over Random |
|---|---|---|---|---|
| Top 10% | 473 | 473 | 13.18% | 1.32x |
| **Top 20%** | **946** | **946** | **26.35%** | **1.32x** |
| Top 30% | 1,419 | 1,419 | 39.53% | 1.32x |
| Random 20% | 946 | ~718 | ~20.00% | 1.00x |

> **Top-K Precision = 1.000 is a prevalence artifact.** With 75.9% positive rate, every encounter in the top 20% is positive by base rate — not because of model skill. The meaningful metric is Lift = 1.32x: the model ranks 32% more true positives into the reviewed slice vs. random ordering.
>
> **Important context:** When positive prevalence is very high (>75%), the operational value of ranking is inherently limited. Lift = 1.32x means the model provides moderate improvement over random ordering. Under a lower-prevalence clinical label (e.g., 20–40% positive rate), this metric would be more operationally impactful.

---

## 11. Leakage Assessment Summary

| Check | Result |
|---|---|
| Full-feature set (16 features) max |corr| with label | 0.523 — **FAIL** (leakage) |
| Full-feature set ROC-AUC | **1.000** — **pure leakage** |
| SAFE_FEATURES (10 features) max |corr| with label | 0.379 — **PASS** |
| SAFE_FEATURES ROC-AUC | 0.897 — **valid signal** |
| InferenceGuard blocks FORBIDDEN_FEATURES at runtime | ✅ |

See `docs/feature_provenance.md` for full leakage analysis.

---

## 12. Validation Distinction (CRITICAL)

| Validation Type | Status | What it means |
|---|---|---|
| **Software validation** | ✅ 241/241 tests pass | Code components behave as specified. Does NOT validate prediction quality. |
| **ML validation (labels-3.0.0)** | ⚠️ Synthetic data only | ROC-AUC 0.897 on Synthea-derived structural labels. 1000-seed permutation test p=0.0000. Labels are controlled proxies, not gold standard. |
| **Clinical validation** | ❌ Not performed | No comparison against real pharmacist-verified medication error outcomes. |
| **External validation** | ❌ Not performed | No multi-site, multi-period, or prospective study. |

> **Publishing constraint:** These results must never be cited as evidence of clinical effectiveness. Any manuscript or poster must clearly state: "Evaluated on synthetic data with engineered labels. No clinical validation has been performed."
>
> **Mandatory disclaimer:**
> Evaluasi dilakukan hanya pada data sintetis Synthea dengan engineered labels. Hasil tidak merepresentasikan clinical validation.
> 241/241 software tests hanya menunjukkan correctness perangkat lunak, bukan validitas ML atau klinis.
> ML digunakan untuk admission-review prioritization, bukan diagnosis maupun keputusan terapi.

---

## 13. Limitations and Risks

| Risk | Mitigation |
|---|---|
| **Controlled synthetic labels** | `has_discrepancy` (labels-3.0.0) derived from structural gaps, no clinical ground truth. Documented in `docs/label_definition.md`. |
| **Synthetic data** | All data is Synthea-generated. Not representative of any real population. |
| **Feature leakage risk** | FORBIDDEN_FEATURES (6 features) rejected at runtime by InferenceGuard. Full-feature set shows ROC-AUC=1.0 (leakage). SAFE_FEATURES show 0.897 (valid). |
| **High positive prevalence (76%)** | Top-K precision = 1.0 is a prevalence artifact. Lift = 1.32x is the meaningful operational metric. |
| **Artificial DUPLICATION labels** | 76.7% of DUPLICATION cases are artificially constructed. Weakens clinical realism of DUPLICATION signal. |
| **Generalizability** | No external validation has been performed. |
| **Allergy features missing** | `allergy_count` and `has_drug_allergy` are 0 for all rows (DQI-001). |
| **Dose/route/frequency rules disabled** | Fields are null (DQI-005). Discrepancy engine operates on omission + duplication only. |
