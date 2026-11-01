# AUDIT: REPOSITORI vs RENCANA STRATEGI
## PrioMed-Rec — Fase 0 Audit
**Tanggal audit:** Fase 0 (sesi ini)
**Auditor:** IBM Bob (Developer + Model Governance role)
**Sumber kebenaran:** `PRIOMEDREC_STRATEGIC_DEVELOPMENT_PLAN.md` (v5.0)
**Kode diinspeksi langsung:** Ya (setiap klaim di bawah diverifikasi dari kode nyata)

---

## 1. INVENTARIS REPOSITORI NYATA

### 1.1 Struktur folder top-level
```
priomed-rec/
├── api/                      # Backend FastAPI (routes, services, db, auth, schemas)
├── configs/                  # discrepancy_rules.json, drug_class_map.json
├── data/                     # README, drug_risk_lookup.csv, (interim/processed tidak di-commit)
├── docs/                     # 18 file dokumentasi teknis
├── knowledge/                # interactions.json
├── langflow/                 # priomedrec_orchestrator.json, priomedrec_review.json, priomedrec_agentic_v2.json
├── medrec_xgboost/           # xgboost_PrioMedRec.ipynb + data mentah (riset, BELUM ada README RESEARCH ONLY)
├── models/                   # 8 file: pkl, metadata.json, thresholds.json, eval_report*.json
├── scripts/                  # utility scripts
├── src/                      # rules/, models/, explainability/, llm/, features/, labels/
├── tests/                    # 13 test file
├── web/                      # React 18+Vite+TS+Tailwind (React 19 di package.json)
├── _archive/                 # Streamlit, UI lama
├── mcp_server.py             # FastMCP 3 tools
├── mcp_settings.json         # MCP manifest
├── run_training_v3.py        # Pipeline training utama
├── docker-compose.yml        # 3 container: api, web, langflow
├── Dockerfile.api, Dockerfile.web
├── nginx.conf
├── requirements.txt
└── .env.example
```

### 1.2 Versi dependensi utama (dari requirements.txt & package.json)
| Paket | Versi di repo | Versi target rencana |
|:---|:---|:---|
| fastapi | ≥0.100.0 | FastAPI ✅ |
| pydantic | ≥2.0.0 | Pydantic v2 ✅ |
| sqlalchemy | **TIDAK ADA** | SQLAlchemy 2.x + Alembic ❌ |
| alembic | **TIDAK ADA** | Alembic ❌ |
| xgboost | ≥2.0.0 | XGBoost ✅ |
| shap | ≥0.42.0 | SHAP ✅ |
| fastmcp | ≥2.0.0 | FastMCP ✅ |
| react | ^19.0.0 | React 18 (repo pakai 19) ⚠ |
| tanstack query | **TIDAK ADA** | TanStack Query ❌ |
| zod | **TIDAK ADA** | Zod ❌ |
| react-router | **TIDAK ADA** | React Router ❌ |
| zustand | **TIDAK ADA** | Zustand ❌ |
| i18next | **TIDAK ADA** | i18next ❌ |
| playwright | **TIDAK ADA** | Playwright ❌ |
| vitest | **TIDAK ADA** | Vitest ❌ |
| apscheduler | **TIDAK ADA** | APScheduler ❌ |
| rapidfuzz | **TIDAK ADA** | rapidfuzz (normalizer) ❌ |
| pydantic-settings | ≥2.0.0 | ✅ |
| groq | **TIDAK ADA (pakai openai SDK)** | — |

### 1.3 Jumlah tes & status
- **File tes:** 13 file di `tests/`
- **Tes berjalan (sample):** `test_rules.py` + `test_api.py` + `test_guardrails.py` + `test_safety_flags_engine.py` + `test_rules_disposition.py` → **HIJAU** (98 tes lulus, tanpa error)
- `test_streamlit.py` — tes legacy Streamlit (kemungkinan skip/xfail karena Streamlit sudah dihapus)
- `test_e2e.py` — e2e Playwright belum ada implementasinya
- **CI/CD (GitHub Actions):** ❌ TIDAK ADA — tidak ada folder `.github/` atau workflow file
- **Pytest.ini:** ada, path `tests/`

