# Data Dictionary — PrioMed-Rec

**Version:** 0.1.0  
**Source:** Synthea Synthetic EHR (verified via `data/interim/dqi_report.json`)  
**Maintained by:** See `docs/data_provenance.md`

> ⚠️ This dictionary reflects **actual columns** verified from the CSV files, not assumed schema. Do not add columns here without re-running the data audit.

---

## Table of Contents

1. [patients.csv](#1-patientscsv)
2. [encounters.csv](#2-encounterscsv)
3. [medications.csv](#3-medicationscsv)
4. [medication_requests.csv](#4-medication_requestscsv)
5. [medication_administrations.csv](#5-medication_administrationscsv)
6. [conditions.csv](#6-conditionscsv)
7. [allergies.csv](#7-allergiescsv)
8. [primedrec_master.csv](#8-primedrec_mastercsv)
9. [primedrec_risk_features.csv](#9-primedrec_risk_featurescsv)
10. [validation_report.csv](#10-validation_reportcsv)

---

## 1. `patients.csv`

**Rows:** 17,286 | **Role:** Patient master registry

| Column | Type | Nullable | Null Rate | Notes |
|---|---|---|---|---|
| `patient_id` | string (UUID) | No | 0% | Primary key |
| `patient_name` | string | No | 0% | Synthetic name |
| `gender` | string | No | 0% | Values: `M`, `F` |
| `birth_date` | string (ISO date) | No | 0% | Format: `YYYY-MM-DD` |
| `deceased_date` | string (ISO date) | Yes | **86.8%** | Null = alive |
| `marital_status` | string | No | 0% | Synthetic category |

**DQI Notes:**
- `deceased_date` is intentionally sparse (86.8% null = living patients). Expected.

---

## 2. `encounters.csv`

**Rows:** 488,422 | **Role:** All clinical encounters

| Column | Type | Nullable | Null Rate | Notes |
|---|---|---|---|---|
| `encounter_id` | string (UUID) | No | 0% | Primary key |
| `patient_id` | string (UUID) | No | 0% | FK → patients |
| `encounter_start` | string (ISO datetime) | No | 0% | |
| `encounter_end` | string (ISO datetime) | No | 0% | |
| `encounter_class` | string | No | 0% | FHIR codes: `AMB`, `IMP`, `EMER`, `HH`, `VR` |
| `encounter_class_display` | string | Yes | **100%** | ⚠️ DQI-003: Entirely empty — do not use |
| `encounter_type` | string | No | 0% | Textual description of encounter type |
| `encounter_type_code` | string | No | 0% | SNOMED code |
| `reason` | string | Yes | **36.6%** | Optional reason for encounter |

**DQI Notes:**
- `encounter_class_display` is 100% null — use `encounter_class` (FHIR code) directly.
- `reason` null rate 36.6% is clinically expected; encounters without explicit reason are valid.

---

## 3. `medications.csv`

**Rows:** 319,329 | **Role:** Reference table for medication lookup (not event data)

| Column | Type | Nullable | Null Rate | Notes |
|---|---|---|---|---|
| `medication_id` | string (UUID) | No | 0% | Primary key |
| `medication_name` | string | No | 0% | Medication display name |
| `medication_code` | string | No | 0% | RxNorm code |
| `medication_system` | string | No | 0% | Coding system URI |

**DQI Notes:**
- This is a **reference table**, not an event table. Row count (319,329) reflects unique medication entries, not prescriptions.

---

## 4. `medication_requests.csv`

**Rows:** 885,606 | **Role:** All medication prescriptions/orders

| Column | Type | Nullable | Null Rate | Notes |
|---|---|---|---|---|
| `medication_request_id` | string (UUID) | No | 0% | Primary key |
| `patient_id` | string (UUID) | No | 0% | FK → patients ✅ |
| `encounter_id` | string (UUID) | No | 0% | FK → encounters ⚠️ |
| `medication_name` | string | Yes | **36.1%** | ⚠️ DQI-004: Null for ~319K rows — use `medication_code` for these |
| `medication_code` | string | Yes | **36.1%** | Same rows as medication_name null |
| `medication_system` | string | Yes | **36.1%** | Same rows |
| `dose_value` | float | Yes | **67.5%** | ⚠️ DQI-005: High null rate |
| `dose_unit` | string | Yes | **100%** | ⚠️ DQI-005: Entirely empty in this dataset |
| `frequency` | string | Yes | **100%** | ⚠️ DQI-005: Entirely empty |
| `timing_text` | string | Yes | **100%** | ⚠️ DQI-005: Entirely empty |
| `route` | string | Yes | **100%** | ⚠️ DQI-005: Entirely empty |
| `status` | string | No | 0% | FHIR status: `active`, `completed`, `stopped`, etc. |
| `intent` | string | No | 0% | FHIR intent: `order`, `proposal`, etc. |
| `authored_on` | string (ISO datetime) | No | 0% | Date prescription was written |

**DQI Notes:**
- **DQI-004:** 36.1% of rows have null `medication_name/code/system` — these correspond to rows where the medication reference uses an internal UUID. Join to `medications.csv` via `encounter_id` if needed.
- **DQI-005:** `dose_unit`, `frequency`, `timing_text`, `route` are 100% null. Dose/frequency/route-level discrepancy checks **cannot be performed** from this table — use `medication_administrations.csv` where available.
- **DQI-006 (RI):** 50.9% of `encounter_id` values (450,480 rows) do not match any `encounter_id` in `encounters.csv`. Decision: see `DECISION_LOG.md` DQI-006.

---

## 5. `medication_administrations.csv`

**Rows:** 319,329 | **Role:** Actual medication administration events

| Column | Type | Nullable | Null Rate | Notes |
|---|---|---|---|---|
| `medication_administration_id` | string (UUID) | No | 0% | Primary key |
| `patient_id` | string (UUID) | No | 0% | FK → patients ✅ |
| `encounter_id` | string (UUID) | No | 0% | FK → encounters |
| `medication_name` | string | No | 0% | Full medication display name |
| `medication_code` | string | No | 0% | RxNorm code |
| `effective_datetime` | string (ISO datetime) | No | 0% | When medication was given |
| `dose_value` | float | Yes | **98.9%** | Nearly entirely empty |
| `dose_unit` | string | Yes | **100%** | Entirely empty |
| `route` | string | Yes | **100%** | Entirely empty |
| `status` | string | No | 0% | FHIR status |

**DQI Notes:**
- `dose_value` (98.9% null) and `dose_unit`/`route` (100% null) mean dose-level reconciliation from administration records is not feasible in this dataset.
- `medication_name` and `medication_code` are fully populated — **this table is the primary source for medication identity matching**.

---

## 6. `conditions.csv`

**Rows:** 631,452 | **Role:** Clinical diagnoses

| Column | Type | Nullable | Null Rate | Notes |
|---|---|---|---|---|
| `condition_id` | string (UUID) | No | 0% | Primary key |
| `patient_id` | string (UUID) | No | 0% | FK → patients ✅ |
| `encounter_id` | string (UUID) | No | 0% | FK → encounters |
| `condition_name` | string | No | 0% | SNOMED display name |
| `condition_code` | string | No | 0% | SNOMED code |
| `onset_date` | string (ISO date) | No | 0% | |
| `clinical_status` | string | No | 0% | `active`, `resolved`, etc. |
| `verification_status` | string | No | 0% | `confirmed`, `unconfirmed`, etc. |

**DQI Notes:**
- All columns fully populated. No DQI issues.

---

## 7. `allergies.csv`

**Rows:** 15,802 | **Role:** Patient allergy records

| Column | Type | Nullable | Null Rate | Notes |
|---|---|---|---|---|
| `allergy_id` | string (UUID) | No | 0% | Primary key |
| `patient_id` | string (UUID) | Yes | **100%** | ⚠️ DQI-001: All null — see decision below |
| `allergy_name` | string | No | 0% | |
| `allergy_code` | string | No | 0% | |
| `clinical_status` | string | No | 0% | |
| `verification_status` | string | No | 0% | |

**DQI Notes:**
- **DQI-001 (CRITICAL):** `patient_id` is 100% null (15,802/15,802 rows). This table **cannot be joined to patients**. Decision: see `DECISION_LOG.md` DQI-001. Allergy features are excluded from the feature matrix unless a reliable patient linkage is recovered.

---

## 8. `primedrec_master.csv`

**Rows:** 488,422 | **Role:** Pre-computed admission-level dataset (1 row per encounter)

| Column | Type | Nullable | Null Rate | Canonical? | Notes |
|---|---|---|---|---|---|
| `encounter_id` | string (UUID) | No | 0% | ✅ | Primary key |
| `patient_id` | string (UUID) | No | 0% | ✅ | |
| `encounter_start_x` | string | No | 0% | ✅ **USE THIS** | From risk_features join (left side) |
| `encounter_start_y` | string | No | 0% | ❌ discard | Duplicate from encounters join (right side) |
| `birth_date_x` | string | No | 0% | ✅ **USE THIS** | From risk_features join |
| `birth_date_y` | string | No | 0% | ❌ discard | From patients join |
| `age` | float | No | 0% | ✅ | Age at encounter |
| `age_65_plus` | int | No | 0% | ✅ | Binary flag |
| `medication_count` | int | No | 0% | ✅ | |
| `polypharmacy` | int | No | 0% | ✅ | Binary (medication_count >= 5) |
| `high_alert_medication` | int | No | 0% | ✅ | Binary flag |
| `encounter_end` | string | No | 0% | ✅ | |
| `encounter_class` | string | No | 0% | ✅ | FHIR code |
| `encounter_class_display` | string | Yes | **100%** | ❌ discard | All null — same as encounters.csv |
| `encounter_type` | string | No | 0% | ✅ | |
| `encounter_type_code` | string | No | 0% | ✅ | |
| `reason` | string | Yes | 36.6% | ✅ | Optional |
| `gender` | string | No | 0% | ✅ | |
| `deceased_date` | string | Yes | 69.6% | ✅ | |

**DQI Notes:**
- **DQI-002:** Duplicate column pairs: `encounter_start_x/y` and `birth_date_x/y`. Canonical choice: use `_x` variants (from the left join side, originating from `primedrec_risk_features`).
- `encounter_class_display` is 100% null — same root issue as `encounters.csv`.

---

## 9. `primedrec_risk_features.csv`

**Rows:** 488,422 | **Role:** Baseline feature matrix (9 features only)

| Column | Type | Nullable | Null Rate | Notes |
|---|---|---|---|---|
| `encounter_id` | string (UUID) | No | 0% | Primary key |
| `patient_id` | string (UUID) | No | 0% | |
| `encounter_start` | string | No | 0% | |
| `birth_date` | string | No | 0% | |
| `age` | float | No | 0% | |
| `age_65_plus` | int | No | 0% | Binary flag |
| `medication_count` | int | No | 0% | |
| `polypharmacy` | int | No | 0% | Binary |
| `high_alert_medication` | int | No | 0% | Binary |

**DQI Notes:**
- All columns fully populated. Only 9 base features — Sub-Task 4 will expand this significantly.

---

## 10. `validation_report.csv`

**Rows:** 1 | **Role:** Pre-computed validation summary from data generation

| Column | Value | Notes |
|---|---|---|
| `expected_patients` | 17,286 | |
| `patient_rows` | 17,286 | Matches |
| `unique_patients` | 17,286 | No duplicates |
| `encounter_rows` | 488,422 | |
| `unique_encounters` | 488,422 | No duplicates |
| `medication_request_rows` | 885,606 | |
| `medication_administration_rows` | 319,329 | |
| `condition_rows` | 631,452 | |
| `allergy_rows` | 15,802 | |
| `observation_rows` | 9,129,492 | File excluded from repo (too large) |
| `parser_errors` | **0** | ✅ |

---

## Canonical Column Decisions Summary

| Issue | Table | Decision |
|---|---|---|
| `encounter_class_display` all null | encounters, primedrec_master | Do not use. Use `encounter_class` (FHIR code). |
| `allergies.patient_id` all null | allergies | Exclude allergy join. Flag DQI-001. |
| `medication_requests` dose/route/freq all null | medication_requests | Use `medication_administrations` for identity matching. |
| `primedrec_master` duplicate cols | primedrec_master | Use `_x` variants. Drop `_y`. |
| `medication_requests.encounter_id` 50.9% orphan | medication_requests | Filter to matched encounters only. Flag DQI-006. |
