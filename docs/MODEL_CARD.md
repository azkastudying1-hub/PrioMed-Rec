# Model Card — PrioMed-Rec Admission Prioritization Model

**Model version:** `model-0.3.0`
**Feature version:** `features-0.3.0`
**Label version:** `labels-3.0.0`
**Training date:** See `models/metadata.json`

---

## Changelog

| Version | Change |
|---|---|
| `model-0.3.0` (labels-3.0.0, features-0.3.0) | Labels replaced: structural detection only, no 65% downsampling (labels-3.0.0). Feature set narrowed to 10 leakage-safe features (SAFE_FEATURES). InferenceGuard added — rejects forbidden features at runtime. Isotonic calibration applied. 1000-seed permutation test (p=0.0000, 11.7σ). **Selected: XGBoost** (ROC-AUC = 0.897). |
| `model-0.3.0` (labels-2.0.0) | Longitudinal Synthea derivation + 65% probabilistic downsampling. Selected: **RandomForest** (ROC-AUC = 0.74). Downsampling introduced 35% false-negative rate on true positives. |
| `model-0.2.0` | Target changed to `has_discrepancy` (binary random proxy, seed=42). Fixed review_priority target leakage. Random label → ROC-AUC ≈ 0.50 (correct — no signal). |
| `model-0.1.0` | Initial prototype — trained on `review_priority` (caused F1=1.0 leakage). |

---

## Model Overview

| Property | Value |
|---|---|
| **Model type** | XGBoost (selected from: Rule Baseline · Logistic Regression · Random Forest · XGBoost) |
| **Task** | Binary classification — predict `has_discrepancy` (0 = no discrepancy, 1 = discrepancy likely) |
| **Input** | 10 leakage-safe clinical and medication features per admission encounter (SAFE_FEATURES) |
| **Output** | `predicted_discrepancy_likelihood` [0,1] + `medication_review_priority` {LOW, MEDIUM, HIGH} |
| **Use case** | Decision support — pharmacist medication-review ordering priority |
| **Inference guard** | `InferenceGuard` rejects any feature set containing FORBIDDEN_FEATURES at runtime |

> ⚠️ **Terminology:** Output is `Predicted Discrepancy Likelihood` and `Medication Review Priority`.
> It is NOT `clinical risk probability` and does NOT prioritize patients for emergency medical treatment.
> PrioMed-Rec prioritizes the ORDER in which admitted patients should receive pharmacist medication-reconciliation review.

---

## Intended Use

This model assists pharmacists in deciding **which admitted patients to review first** for medication reconciliation when pharmacist capacity is limited. It is a decision-support prototype only.

**Intended users:** Clinical pharmacists in hospital admission workflows.
**Intended setting:** Prototype / research — not validated for clinical deployment.
**Not intended for:** Emergency triage, autonomous prescribing, or any decision that bypasses pharmacist judgment.

---

## Clinical Safety Boundaries

| This model MUST NOT | This model MAY |
|---|---|
| Make autonomous clinical decisions | Rank encounters by medication review priority |
| Override pharmacist judgment | Flag encounters for expedited pharmacist review |
| Claim to detect real medication errors | Provide a structured summary for pharmacist consideration |
| Be used without human review | Explain its prioritization rationale via SHAP values |
| Calculate or modify clinical risk probability | Return `verification_required: true` on every discrepancy flag |

---

## Training Data

| Property | Value |
|---|---|
| **Source** | Synthea Synthetic EHR — entirely synthetic, no real patient data |
| **Size** | 31,625 encounters, 6,159 unique patients |
| **Label** | `has_discrepancy` — derived from Synthea longitudinal structural discrepancy detection (labels-3.0.0) |
| **Label strategy** | `encounter_level_structural_discrepancy_detection` — label=1 iff encounter has ≥1 OMISSION or DUPLICATION candidate; no probabilistic downsampling |
| **Split** | Patient-level 70/15/15 (train/val/test) — no patient crosses splits |
| **Positive rate** | 76.3% (encounter-level) |

> ⚠️ **Label Notice (labels-3.0.0):** `has_discrepancy` is derived from structural medication gap analysis (OMISSION / DUPLICATION). Every structurally positive encounter is labeled 1. Labels are **controlled synthetic engineering targets** — they are NOT clinical ground truth and do NOT represent verified real-world medication errors.
>
> See `docs/label_definition.md` (v3.0.0) and `docs/DECISION_LOG.md` entries LBL-001, LBL-002, LBL-003 for the full derivation history and rationale.

---

## Feature Set (features-0.3.0)

### SAFE_FEATURES (10) — used for inference