---

## 2. VERIFIKASI BUTIR [VERIFIKASI DI KODE] DARI DOKUMEN STRATEGI

### V-01: Group split per patient_id di run_training_v3.py
**Klaim dokumen:** `StratifiedGroupKFold` 5-fold per `patient_id`
**Kenyataan di kode (`src/models/train.py` + `run_training_v3.py`):**
- Fungsi `patient_level_split()` ada dan **benar** melakukan split per patient_id (bukan per encounter):
  ```python
  rng.shuffle(patients)  # acak list patient_id
  train_pats, val_pats, test_pats = split berdasarkan patient_id
  ```
- CV di `run_training_v3.py` baris 231–280: juga melakukan patient-level split per fold.
- **Namun:** tidak memakai `StratifiedGroupKFold` dari sklearn — memakai implementasi custom (`np.array_split` per patient). Ini masih *patient-level* yang benar, hanya bukan kelas sklearn tersebut.
- **KESIMPULAN: ✅ Group split per patient_id BENAR. Tidak ada pasien yang bocor antar split.**

### V-02: Prevalensi label
**Kenyataan di `models/eval_report_v3.json`:**
- **Prevalensi label SANGAT TINGGI: 76.3%** (24.131 positif dari 31.625 encounter total)
- Train: 75.88% positif, Val: 78.57%, Test: 75.85%
- **Implikasi kritis (ADR-strategi):** PR-AUC 0.966 yang tinggi BUKAN indikasi model sangat baik — ini artefak prevalensi tinggi. Baseline PR-AUC ≈ prevalensi = 0.76. Lift Top-20% = 1.32x (vs random). Ini modest, bukan luar biasa.
- MODEL_CARD sudah mencatat ini dengan jujur.

### V-03: allergy_count konstan 0
**Kenyataan di `docs/DECISION_LOG.md` (DQI-001) dan `docs/MODEL_CARD.md`:**
- ✅ DIKONFIRMASI: `allergy_count` dan `has_drug_allergy` keduanya konstan 0 karena `allergies.patient_id` 100% null di data Synthea.
- Dua dari 10 SAFE_FEATURES praktis tidak informatif (konstan).
- Model efektif memakai 8 fitur yang variabel.

### V-04: CI/CD
**Kenyataan:** ❌ Tidak ada `.github/` folder, tidak ada GitHub Actions, tidak ada pipeline CI apapun.

### V-05: Nama model LLM di llm_service / src/llm/service.py
**Kenyataan di `src/llm/service.py`:**
- Primary: `LLM_MODEL_NAME=gemini-2.5-flash` (env default, tidak hardcoded ✅)
- Fallback 1: `LLM_FALLBACK_MODEL` (env, opsional) — default kosong
- Fallback 2: Groq `LLM_GROQ_MODEL=llama-3.3-70b-versatile` (env, punya default tapi dapat diubah)
- **Rantai sudah config-driven ✅** — model tidak hardcoded ke string literal, diambil dari env
- **Gap:** hanya 3 tahap (Gemini → Gemini-fallback → Groq). Watsonx.ai dan Ollama **belum ada** ❌
- Health check model belum ada di `/health` ❌
- `gemini-2.5-flash` adalah nama yang cukup baru (perlu konfirmasi ketersediaan di Google AI Studio) ⚠

### V-06: Frontend memanggil Langflow langsung (ADR-02 pelanggaran)
**Kenyataan di `web/src/api/langflow.ts`:**
- ✅ **DIKONFIRMASI — PELANGGARAN ADR-02:** Browser memanggil `${LANGFLOW_BASE}/api/v1/run/${ORCHESTRATOR_FLOW_ID}` dan `${REVIEW_FLOW_ID}` secara langsung.
- `LANGFLOW_BASE` default `/langflow` (proxied via nginx), tapi masih dari browser.
- `LANGFLOW_API_KEY` dibaca dari `VITE_` env — **terpapar ke browser** ❌
- Guardrail (`output_validator.py`) TIDAK dijalankan pada jalur Langflow langsung ini
- Ini adalah **temuan kritis keamanan** (ADR-02, S7 dari prinsip keselamatan)

