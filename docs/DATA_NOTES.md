# DATA_NOTES.md — Reference Data Curation Methodology

**Document version:** 1.0  
**Last updated:** 2025  
**Scope:** `data/drug_risk_lookup.csv` and `knowledge/interactions.json`

---

## 1. Purpose

This document records **how** each row in the safety reference files was derived,
so that any reviewer (mentor, auditor, future developer) can trace every flag back
to a publicly documented, verifiable source.

PrioMed-Rec is a *clinical decision support* tool, not a medical database. The lookup
tables serve as guardrails for the rule engine — they help surface candidates for
pharmacist review, never replace it.

---

## 2. `data/drug_risk_lookup.csv`

### 2.1 Schema

| Column | Type | Description |
|--------|------|-------------|
| `drug_name` | string | Lower-case generic/INN drug name (English) |
| `high_alert` | 0/1 | ISMP High-Alert classification |
| `nti` | 0/1 | FDA Narrow Therapeutic Index classification |
| `beers_pim` | 0/1 | AGS Beers Criteria PIM for adults ≥ 65 |
| `category` | string | Pharmacological/clinical category (from ISMP) |
| `route` | string | Typical route(s) referenced in source |
| `source` | string | Concatenated source identifiers |

### 2.2 Source documents

| Identifier | Full title | Year | Public URL |
|------------|-----------|------|-----------|
| `ISMP_2024` | ISMP High-Alert Medications in Acute Care Settings | 2024 | https://www.ismp.org/recommendations/high-alert-medications-acute-list |
| `FDA_NTI` | FDA Pharmacometric Approach to Define Narrow Therapeutic Index Drugs | 2024 | https://www.fda.gov/drugs/drug-approvals-and-databases/narrow-therapeutic-index-drugs |
| `AGS_BEERS_2023` | 2023 American Geriatrics Society Beers Criteria® | 2023 | https://doi.org/10.1111/jgs.18372 |

### 2.3 Curation method — hardcoded from public summaries

The lookup rows were **not** programmatically extracted from the ISMP PDF or the AGS
journal article (both require separate access/licensing to redistribute). Instead:

1. **ISMP High-Alert (2024):** Drug categories and representative examples were transcribed
   manually from the publicly accessible ISMP website listing
   (`ismp.org/recommendations/high-alert-medications-acute-list`).
   Each drug was assigned `high_alert=1` if its category is on the acute-care list.

2. **FDA NTI:** Drug names were taken from the FDA's publicly available NTI guidance
   summary page. Each drug was assigned `nti=1`.

3. **AGS Beers Criteria (2023):** `beers_pim=1` was assigned based on public-domain
   summaries of the Beers Criteria (AHRQ public summary, Wikipedia synthesis, and
   open-access review articles). The journal article itself (DOI: 10.1111/jgs.18372)
   is behind a paywall; **the full text was not used as a data source**.

   > ⚠️ **License note:** The AGS Beers Criteria is a clinical guideline published by
   > the American Geriatrics Society. The naskah lengkap (full text) is copyrighted by
   > AGS / Wiley. This project does **not** reproduce table content from that article.
   > The `beers_pim` flags reflect the public-domain summary, not verbatim article data.

4. **Deduplication:** Where a drug appeared in multiple sources (e.g., warfarin appears
   in both ISMP and FDA NTI), a single row was kept with all applicable flags set to 1.

5. **Encoding:** All drug names stored as lower-case INN/generic names (English), matching
   the normalisation output of `src/rules/medication_normalizer.py`.

### 2.4 Completeness limitation

The lookup covers **114 high-priority drug names**. It is intentionally narrow:
only drugs with clear, publicly documented safety concern signals are included.
Drugs not in the lookup receive no flag — this is a *conservative* design.
The lookup is versioned as `drug_risk_lookup-v1.0`.

**Not covered:**
- Indonesian brand names (KFA mapping is Future Work)
- Pediatric dosing safety flags
- Renal/hepatic dose adjustment rules (Future Work, requires DQI improvement)
- Off-label indication assessment (out of scope per §1, [Wawancara])

---

## 3. `knowledge/interactions.json`

### 3.1 Schema

Each entry:
```json
{
  "pair": ["drug_a", "drug_b"],
  "severity": "MAJOR | MODERATE | MINOR",
  "mechanism": "...",
  "clinical_note": "...",
  "source": "...",
  "source_url": "...",
  "year": 2024,
  "status": "CANDIDATE"
}
```

### 3.2 Curation method

Ten drug-drug interactions were selected from:
- **Drugs.com Interactions Checker** (publicly accessible, referenced per-entry)
- **Medscape Drug Interaction Checker** (publicly accessible, referenced per-entry)
- **WHO Model Formulary 2023** open-access summaries

Criteria for inclusion:
1. Severity ≥ MODERATE per at least one reference source
2. Drug pair frequently seen together in hospital admission scenarios
3. Mechanism documented in at least one public-access source

All entries carry `"status": "CANDIDATE"` and `"verification_required": true` —
they are never presented to users as confirmed contraindications.

### 3.3 What the interaction KB is NOT

- It is not a comprehensive drug interaction database (that would be Micromedex / Lexicomp /
  clinical-pharmacology-grade products — out of scope for this project).
- It does not assess severity based on individual patient parameters (renal function,
  polymorphisms, etc.).
- The LLM layer is explicitly forbidden from extending or modifying interaction entries
  (principle 3 of the architecture contract).

---

## 4. Reproducibility

To regenerate `drug_risk_lookup.csv` from the same source list:

```bash
python -c "
from scripts.build_lookup import build_lookup_csv
build_lookup_csv('data/drug_risk_lookup.csv')
"
```

> The build script (`scripts/build_lookup.py`) encodes the same hardcoded lists
> documented in §2.3 above. It does not call any external API or scrape any website.

---

## 5. Update policy

| Trigger | Action |
|---------|--------|
| ISMP releases a new acute-care high-alert list | Manual review; update `high_alert` flags + bump `drug_risk_lookup` version |
| AGS Beers Criteria new edition (≈every 3 years) | Manual review of public summary; update `beers_pim` flags |
| FDA publishes new NTI guidance | Manual review; update `nti` flags |
| New drug added to hospital formulary | Add row manually with source citation |

All changes to `drug_risk_lookup.csv` must be accompanied by a commit message
referencing the source document and date of update.

---

*This document was authored as part of PrioMed-Rec project transparency and
reproducibility requirements. It is not a clinical reference document.*