| Feature | Type | Description |
|---|---|---|
| `age` | Demographic | Patient age at admission |
| `age_65_plus` | Demographic | Binary flag: age ≥ 65 |
| `gender_encoded` | Demographic | 0/1 encoding |
| `polypharmacy_flag` | Risk indicator | ≥5 medications flag |
| `high_alert_flag` | Risk indicator | Any high-alert medication present |
| `high_alert_count` | Risk indicator | Count of high-alert medications |
| `active_condition_count` | Clinical complexity | Active diagnoses at admission |
| `prior_encounter_count` | Clinical complexity | Prior encounters for this patient |
| `allergy_count` | Allergy | Currently 0 (DQI-001) |
| `has_drug_allergy` | Allergy | Currently 0 (DQI-001) |

### FORBIDDEN_FEATURES (6) — rejected at inference by InferenceGuard

| Feature | Why forbidden |
|---|---|
| `discontinued_medication_count` | Mirrors OMISSION label logic — leakage |
| `potential_duplicate_candidates` | Mirrors DUPLICATION label logic — leakage |
| `pre_admission_medication_count` | Label-adjacent (OMISSION detection) |
| `admission_medication_count` | Label-adjacent (DUPLICATION detection) |
| `new_medication_count` | Label-adjacent |
| `total_medication_count` | Aggregates label-adjacent counts |

> Full leakage analysis in `docs/feature_provenance.md` and `docs/ML_AUDIT_REPORT.md`.

---

## Validation Results (model-0.3.0, labels-3.0.0, features-0.3.0)

> **Selection criterion:** `top_20pct_recall` (primary) + `pr_auc` (tiebreaker) on the **validation set only**.
> The test set is used **once** — for the final report. It is never used for selection or tuning.

### Validation Set

| Model | ROC-AUC | PR-AUC | F1 | Recall | Precision | Brier | Top-20% Rec |
|---|---|---|---|---|---|---|---|
| Rule Baseline | — | — | — | — | — | — | — |
| Logistic Regression | 0.8396 | 0.9576 | 0.7879 | 0.6552 | 0.9879 | 0.1623 | 0.2545 |
| Random Forest | 0.8891 | 0.9696 | 0.8260 | 0.7184 | 0.9715 | 0.1386 | 0.2545 |
| **XGBoost ✅** | **0.8938** | **0.9705** | **0.8275** | **0.7337** | **0.9488** | **0.1336** | **0.2545** |

**Selected model:** XGBoost (highest ROC-AUC and PR-AUC; Top-20% Recall tied across all models)

---

## Test Set Results (model-0.3.0, XGBoost, leakage-safe features)
> **Sumber:** `models/eval_report_v4.json` (STAB-001) — versi ini lebih akurat dari eval_report_v3.json

| Metric | Value | Catatan |
|---|---|---|
| ROC-AUC | **0.8967** | Valid; 11.72σ di atas distribusi permutasi |
| PR-AUC | **0.9666** | ⚠ Dipengaruhi prevalensi tinggi (76%); baseline PR-AUC ≈ prevalensi |
| F1 | 0.8410 | — |
| Recall | 0.7574 | — |
| Precision | 0.9454 | — |
| Brier Score | 0.1322 | Pre-calibration |
| **Top-10% Recall (Lift@10%)** | **0.1318 (Lift 1.32x)** | Model vs random di top-10% antrean |
| **Top-20% Recall (Lift@20%)** | **0.2635 (Lift 1.32x)** | Model vs random di top-20% antrean |
| **Top-30% Recall (Lift@30%)** | **0.3953 (Lift 1.32x)** | Model vs random di top-30% antrean |
| Permutation test (1000 seeds) | p = 0.0000, 11.72σ above mean | XGBoost; max permuted ROC = 0.6149 |
| CV ROC (5×5 repeated) | 0.887 ± 0.012 (CI95: [0.882, 0.892]) | Patient-level GroupKFold |
| Calibration — XGBoost_cal (post-isotonic) | Brier = 0.1116; MACE < 0.010 — **GOOD** | STAB-001 |

### Interpretasi Lift Jujur
| Lift@K | Nilai | Interpretasi |
|---|---|---|
| Lift@10% | 1.32x | Jika apoteker menelaah 10% teratas, menangkap 13.2% kasus vs 10% random |
| Lift@20% | 1.32x | Menangkap 26.4% vs 20% random |
| Lift@30% | 1.32x | Menangkap 39.5% vs 30% random |

> ⚠️ **Catatan Lift:** Lift Top-K = 1.32x adalah moderate. Ini bukan angka yang mengejutkan. Karena prevalensi sangat tinggi (76%), hampir semua encounter dalam top-K sudah positif berdasarkan base rate. Nilai ini **lebih bermakna sebagai bukti bahwa model bisa mengurutkan** daripada sebagai klaim akurasi klinis. Jika prevalensi diturunkan ke ~40% (L2/L3 label), lift akan lebih berarti.

