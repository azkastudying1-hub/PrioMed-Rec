# Data layout and governance

This repository uses the following operational data contract:

| Location | Purpose | Used by live website/API |
|---|---|---|
| `raw/synthea/` | Synthetic source EHR extracts | Training / reproducibility only |
| `interim/` | Derived cohorts and medication timelines | Pipeline only |
| `processed/model_ready.csv` | Legacy API model training matrix | Model development / audit |
| `processed/feature_matrix.csv` | Feature-engineering output | Model development / audit |
| `drug_risk_lookup.csv` | Curated safety-reference lookup | Yes |
| `priomed.db` | Local development database | Yes locally; use `/app/runtime` under Docker |

`medrec_xgboost/data/` is intentionally isolated because it has a different, admission-time MedRec schema. It is not automatically consumed by the live API yet. A schema adapter and a locally validated trained artefact are required before replacing the legacy API model.

The unreferenced UCI Diabetes source dataset is retained at `_archive/data_legacy/` rather than mixed with the active MedRec data contract.

## Quality rules

- Never place personal identifiers or real patient data in this repository.
- Preserve raw data as read-only input; create derived outputs in `interim/` or `processed/`.
- Run `python scripts/validate_data_layout.py` before training or deployment to identify missing required files and accidental mixed artefacts.
- Keep label creation, temporal split, calibration, and final test evaluation separate to avoid leakage.
