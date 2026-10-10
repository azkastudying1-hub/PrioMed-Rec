# Feature Provenance — PrioMed-Rec

**Version:** features-0.2.0
**Label version:** labels-3.0.0
**Related decisions:** `docs/DECISION_LOG.md` (DQI-001, DQI-005, LBL-001, LBL-002, FTR-001)

> **Purpose:** Document the origin, derivation method, and leakage risk of every feature.
> This is mandatory for reproducibility, audit, and clinical safety review.

---

## Feature Sets

Two feature sets are defined:

| Set | Name | Features | Use |
|---|---|---|---|
| Full | `FEATURE_COLUMNS` | 16 | Ablation analysis, leakage assessment |
| Leakage-safe | `LEAKAGE_SAFE_FEATURE_COLUMNS` | 10 | **Primary ML feature set** |

---

## Leakage-Safe Feature Set (PRIMARY — 10 features)

These features are available **before** the medication reconciliation review is performed.
They do NOT require comparing pre-admission vs. admission medication lists.

| Feature | Source | Derivation | Leakage Risk | Status |
|---|---|---|---|---|
| `age` | Admission cohort / demographics | `(encounter_start - birth_date) / 365.25` | None | ✅ Safe |
| `age_65_plus` | Derived from `age` | `1 if age >= 65 else 0` | None | ✅ Safe |
| `gender_encoded` | Patient demographics | `0=F, 1=M, 2=Other` | None | ✅ Safe |
| `polypharmacy_flag` | Admission medication list | `1 if total_medication_count >= 5 else 0` | Low | ✅ Safe* |
| `high_alert_flag` | Admission medication list + config | `1 if any medication in high_alert_medications.json` | Low | ✅ Safe* |
| `high_alert_count` | Admission medication list + config | count of high-alert medications at admission | Low | ✅ Safe* |
| `active_condition_count` | Conditions table | count of active conditions at encounter start | None | ✅ Safe |
| `prior_encounter_count` | Encounters table | count of prior encounters for this patient | None | ✅ Safe |
| `allergy_count` | Allergies table | count of allergy records (DQI-001: constant 0) | None | ✅ Safe (null) |
| `has_drug_allergy` | Allergies table | 1 if any drug allergy (DQI-001: constant 0) | None | ✅ Safe (null) |

> *`polypharmacy_flag`, `high_alert_flag`, `high_alert_count` use the **admission medication list only** (not the comparison between lists). A pharmacist knows what medications are ordered at admission; they do not yet know the gap to pre-admission meds. These are safe.

---

## Full Feature Set (REFERENCE — 16 features)

Includes all leakage-safe features plus the following:

| Feature | Source | Derivation | Leakage Risk | Status |
|---|---|---|---|---|
| `pre_admission_medication_count` | Pre-admission medication list | count of active meds before admission | **HIGH** | ⚠️ Excluded from safe set |
| `admission_medication_count` | Admission medication list | count of meds ordered at admission | Moderate | ⚠️ Excluded from safe set |
| `total_medication_count` | Both lists | `pre_admission + admission - overlap` | **HIGH** | ⚠️ Excluded from safe set |
| `new_medication_count` | Comparison of lists | medications in AML not in PAML | **CRITICAL** | ❌ Label-adjacent |
| `discontinued_medication_count` | Comparison of lists | medications in PAML not in AML | **CRITICAL** | ❌ Label-adjacent |
| `potential_duplicate_candidates` | AML analysis | medications with potential duplicates | HIGH | ⚠️ Label-adjacent |

### Why these features are excluded from the primary set

The labels in `labels-3.0.0` are derived from:
1. **OMISSION**: medications in PAML absent from AML (same logic as `discontinued_medication_count`)
2. **DUPLICATION**: same code >= 2x in AML (same logic as `potential_duplicate_candidates`)

Using `discontinued_medication_count` or `potential_duplicate_candidates` as features creates a **structural shortcut**: the model learns a near-trivial function of the label derivation logic rather than learning to predict discrepancy likelihood from admission characteristics.

**Evidence (labels-3.0.0):**

| Feature | |corr| with has_discrepancy |
|---|---|
| `total_medication_count` | 0.523 |
| `pre_admission_medication_count` | 0.451 |
| `discontinued_medication_count` | 0.451 |
| `admission_medication_count` | 0.386 |
| `new_medication_count` | 0.386 |

All safe-set features have |corr| < 0.40 (max = 0.379 for `active_condition_count`).

**Full-feature models achieve ROC-AUC = 1.0 (perfect prediction)** — confirming complete label-derivation leakage.
**Leakage-safe models achieve ROC-AUC = 0.89** — genuine signal from admission characteristics.

---

## Feature Leakage Classification

| Label-derivation logic | Feature that mirrors it | Classification |
|---|---|---|
| `PAML - AML codes != empty` → OMISSION | `discontinued_medication_count` | **Target leakage** |
| `AML code count >= 2` → DUPLICATION | `potential_duplicate_candidates` | Target leakage |
| `new medications in AML` | `new_medication_count` | Target leakage |
| Total medication burden | `total_medication_count` | Structural leakage |
| Pre-admission list size | `pre_admission_medication_count` | Structural leakage |

---

## Feature Availability Timeline

```
Admission event
  |
  +-- Patient demographics (age, gender)          -> SAFE
  |   [available at registration]
  |
  +-- Clinical history (active conditions,        -> SAFE
  |   prior encounters)
  |   [available from EHR at admission time]
  |
  +-- Admission medication scan                   -> SAFE (with caveats)
  |   (polypharmacy_flag, high_alert_flag,
  |   high_alert_count)
  |   [available once admission orders entered]
  |
  +-- Pre-admission medication reconciliation     -> EXCLUDED (label-adjacent)
  |   (BPMH collection, comparison with
  |   admission list)
  |   (discontinued_count, new_count, gap analysis)
  |   [This IS the pharmacist review process —
  |    using its outputs as ML input conflates
  |    the input with the target]
  |
  v
Pharmacist review begins (ML prediction used HERE)
```

---

## Data Quality Issues Affecting Features

| Issue | DQI ID | Affected Features | Resolution |
|---|---|---|---|
| `allergies.patient_id` 100% null | DQI-001 | `allergy_count`, `has_drug_allergy` | Constant 0; retained as placeholder |
| `dose_unit`, `frequency`, `route` 100% null | DQI-005 | Would enable DOSE/FREQ/ROUTE features | Permanently disabled |
| `medication_requests` 36.1% null name/code | DQI-004 | Affects `discontinued_medication_count` quality | Use `medication_administrations` as primary |

---

## Decision: FTR-001 — Leakage-safe feature set as primary

**Date:** 2025
**Decision:** Use `LEAKAGE_SAFE_FEATURE_COLUMNS` as the primary feature set for all ML training and inference.

**Rationale:**
The full feature set (16 features) includes 6 features derived from medication list comparison — the same comparison used to generate synthetic labels. This creates a structural shortcut where models learn to predict `has_discrepancy` by reconstructing the label derivation rule, not by learning from admission characteristics.

The leakage-safe set (10 features) excludes all medication-comparison-derived features. It achieves ROC-AUC = 0.89 on the test set (vs 1.0 for full features), demonstrating that the model learns genuine signal from demographics, clinical complexity, and medication risk indicators — not just from the label-derivation shortcut.

**Evidence:**
- Full features: max |corr| = 0.523, ROC-AUC = 1.0 (leakage confirmed)
- Safe features: max |corr| = 0.379, ROC-AUC = 0.89 (genuine signal)
- Permutation test (100 seeds): p = 0.00, 4.81σ above permutation mean
