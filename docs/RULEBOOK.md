# RULEBOOK — PrioMed-Rec Discrepancy Engine

**Rule version:** `rules-0.1.0`  
**Config source:** `configs/discrepancy_rules.json`  
**Engine:** `src/rules/discrepancy_engine.py`

> All rules are **deterministic** and **configuration-driven**. Changing rule parameters requires incrementing `rule_version`. Every flag carries `verification_required: true` — pharmacist confirmation is mandatory before any clinical action.

---

## Normalization Policy

| Priority | Key | Rule |
|---|---|---|
| 1 (primary) | `medication_code` | RxNorm or equivalent coding-system code. Use as-is if non-null and non-empty. |
| 2 (fallback) | `normalized_name` | Lowercase stripped medication name with dosage strings removed. |
| Unresolved | `UNRESOLVED_MEDICATION_MATCH` | Raised when both code and name are null/empty. Requires pharmacist resolution. |

Canonical source: `src/rules/medication_normalizer.py`

---

## Rule Definitions

### R1 — POTENTIAL_OMISSION

| Property | Value |
|---|---|
| **rule_id** | `potential_omission.rules-0.1.0` |
| **Enabled** | `true` |
| **Description** | A medication present in the pre-admission list is absent from the admission list. |
| **Detection logic** | `norm_key ∈ pre_admission_keys` AND `norm_key ∉ admission_keys` |
| **Active status filter** | Only `status NOT IN ('completed', 'stopped')` are checked |
| **Severity** | `REVIEW` |
| **Clinical interpretation** | Potential omission — may be intentional (clinical decision) or an oversight. **Pharmacist must verify.** |
| **False positive risk** | Deliberate clinical discontinuation; medication substituted with equivalent |
| **Data constraints** | Requires `medication_code` or `medication_name` to be non-null |

---

### R2 — POTENTIAL_DUPLICATION

| Property | Value |
|---|---|
| **rule_id** | `potential_duplication.rules-0.1.0` |
| **Enabled** | `true` |
| **Description** | The same medication (by `norm_key`) appears more than once in the admission list. |
| **Detection logic** | `count(norm_key in admission_list) > 1` |
| **Severity** | `REVIEW` |
| **Clinical interpretation** | Potential therapeutic duplication. May be same drug via different routes, different formulations, or an ordering error. **Pharmacist must verify.** |
| **False positive risk** | Same medication ordered via different routes (e.g. oral + IV) — clinically valid |

---

### R3 — POTENTIAL_DOSE_MISMATCH

| Property | Value |
|---|---|
| **rule_id** | `potential_dose_mismatch.rules-0.1.0` |
| **Enabled** | `false` — **disabled** |
| **Reason disabled** | `dose_value` and `dose_unit` are 100% null in `medication_requests.csv` (DQI-005). No dose data available in this dataset. |
| **Restoration condition** | Re-enable when a data source with populated dose fields is available. Set `enabled: true` and increment `rule_version`. |

---

### R4 — POTENTIAL_FREQUENCY_MISMATCH

| Property | Value |
|---|---|
| **Enabled** | `false` — **disabled** |
| **Reason** | `frequency` and `timing_text` 100% null (DQI-005). |

---

### R5 — POTENTIAL_ROUTE_MISMATCH

| Property | Value |
|---|---|
| **Enabled** | `false` — **disabled** |
| **Reason** | `route` 100% null in `medication_requests.csv` (DQI-005). |

---

### UNRESOLVED_MEDICATION_MATCH

Not a rule — raised by the normalizer when a medication cannot be safely identified. Triggers pharmacist review for that medication.

---

## Output Contract

Every flag in the output follows this schema (PROJECT_CONTEXT §14):

```json
{
  "flag_type": "POTENTIAL_OMISSION",
  "severity": "REVIEW",
  "medication_code": "12345",
  "medication_name": "Warfarin 5mg",
  "pre_admission_detail": {"dose_value": null, "route": null, "frequency": null, "status": "active"},
  "admission_detail": null,
  "evidence": "Medication present in pre-admission list but absent from admission list.",
  "verification_required": true,
  "rule_id": "potential_omission.rules-0.1.0"
}
```

**`verification_required: true` is mandatory on every flag.** This ensures the system is never interpreted as making a definitive clinical determination.

---

## Versioning Policy

| When to increment | How |
|---|---|
| Any rule logic change | Increment `rule_version` in `configs/discrepancy_rules.json` |
| Enable/disable a rule | Increment version + add to DECISION_LOG.md |
| Add a new rule | Increment version + add section to this RULEBOOK |
| Normalization logic change | Increment version |

---

## Rule Baseline Performance

The rule engine is used as a **transparent baseline classifier** in comparison with ML models. See `models/eval_report.json` and `docs/evaluation_protocol.md` for comparative metrics.
