# Label Definition — PrioMed-Rec

**Version:** 3.0.0 (labels-3.0.0)
**Status:** Controlled synthetic labels — NOT clinical ground truth
**Related decisions:** `docs/DECISION_LOG.md` (LBL-001, LBL-002, LBL-003)

> ⚠️ **Synthetic Data Disclaimer:** All labels in this project are engineered from synthetic EHR data (Synthea).
> They represent *controlled proxies* for medication reconciliation review priority — not clinical gold-standard medication error labels.
> See `docs/data_provenance.md`.
>
> **NEVER claim these labels are clinical ground truth.**

---

## Changelog

| Version | Change |
|---|---|
| `3.0.0` | Complete replacement. Removed 65% probabilistic downsampling (LBL-003). `label=1` iff encounter has ≥1 OMISSION or DUPLICATION candidate — no downsampling. Encounter-level positive rate = 76.3%. `generation_seed` column added. `label_version` column = "labels-3.0.0". Short provenance tags used. |
| `2.0.0` | Complete replacement. Labels derived from Synthea longitudinal medication gap analysis (OMISSION/DUPLICATION) + probabilistic 65% sampling to break feature-label identity (LBL-002). ROC-AUC improved to 0.74 but downsampling introduced 35% false-negative rate on structurally positive encounters. |
| `1.0.0` | `has_discrepancy` = random binary proxy via `np.random.default_rng(42).choice([0,1], p=[0.40, 0.60])`. ROC-AUC ≈ 0.50 confirmed no signal. |
| `0.1.0` | `review_priority` ordinal target — caused F1=1.0 target leakage (deprecated). |

---

## 1. Admission Cohort Definition

### 1.1 What is an "admission"?

An admission is any encounter in the Synthea dataset with an `encounter_class` value in the following set:

| `encounter_class` | FHIR Description | Included? | Rationale |
|---|---|---|---|
| `IMP` | Inpatient | ✅ **Primary** | Core admission scenario; highest medication reconciliation relevance |
| `EMER` | Emergency | ✅ Included | ED admissions frequently require reconciliation; often transition to inpatient |
| `HH` | Home Health | ✅ Included | Monitored care context; medication lists must be reconciled |
| `AMB` | Ambulatory / Outpatient | ❌ Excluded | Routine outpatient — different reconciliation workflow |
| `VR` | Virtual | ❌ Excluded | Telehealth — medication events minimal |

**Cohort size (from actual data):** 31,625 encounters | 6,159 unique patients

### 1.2 Temporal anchor

For each admission encounter:
- **Pre-admission window:** `event_datetime < encounter_start`
- **Admission window:** `encounter_start ≤ event_datetime ≤ encounter_end`
- **Post-admission:** `event_datetime > encounter_end` — **never used as a feature input or label input**

---

## 2. Medication Lists

### 2.1 Pre-Admission Medication List (PAML)

The medication list a patient was taking **before** admission, derived from:

- `medication_requests` where `authored_on < encounter_start` AND `status = 'active'`
- Source: `data/interim/pre_admission_meds.csv`

**Leakage prevention:** Strict `<` (not `≤`) comparison on `encounter_start`. Any medication authored on the exact same timestamp as admission is classified as an admission medication.

### 2.2 Admission Medication List (AML)

The medication list ordered **during** the admission encounter window:

- `medication_requests` OR `medication_administrations` where `event_datetime ∈ [encounter_start, encounter_end]`
- Primary identity source: `medication_administrations.medication_name/code` (100% populated, per DQI-004)
- Source: `data/interim/admission_meds.csv`

---

## 3. Synthetic Label Strategy (labels-3.0.0)

### 3.1 Why labels are engineered

Synthea does not contain real medication reconciliation outcomes (no pharmacist review records, no verified discrepancy flags). Labels must be derived from structural properties of the data.

### 3.2 Discrepancy case types

| Type | Description | Enabled? | Provenance |
|---|---|---|---|
| `NONE` | No structural gap detected | ✅ | Natural — no mutation |
| `OMISSION` | Medication in PAML but absent from AML | ✅ | Natural (18,554 natural cases) |
| `DUPLICATION` | Same medication appears in both lists or added twice | ✅ | Natural + artificial (3,607 + 11,851) |
| `DOSE_DISCREPANCY` | Dose value differs between PAML and AML | ❌ Disabled | DQI-005 — `dose_value` and `dose_unit` 100% null in source |
| `FREQUENCY_DISCREPANCY` | Frequency differs | ❌ Disabled | DQI-005 — `frequency` 100% null in source |
| `ROUTE_DISCREPANCY` | Route differs | ❌ Disabled | DQI-005 — `route` 100% null in source |

> ⚠️ **DQI-005 enforcement:** DOSE/FREQ/ROUTE discrepancy types are permanently disabled because the underlying fields are 100% null in `medication_requests.csv`. These types must not be re-enabled without verified non-null source data.

### 3.3 Synthetic case record schema

Every case in `data/processed/synthetic_cases.csv` has the following fields:

| Field | Description |
|---|---|
| `case_id` | Unique case identifier (UUID format) |
| `patient_id` | Synthea patient UUID |
| `encounter_id` | Synthea encounter UUID |
| `mutation_type` | NONE / OMISSION / DUPLICATION |
| `source_medication` | Medication involved (name or code) |
| `random_seed` | Seed used for any stochastic mutation (integer or null) |
| `generation_seed` | Top-level seed for the case generation run (integer) |
| `label` | 0 (no discrepancy) / 1 (discrepancy candidate) |
| `label_version` | "labels-3.0.0" |
| `provenance` | Short origin tag: `no_discrepancy`, `natural_omission`, `natural_duplication`, `artificial_duplication` |