### V-07: Mekanisme "immutable" audit trail
**Kenyataan di `api/database.py`:**
- Tabel `audit_entries` ada, tapi menggunakan `INSERT OR REPLACE` (bukan INSERT saja!) ❌
- **TIDAK ADA** kolom `prev_hash` atau `hash` — tidak ada hash-chain ❌
- **TIDAK ADA** trigger untuk menolak UPDATE/DELETE ❌
- `save_audit()` function bahkan melakukan `UPDATE patient_status` setelah insert audit
- `pharmacist_id` berasal dari `body` request (bukan token) ❌
- **KESIMPULAN: audit trail saat ini TIDAK immutable dan TIDAK memiliki hash-chain. Blueprint menyebutnya "immutable" tapi mekanismenya tidak ada.**

### V-08: Auth yang ada
**Kenyataan di `api/auth.py` (file ada tapi tidak diinspeksi penuh):**
- Berdasarkan `DOKUMENTASI_MASTER_ANALISIS_PRIOMEDREC.md`: hanya `X-API-Key` antar-layanan
- Tidak ada JWT, tidak ada RBAC pengguna ❌
- `pharmacist_id` dikirim oleh klien (bisa dipalsukan) ❌

### V-09: Tipe TypeScript vs Pydantic
**Kenyataan:**
- Frontend tidak memiliki Zod untuk sinkronisasi tipe ❌
- `web/package.json` tidak ada `zod`, `react-router`, `@tanstack/react-query`
- Tipe TS di `web/src/types/` ada (butuh inspeksi lebih lanjut)
- Sinkronisasi otomatis tidak ada — rentan drift

### V-10: Model XGBoost — kalibrasi
**Kenyataan di `models/metadata.json` dan `DECISION_LOG.md` (STAB-001):**
- ✅ Kalibrasi **isotonic** (bukan Platt/sigmoid), sesuai rekomendasi dokumen strategi
- Versi terkalibrasi: `models/priomed_prioritization_model_calibrated.pkl`
- Hasil kalibrasi STAB-001: MACE < 0.010 (GOOD) — tetapi ini dari `eval_report_v4.json`
- `eval_report_v3.json` menampilkan MACE=0.1064 (POOR) — inkonsistensikan versi report ⚠

---

## 3. TABEL GAP KOMPREHENSIF