**Confusion matrix (test set, n=4,733):**

> Positive prevalence on test set = 75.85%

|  | Predicted 0 | Predicted 1 |
|---|---|---|
| **Actual 0** | TN: — | FP: — |
| **Actual 1** | FN: — | TP: — |

> ⚠️ **Top-K Prevalence Note:** Top-20% Precision = 1.000 is a prevalence artifact — with 76% positive rate, every encounter in the top 20% ranked by model score is already positive by base rate. Top-20% Recall = 0.2635 reflects the model's ranking power. Lift = 1.32x (vs random baseline 1.00x at this prevalence).

---

## Known Limitations

1. **Synthetic data only:** All data is Synthea-generated — not representative of any real patient population. No external clinical validation has been performed.
2. **Controlled synthetic labels:** `has_discrepancy` (labels-3.0.0) is derived from structural medication gap detection. Labels are NOT clinical gold standard and do NOT represent verified medication errors.
3. **Software validation ≠ ML validation ≠ clinical validation:** 241 passing tests confirm software correctness. They do NOT validate predictive performance or clinical utility.
4. **Missing dose/route/frequency data:** DQI-005 — these fields are 100% null; dose/freq/route discrepancy checks are permanently disabled.
5. **Allergy features unavailable:** DQI-001 — `allergies.patient_id` is 100% null; allergy features are constant 0.
6. **High positive prevalence (76%):** Encounter-level positive rate is 76.3% because almost every admitted patient has at least one medication gap candidate. This inflates Top-K precision metrics.
7. **Artificial DUPLICATION labels:** 76.7% of DUPLICATION training cases are artificially constructed. OMISSION labels are 100% natural Synthea gaps. This asymmetry weakens clinical realism of the DUPLICATION signal.
8. **No temporal/geographic generalizability:** No multi-site or multi-period validation.
9. **Top-K Lift = 1.32x at current prevalence:** Operational value of ranking is reduced when baseline positive rate is already high. Lift metric is most meaningful at lower prevalence (20–40%).

---

## Thresholds

See `configs/model_thresholds.json`. Thresholds are **provisional** — set by the project team, not clinically validated.

| Priority | Condition |
|---|---|
| HIGH | `predicted_discrepancy_likelihood ≥ 0.70` |
| MEDIUM | `predicted_discrepancy_likelihood ≥ 0.40` |
| LOW | `predicted_discrepancy_likelihood < 0.40` |

Thresholds must not be modified by automated systems (e.g. LLM). Any change requires human approval and version increment.

---

## Explainability (XAI)

**Method:** SHAP (SHapley Additive exPlanations) via `src/explainability/shap_explainer.py`

| Model | SHAP Explainer Used |
|---|---|
| XGBoost | `shap.TreeExplainer` |
| Random Forest | `shap.TreeExplainer` |
| Logistic Regression | `shap.LinearExplainer` |
| Rule Baseline | Fallback (uniform zero — no learned weights) |

**Output per prediction:**
- Top-5 contributing features (sorted by |SHAP value|)
- Each feature shows: name, value, shap_value, direction (increases_likelihood / decreases_likelihood / neutral)

**Guardrail:** `get_explanation()` receives `predicted_discrepancy_likelihood` and `medication_review_priority` as inputs and returns them verbatim — it cannot modify them.

---

## Validation Distinction (IMPORTANT)

| Validation Type | Status | Evidence |
|---|---|---|
| **Software validation** | ✅ 241/241 tests pass | `pytest` — correctness of individual components |
| **ML validation (labels-3.0.0)** | ⚠️ Synthetic data only | ROC-AUC 0.897; 1000-seed permutation test p=0.0000, 11.7σ above mean. Top-20% Lift=1.32x. Calibration MACE < 0.010. See `docs/ML_AUDIT_REPORT.md` |
| **Clinical validation** | ❌ Not performed | No comparison against real pharmacist-verified medication error outcomes |
| **External validation** | ❌ Not performed | No multi-site, multi-period, or prospective evaluation |

> **Mandatory disclaimer:**
> Evaluasi dilakukan hanya pada data sintetis Synthea dengan engineered labels. Hasil tidak merepresentasikan clinical validation.
> 241/241 software tests hanya menunjukkan correctness perangkat lunak, bukan validitas ML atau klinis.
> ML digunakan untuk admission-review prioritization, bukan diagnosis maupun keputusan terapi.

---

## Versioning

| Component | Version |
|---|---|
| Model | `model-0.3.0` |
| Labels | `labels-3.0.0` |
| Features | `features-0.3.0` |
| Rules | `rules-0.1.0` |
| Thresholds | `thresholds-0.1.0` |
| API | `1.1.0` |