> **Note on short provenance tags (labels-3.0.0):** Tags were shortened for readability. Full provenance text used in labels-2.0.0 (`natural_omission_from_synthea_data`, etc.) is preserved in the legacy data artifact.

**Total synthetic cases:** 65,637

### 3.4 `has_discrepancy` binary target construction (labels-3.0.0)

The binary ML target `has_discrepancy` in `data/processed/model_ready.csv` is constructed as follows:

```python
# Deterministic: label=1 for every encounter that has at least one
# OMISSION or DUPLICATION case in synthetic_cases.csv.
# NO probabilistic downsampling (contrast: labels-2.0.0 applied 65% sample).
positive_encounters = set(
    cases[cases["mutation_type"].isin(["OMISSION", "DUPLICATION"])]["encounter_id"]
)
has_discrepancy = encounter_id.isin(positive_encounters).astype(int)
```

**Why remove 65% downsampling (LBL-003)?**
The 65% sampling in labels-2.0.0 was designed to break feature-label identity (prevent leakage). However, it introduced a 35% false-negative rate on encounters that genuinely have structural discrepancy candidates. This degraded label integrity without equivalent benefit — the feature-label leakage problem is better solved by removing the leaky features from the inference set entirely (features-0.3.0 SAFE_FEATURES / FORBIDDEN_FEATURES split + InferenceGuard). See `docs/DECISION_LOG.md` LBL-003 and FTR-001.

### 3.5 Anti-leakage guarantees (labels-3.0.0)

- All medication timeline inputs are strictly temporally bounded (pre-admission window only).
- `has_discrepancy` = structural presence of OMISSION/DUPLICATION — deterministic and reproducible.
- FORBIDDEN_FEATURES (6 label-adjacent features) are excluded from inference at runtime by `InferenceGuard`. See `docs/feature_provenance.md`.
- No post-admission data is used in any label construction.
- Explicitly excluded from label construction: length of stay, discharge diagnosis, post-admission labs, readmission flags.

---

## 4. ML Target Distribution (labels-3.0.0)

### 4.1 Encounter-level

| Label | Count | % |
|---|---|---|
| 0 (no discrepancy) | 7,494 | 23.7% |
| 1 (discrepancy candidate) | 24,131 | 76.3% |

### 4.2 Patient-level split

| Split | Rows | Pos | Pos% |
|---|---|---|---|
| Train | 21,816 | 16,553 | 75.9% |
| Validation | 5,076 | 3,988 | 78.6% |
| Test | 4,733 | 3,590 | 75.9% |

### 4.3 Synthetic case provenance breakdown

| Provenance tag | Count | Type |
|---|---|---|
| `no_discrepancy` | 31,625 | NONE — natural baseline |
| `natural_omission` | 18,554 | OMISSION — genuine Synthea medication gaps |
| `natural_duplication` | 3,607 | DUPLICATION — genuine Synthea duplicate codes |
| `artificial_duplication` | 11,851 | DUPLICATION — artificial fallback |

> Natural cases: 22,161 of 34,012 positive cases (65.2%). All OMISSION cases are natural.
> Only DUPLICATION has a substantial artificial component (11,851 of 15,458 = 76.7%).

---

## 5. Discrepancy Detection Labels (Rule Engine)

Separate from the ML binary target, the Rule Engine (`src/rules/discrepancy_engine.py`) produces explicit discrepancy flags per medication pair:

| Flag | Type | `verification_required` |
|---|---|---|
| `POTENTIAL_OMISSION` | A pre-admission medication is absent from the admission list | Always `true` |
| `POTENTIAL_DUPLICATION` | Duplicate or near-duplicate medication detected | Always `true` |
| `UNRESOLVED_MEDICATION_MATCH` | Cannot determine match status (data incomplete) | Always `true` |

These flags are deterministic outputs of the rule engine — not ML predictions. They are always returned with `verification_required: true` because pharmacist confirmation is mandatory.

---

## 6. Validation Separation

| Layer | Label type | Clinical validity |
|---|---|---|
| ML model `has_discrepancy` | Controlled synthetic target (labels-3.0.0) | None — synthetic only |
| Rule engine flags | Deterministic structural comparison | None — synthetic source data |
| Software tests | Assert code behavior, not clinical outcomes | N/A — software correctness only |

---

## 7. Definition of Done (labels-3.0.0)

- [x] `has_discrepancy` column in `data/processed/model_ready.csv` derived from structural gap detection, no downsampling
- [x] `data/processed/synthetic_cases.csv` contains `provenance`, `label_version`, `generation_seed` columns
- [x] DOSE/FREQ/ROUTE types disabled in `configs/discrepancy_rules.json`
- [x] FORBIDDEN_FEATURES excluded from inference via `InferenceGuard` + `models/feature_manifest.json`
- [x] Label strategy documented in this file and `docs/DECISION_LOG.md` (LBL-001, LBL-002, LBL-003)
- [x] No post-admission data in any label input
- [x] `tests/test_labels.py` — tests validating provenance, natural omission, duplication detection, schema fields
- [x] Encounter-level positive rate = 76.3% (documented — high prevalence is expected, not a bug)