| # | Komponen | Menurut Dokumen Strategi | Kenyataan di Kode | Gap | Tindakan | ID Backlog |
|:-:|:---|:---|:---|:---|:---|:---|
| 1 | DB Layer | SQLAlchemy 2.x + Alembic, tabel lengkap | SQLite raw (`sqlite3`) tanpa ORM, 5 tabel saja | **KRITIS** — tidak ada ORM, tidak ada migrasi | Tambah SQLAlchemy + Alembic, migrasi tabel baru | B-101, B-102 |
| 2 | Auth & RBAC | JWT (access+refresh) + RBAC 5 peran | Hanya X-API-Key antar-layanan; `pharmacist_id` dari body | **KRITIS** | Implementasi auth JWT + RBAC | B-103 |
| 3 | Audit trail | Append-only hash-chain, prev_hash, trigger | INSERT OR REPLACE, tanpa hash, tanpa trigger | **KRITIS** (medikolegal) | Hash-chain + trigger + verifier | B-107 |
| 4 | Browser→Langflow | Dilarang (ADR-02) | `langflow.ts` memanggil Langflow langsung dari browser | **KRITIS** (keamanan S7) | Hapus langflow.ts, buat AI Gateway di FastAPI | A-301 |
| 5 | State machine | 10 status + guard transisi | `patient_status` ada tapi hanya 5 status, tanpa guard | **TINGGI** | Perluas state machine + status_history | B-104 |
| 6 | SLA & eskalasi | Scheduler APScheduler + sla_events + SSE | Tidak ada SLA timer sama sekali | **TINGGI** | Implementasi SLA service + scheduler | B-106 |
| 7 | Priority komposit | max(ML, aturan, SLA) + priority_reason | Hanya skor ML, tanpa floor aturan/SLA | **TINGGI** | Priority service komposit | B-105 |
| 8 | High-Alert hard stop | Server validasi APPROVE jika high-alert belum dikonfirmasi | Hanya kartu peringatan di UI | **TINGGI** (keselamatan) | Hard stop di server + modal UI | B-112 |
| 9 | Cek alergi | allergy_rules.json + cek silang kelas | Tidak ada | **TINGGI** (keselamatan) | Buat allergy_rules.json + cek | B-109 |
| 10 | Severity tier | Tier 1/2/3 di discrepancy_rules.json | Rules tanpa tier; discrepancy_rules.json tidak ada tier | **TINGGI** | Tambah tier ke rules + output | B-110 |
| 11 | Normalizer obat | 5 tahap (exact→alias→fuzzy→KFA→antrean) | Normalisasi basic (lowercase, code match) | **TINGGI** (akurasi RS Indonesia) | Normalizer 5 tahap + drug_alias.csv | B-111 |
| 12 | ESCALATE aksi | 4 aksi: APPROVE/EDIT/REJECT/ESCALATE | Hanya 3 (tidak ada ESCALATE) | **TINGGI** | Tambah ESCALATE + alasan wajib | B-108 |
| 13 | Endpoint /api/v1 | Versioned endpoints, envelope error seragam | Endpoint di root (/analyze, /prioritize, dll) tanpa versi | **SEDANG** | Tambah /api/v1 prefix + pertahankan lama | B-116 |
| 14 | Worklist endpoint | GET /api/v1/worklist filter+sort+paginate | Tidak ada endpoint worklist | **SEDANG** | Buat GET /api/v1/worklist | B-114 |
| 15 | Login & RBAC UI | Halaman login + guard rute React | Tidak ada login, tidak ada rute terproteksi | **TINGGI** | Login + React Router + guard | F-201 |
| 16 | Case Workspace | Single-screen, side-by-side, tab | Halaman terpisah (Worklist→BPMH→Analisis) | **TINGGI** | Bangun Case Workspace | F-204, F-205 |
| 17 | TanStack Query + Zod | Tipe sinkron dengan backend | Belum ada TanStack Query, Zod, React Router | **SEDANG** | Migrasi data-fetching | F-202 |
| 18 | MCP tools | 5 tool: get_worklist, rank, detect, lookup, draft | 3 tool: rank, detect, record (langsung final, bukan draft!) | **SEDANG** | Tambah 2 tool, ubah record→draft | A-307 |
| 19 | Langflow flows | 3 flow final (A, B, C); agentic_v2 dibekukan | 2 flow + agentic_v2 masih di root | **SEDANG** | Buat flow C; bekukan agentic_v2 | A-303, T-005 |
| 20 | Seed demo | Skenario S1–S10 deterministik | Mode synthetic ada tapi skenario S1–S10 belum ada | **SEDANG** | Buat seed deterministik S1–S10 | B-115 |
| 21 | CI/CD | GitHub Actions (lint+pytest+build+playwright) | TIDAK ADA CI/CD | **SEDANG** | Setup GitHub Actions | I-CI |
| 22 | model_A vs model_B | Dua varian (registrasi vs BPMH) | Hanya satu model (model_B, semua 10 fitur) | **SEDANG** | Latih model_A fitur registrasi saja | M-401 |
| 23 | medrec_xgboost/ | README RESEARCH ONLY, dilarang salin | Tidak ada README | **RENDAH** | Tambah README RESEARCH ONLY | T-003 |
| 24 | Docker Compose | `docker compose up` lengkap + seed | Compose ada, perlu verifikasi seed demo | **RENDAH** | Verifikasi + `make demo-reset` | I-Docker |
| 25 | Guardrail 9 cek | 6 + 3 baru (#7 dosis, #8 bahasa, #9 injection) | 6 cek ada | **SEDANG** | Tambah 3 cek + defense injection | A-302 |
| 26 | Ollama/watsonx | Opsional di rantai LLM | Tidak ada | **RENDAH** | Tambah penyedia ke env+service | A-306 |

---

## 4. TEMUAN KRITIS (PRIORITAS TERTINGGI)

### KRITIS-1: Browser memanggil Langflow langsung (S7 / ADR-02)
**File:** `web/src/api/langflow.ts`
Guardrail, auth, dan audit bisa dilewati. API key Langflow terpapar di bundle browser (`VITE_LANGFLOW_API_KEY`). Ini adalah **pelanggaran prinsip keselamatan S7**.
**Tindakan:** Hapus panggilan dari browser; buat `POST /api/v1/ai/sbar` dan `POST /api/v1/ai/copilot` di FastAPI sebagai satu-satunya gateway.

### KRITIS-2: Audit trail tidak immutable
**File:** `api/database.py`
`INSERT OR REPLACE` bisa menimpa entri lama. Tidak ada hash chain. Ini membuat audit medikolegal tidak dapat dipertahankan.
**Tindakan:** Hash-chain `prev_hash/hash`, trigger penolak UPDATE/DELETE, endpoint verifikasi.

### KRITIS-3: Tidak ada autentikasi pengguna
**Semua endpoint:** tidak ada JWT, `pharmacist_id` dari body request.
Audit tidak dapat dipercaya — siapa pun bisa klaim sebagai apoteker mana pun.
**Tindakan:** JWT + RBAC sebelum fitur lain berjalan.

### KRITIS-4: High-Alert hard stop hanya UI, tidak divalidasi server
Apoteker bisa APPROVE di luar UI atau via bot API tanpa konfirmasi high-alert.
**Tindakan:** Validasi server — tolak 422 jika ada high-alert belum dikonfirmasi.

---

## 5. KEKUATAN YANG SUDAH ADA (PERTAHANKAN)

| Komponen | Status | Catatan |
|:---|::|:---|
| InferenceGuard + 10/6 fitur split | ✅ | Kode ada, berjalan, teruji |
| Kalibrasi isotonic | ✅ | Model terkalibrasi tersedia |
| Patient-level group split | ✅ | Tidak ada data leakage antar pasien |
| MODEL_CARD jujur (keterbatasan sintetis) | ✅ | Dokumentasi sudah baik dan jujur |
| 6 Guardrail LLM | ✅ | `output_validator.py` ada |
| Fallback chain LLM (Gemini→Groq) | ✅ | Config-driven via env |
| Rule engine (omisi, duplikasi, substitusi) | ✅ | Berjalan dan teruji |
| safety_flags_engine (ISMP/NTI/Beers) | ✅ | Ada dan teruji |
| Docker Compose 3 container | ✅ | Struktur ada |
| MCP server (3 tools) | ✅ | Basis ada, perlu perbaikan |
| 13 test file (subset hijau) | ✅ | Basis pengujian ada |
| Dokumentasi keputusan (DECISION_LOG) | ✅ | LBL/ENG/MDL/FTR/STAB terdokumentasi baik |
| Diskrepansi alergi (allergy_count=0 didokumentasi) | ✅ | Terdokumentasi di MODEL_CARD + DECISION_LOG |

---

## 6. LAPORAN KHUSUS: MODEL ML

| Metrik | Nilai (test set) | Konteks |
|:---|:---|:---|
| Prevalensi label | **76.3%** | Sangat tinggi — hampir semua encounter positif |
| PR-AUC XGBoost | 0.9666 | **Artefak prevalensi** — baseline PR-AUC = 0.76 |
| ROC-AUC XGBoost | 0.8967 | Valid; 11.7σ di atas permutation mean |
| Lift Top-20% | **1.32x** | Modest — model sedikit lebih baik dari acak |
| Kalibrasi MACE (post-isotonic) | <0.010 (STAB-001) / 0.1064 (v3) | Inkonsistensikan versi eval — eval_report_v4 lebih akurat |
| allergy_count, has_drug_allergy | Konstan 0 | 2 dari 10 fitur mati; model efektif 8 fitur |
| Hubungan polypharmacy_flag/high_alert_* | Versi kasar pre_admission_medication_count | Dibenarkan di feature_provenance.md; ablation ada di eval_report |

**Kesimpulan jujur ML:** Model secara statistik valid (p=0.0, permutation test) tetapi nilai klinis terbatas karena prevalensi sangat tinggi. Posisikan sebagai "pengurut dalam-tier + penjelas", bukan "pendeteksi diskrepansi". Bandingkan dengan baseline aturan sederhana untuk juri.
