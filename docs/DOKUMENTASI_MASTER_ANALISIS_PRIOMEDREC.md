# DOKUMENTASI MASTER & AUDIT KOMPREHENSIF SISTEM PRIOMED-REC
## Analisis Arsitektur End-to-End, Inventarisasi File & Folder, Alur Kerja Klinis, serta Panduan Roadmap Produksi

**Nama Proyek:** PrioMed-Rec (*AI-Powered Admission Medication Reconciliation Prioritization System*)  
**Versi Sistem:** 4.0.0 (Master Blueprint & Web-First Architecture)  
**Tanggal Audit & Penyusunan:** 28 Oktober 2026  
**Klasifikasi Sistem:** *Clinical Decision Support System (CDSS) — Non-Autonomous / Human-in-the-Loop*  
**Prinsip Inti:**
> **"AI decides WHO FIRST. Rules surface WHAT TO CHECK. Pharmacist decides WHAT TO DO."**  
> *(AI menentukan siapa yang diperiksa lebih dulu. Rules mendeteksi apa yang perlu dicek. Apoteker menentukan keputusan klinis akhir.)*

---

## DAFTAR ISI

1. [EXECUTIVE SUMMARY & IDENTITAS PROYEK](#1-executive-summary--identitas-proyek)
2. [INVENTARISASI & KATALOG SEMUA FILE DAN FOLDER LENGKAP](#2-inventarisasi--katalog-semua-file-dan-folder-lengkap)
   - 2.1 File-File Root (Akar Proyek)
   - 2.2 Folder Backend (`api/`)
   - 2.3 Folder Frontend (`web/`)
   - 2.4 Folder Machine Learning & Explainability (`src/`, `models/`, `medrec_xgboost/`)
   - 2.5 Folder Orkes & Agen (`langflow/`, MCP / IBM Bob)
   - 2.6 Folder Pengetahuan & Konfigurasi (`configs/`, `knowledge/`)
   - 2.7 Folder Data Klinis (`data/`)
   - 2.8 Folder Dokumentasi Proyek (`docs/`)
   - 2.9 Folder Pengujian (`tests/`)
   - 2.10 Folder Arsip (`_archive/`)
3. [DOKUMENTASI FITUR FRONTEND (REACT / VITE / TYPESCRIPT)](#3-dokumentasi-fitur-frontend-react--vite--typescript)
   - 3.1 Worklist Page (Daftar Antrean Prioritas Dinamis)
   - 3.2 BPMH Page (Form Penelusuran Riwayat Obat Terbaik)
   - 3.3 Patient Analysis Page (Analisis Mendalam 1 Pasien & Draf SBAR)
   - 3.4 Audit Log Page (Rekam Jejak Keputusan & Medicolegal Compliance)
   - 3.5 Settings Page (Kapasitas Bangsal & Registri High-Alert)
   - 3.6 Tutorial Page (Onboarding Apoteker & Edukasi Alur Kerja)
   - 3.7 Mode Eksekusi: Synthetic vs Live Mode
4. [DOKUMENTASI FITUR BACKEND (FASTAPI & SERVICES)](#4-dokumentasi-fitur-backend-fastapi--services)
   - 4.1 Routing & Endpoint Catalog
   - 4.2 Layer Layanan Klinis (`api/services/`)
   - 4.3 Database & State Persistence (`api/database.py`)
   - 4.4 Multi-Provider LLM Service & 6 Guardrail Checks
5. [DOKUMENTASI MACHINE LEARNING & EXPLAINABILITY](#5-dokumentasi-machine-learning--explainability)
   - 5.1 Definisi Masalah & Target Prediksi
   - 5.2 Fitur Leakage-Safe (10 SAFE_FEATURES vs 6 FORBIDDEN_FEATURES)
   - 5.3 Model XGBoost & Kalibrasi Isotonik
   - 5.4 Evaluasi Model & Baseline Comparison
   - 5.5 Explainability dengan TreeSHAP
   - 5.6 Analisis Track Ganda: `models/` vs `medrec_xgboost/`
6. [DOKUMENTASI INTEGRASI LANGFLOW & IBM BOB (MCP SERVER)](#6-dokumentasi-integrasi-langflow--ibm-bob-mcp-server)
   - 6.1 Peran Langflow dalam Arsitektur
   - 6.2 Alur Orkes Visual: Orchestrator vs Review Flows
   - 6.3 IBM Bob Integration via FastMCP (`mcp_server.py`)
   - 6.4 Prinsip Anti-Halusinasi & Zero Autonomous Action
7. [ALUR KERJA END-TO-END (END-TO-END WORKFLOW)](#7-alur-kerja-end-to-end-end-to-end-workflow)
   - 7.1 Alur Makro Rumah Sakit (Admisi ke Pulang)
   - 7.2 Alur Mikro Apoteker dalam Aplikasi PrioMed-Rec
   - 7.3 Diagram Alur Data & State Machine Pasien
8. [EVALUASI KRITIS & GAP ANALYSIS (TEMUAN LAPANGAN)](#8-evaluasi-kritis--gap-analysis-temuan-lapangan)
   - 8.1 Kesenjangan Standar Data (Synthea US EHR vs Kemenkes / SIMRS)
   - 8.2 Sinkronisasi Dual ML Track
   - 8.3 Kesiapan Infrastruktur Rumah Sakit (On-Premise vs Cloud)
   - 8.4 User Acceptance & Medicolegal Barrier
9. [MASUKAN, SARAN, & ROADMAP PENYEMPURNAAN (LANGKAH DEMI LANGKAH)](#9-masukan-saran--roadmap-penyempurnaan-langkah-demi-langkah)
   - Fase 1: Hardening & Konsolidasi Internal (Jangka Pendek)
   - Fase 2: Standarisasi Data Indonesia & Kemenkes KFA (Jangka Menengah)
   - Fase 3: Shadow Testing & Clinical Pilot di RS Pendidikan (Pra-Produksi)
   - Fase 4: Integrasi Penuh SIMRS & SatuSehat (Enterprise Ready)
10. [KESIMPULAN & PENUTUP](#10-kesimpulan--penutup)

---

## 1. EXECUTIVE SUMMARY & IDENTITAS PROYEK

PrioMed-Rec adalah sistem pendukung keputusan klinis (*Clinical Decision Support System / CDSS*) berbasis kecerdasan buatan (*AI*) yang dirancang khusus untuk memecahkan masalah kemacetan waktu (*time bottleneck*) dan kelelahan peringatan (*alert fatigue*) yang dihadapi oleh apoteker klinis rumah sakit dalam proses **Rekonsiliasi Obat Masuk Rawat Inap (*Admission Medication Reconciliation*)**.

### Urgensi Klinis
- Di rumah sakit umum dan rujukan, apoteker klinis menerima puluhan hingga ratusan pasien baru setiap hari.
- Proses rekonsiliasi manual membutuhkan waktu **15 hingga 50 menit per pasien** (standar WHO dan FIP).
- Akibat keterbatasan tenaga apoteker, telaah resep sering dilakukan secara acak atau berdasarkan urutan kedatangan (*First-In, First-Out / FIFO*). Akibatnya:
  - **~79% waktu apoteker terbuang** menelaah pasien dengan risiko diskrepansi rendah yang resepnya aman.
  - Pasien berisiko tinggi (geriatri, polifarmasi $\ge 5$ obat, pengguna obat indeks terapi sempit/*High-Alert*) yang berada di antrean bawah terlambat diperiksa.
  - Sekitar **50.5% ketidaksesuaian resep (*unintended discrepancies*)** yang tidak terdeteksi pada fase admisi akan terbawa sepanjang masa rawat inap hingga resep pemulangan (*discharge*), memicu kejadian tidak diinginkan terkait obat (*Adverse Drug Events / ADE*) dan peningkatan biaya rawat ulang (*readmission 30-day*).

### Batasan Etika & Medicolegal
PrioMed-Rec **BUKAN** sistem triase kegawatdaruratan medis (bukan triage UGD penentu hidup-mati). PrioMed-Rec adalah **alat triase urutan telaah resep farmasi** (*Medication Review Priority Queue*). Sistem ini tidak pernah mengganti resep secara otonom, tidak mengubah dosis tanpa persetujuan, dan selalu memposisikan **Apoteker dan Dokter Penanggung Jawab Pelayanan (DPJP)** sebagai pemegang keputusan akhir (*Human-in-the-Loop*).

---

## 2. INVENTARISASI & KATALOG SEMUA FILE DAN FOLDER LENGKAP

Berikut adalah rincian inventarisasi fisik seluruh file dan folder yang ada di dalam repositori proyek `priomed-rec`, mencakup fungsi dan perannya dalam arsitektur sistem:

```
priomed-rec/
├── .env.example / .env             # Variabel lingkungan runtime
├── .dockerignore / .gitignore      # Aturan ignore VCS dan build container
├── CHANGELOG.md                    # Catatan riwayat versi sistem
├── DATA_NOTES.md                   # Catatan integritas dan struktur data
├── Dockerfile.api                  # Blueprint container FastAPI backend
├── Dockerfile.web                  # Blueprint container React/Vite/Nginx frontend
├── docker-compose.yml              # Orkes multi-container (API, Web, Langflow)
├── mcp_server.py                   # Server Model Context Protocol (FastMCP) untuk IBM Bob
├── mcp_settings.json               # Konfigurasi integrasi IBM Bob MCP client
├── nginx.conf                      # Konfigurasi reverse proxy Nginx produksi
├── priomedrec_master_blueprint-v4.md # Cetak biru master komprehensif versi 4.0
├── pytest.ini                      # Konfigurasi eksekusi automated testing
├── README.md                       # Dokumentasi pengenalan dan cara menjalankan proyek
├── requirements.txt                # Dependensi Python backend dan ML
├── run_training_v3.py              # Script orisinal training model v3/v4 leakage-safe
├── api/                            # Backend REST API (FastAPI)
├── configs/                        # Konfigurasi berbasis JSON (aturan diskrepansi, ambang batas)
├── data/                           # Direktori data (raw Synthea, interim, processed, SQLite)
├── docs/                           # Dokumentasi teknis, model card, protokol, runbook
├── knowledge/                      # Basis pengetahuan klinis (interaksi obat terkurasi)
├── langflow/                       # File diagram alur orkes visual Langflow
├── medrec_xgboost/                 # Direktori eksperimen & kandidat model XGBoost alternatif
├── models/                         # Model aktif produksi, manifest fitur, dan threshold
├── scripts/                        # Script utilitas validasi data dan lingkungan
├── src/                            # Source code inti pemrosesan data, fitur, ML, rules, dan LLM
├── tests/                          # Automated unit test & integration test suite
├── web/                            # Frontend aplikasi web (React + Vite + TypeScript)
└── _archive/                       # Arsip prototipe lama (Streamlit, UI konseptual, dokumen legacy)
```

---

### 2.1 File-File Root (Akar Proyek)

| Nama File | Ukuran / Karakter | Fungsi & Peran dalam Sistem |
| :--- | :--- | :--- |
| `README.md` | ~8 KB | Gerbang pengenalan proyek, panduan instalasi lokal, dan arsitektur runtime *Website-first*. |
| `priomedrec_master_blueprint-v4.md` | ~37 KB | Dokumen cetak biru master paling lengkap (versi 4.0), merinci landasan regulasi Permenkes 72/2016, alur klinis, formula ML, dan arsitektur hibrida. |
| `DATA_NOTES.md` | ~6.5 KB | Dokumentasi profil data, volume baris tabel Synthea, audit anomali data, dan justifikasi pembersihan. |
| `CHANGELOG.md` | ~2.3 KB | Catatan perubahan historis mulai dari prototipe Streamlit awal hingga migrasi ke React/Vite dan isolasi leakage. |
| `docker-compose.yml` | ~1.9 KB | Konfigurasi orkestrasi 3 kontainer: `api` (port 8000), `langflow` (port 7860), dan `web` (port 80) lengkap dengan volume persisten. |
| `Dockerfile.api` | ~800 B | Definisi image Python 3.12 slim untuk menjalankan FastAPI backend. |
| `Dockerfile.web` | ~376 B | Multi-stage build image frontend: compile React via Node.js lalu disajikan menggunakan Nginx alpine. |
| `nginx.conf` | ~1.4 KB | Konfigurasi reverse proxy internal web server: meneruskan `/api/` ke backend FastAPI dan `/langflow/` ke engine Langflow. |
| `.env.example` / `.env` | ~2.7 KB | Template konfigurasi environment (API keys Gemini/Groq, host, port, flow ID Langflow, CORS). |
| `mcp_server.py` | ~2.2 KB | Server MCP berbasis `fastmcp` (stdio) yang mengekspos 3 tools klinis untuk IBM Bob tanpa hak memanipulasi terapi. |
| `mcp_settings.json` | ~189 B | File manifest pendaftaran server MCP ke ekosistem IBM Bob / Claude Desktop. |
| `requirements.txt` | ~313 B | Daftar dependensi pustaka Python: FastAPI, Uvicorn, XGBoost, Scikit-Learn, SHAP, FastMCP, Pandas, Google-GenAI, Groq, dll. |
| `pytest.ini` | ~138 B | Konfigurasi testing suite, path direktori `tests`, dan penandaan marker `slow`. |
| `run_training_v3.py` | ~28 KB | Script Python independen untuk menjalankan pipeline ekstraksi data, feature engineering, pelatihan XGBoost, kalibrasi isotonik, dan pengujian permutasi 1000-seed. |

---

### 2.2 Folder Backend (`api/`)

Folder ini berisi implementasi REST API modern menggunakan FastAPI yang berfokus pada ketepatan kontrak data, keamanan klinis, dan integrasi multi-layanan:

```
api/
├── __init__.py / app.py            # Entry point backward compatibility
├── main.py                         # Inisialisasi FastAPI, lifespan, middleware CORS, mounting router
├── config.py                       # Parser konfigurasi lingkungan (pydantic-settings / env reader)
├── auth.py                         # Validasi X-API-Key untuk otentikasi antar-layanan
├── database.py                     # SQLite persistence layer (WAL mode, relasi tabel operasional)
├── logging_config.py               # Setup logging terstruktur dengan format audit klinis
├── schemas.py                      # Pydantic schema model (request/response kontrak API)
├── routes/
│   ├── analyze.py                  # POST /analyze (analisis 1 pasien: ML + SHAP + Rules + LLM SBAR)
│   ├── bpmh.py                     # POST & GET /bpmh/{patient_id} (pengelolaan form riwayat obat terbaik)
│   ├── discrepancy.py              # POST /discrepancies (audit rule-based omisi & duplikasi)
│   ├── health.py                   # GET /health (monitoring liveness & versi model/rule/api)
│   ├── interactions.py             # POST /interactions/check & safety (lookup interaksi & high-alert)
│   ├── patient.py                  # GET /patient/{patient_id} & sample (pencarian rekam encounter)
│   ├── prioritization.py           # POST /prioritize & /prioritize/batch (pemeringkatan massal XGBoost)
│   ├── review.py                   # POST /review & GET /reviews (audit trail aksi apoteker)
│   └── wards.py                    # GET /wards & POST /wards/config (konfigurasi kapasitas bangsal)
└── services/
    ├── discrepancy_service.py       # Wrapper pemanggilan DiscrepancyEngine dari src/rules
    ├── llm_service.py              # Orkestrator LLM hibrida (Gemini/Groq/Fallback) + 6 Guardrails
    ├── patient_service.py          # Wrapper patient resolver dan pemuat data encounter
    └── prioritization_service.py   # Loader singleton model XGBoost, komputasi fitur aman & SHAP
```

---

### 2.3 Folder Frontend (`web/`)

Folder ini merupakan antarmuka pengguna utama berbasis React 18, Vite, dan TypeScript dengan arsitektur modular tanpa ketergantungan runtime pada Streamlit:

```
web/
├── index.html                      # Single Page Application HTML root
├── vite.config.ts                  # Konfigurasi build Vite, alias path, dan dev proxy ke FastAPI & Langflow
├── tsconfig.json                   # Konfigurasi compiler TypeScript (strict typing)
├── package.json                    # Metadata proyek frontend, scripts (dev, build), dependensi Lucide/Tailwind
├── src/
│   ├── main.tsx                    # React DOM root bootstrapping
│   ├── App.tsx                     # Top-level state coordinator, routing halaman, live/synthetic switcher
│   ├── index.css                   # Gaya CSS global, Tailwind base, dan tema klinis
│   ├── vite-env.d.ts               # Tipe environment Vite
│   ├── api/
│   │   ├── client.ts               # Wrapper fetch komprehensif ke semua endpoint FastAPI
│   │   ├── langflow.ts             # Klien orkes HTTP khusus ke endpoint Langflow /api/v1/run
│   │   ├── errors.ts               # Parser pesan kesalahan jaringan & klinis yang ramah pengguna
│   │   └── hooks.ts                # React custom hooks untuk fetch data asinkron
│   ├── components/
│   │   ├── clinical.tsx            # Komponen domain klinis: AppShell, PatientCard, PriorityBadge, RiskGauge, SbarCard, DiscrepancyCard, SafetyFlagCard
│   │   └── ui.tsx                  # Komponen atomik: Button, Modal, Input, Badge, Table, Tooltip, Alert
│   ├── data/
│   │   └── clinicalData.ts         # Dataset sintetis realistis untuk demonstrasi mode zero-backend
│   ├── pages/
│   │   ├── WorklistPage.tsx        # Halaman antrean prioritas pasien, filter risiko, SLA monitoring
│   │   ├── BpmhPage.tsx            # Halaman input riwayat obat sebelum admisi (BPMH) & disposisi
│   │   ├── PatientAnalysisPage.tsx # Halaman analisis lengkap 1 pasien, visual SHAP, draf SBAR, review form
│   │   ├── AuditLogPage.tsx        # Halaman jejak audit medicolegal tindakan apoteker
│   │   ├── SettingsPage.tsx        # Halaman konfigurasi kapasitas bangsal & obat high-alert
│   │   └── TutorialPage.tsx        # Panduan onboarding interaktif untuk apoteker baru
│   └── types/
│       └── clinical.ts             # Definisi tipe TypeScript domain klinis lengkap
```

---

### 2.4 Folder Machine Learning & Explainability (`src/`, `models/`, `medrec_xgboost/`)

Sistem ML PrioMed-Rec dibagi menjadi komponen aktif produksi (`src/` dan `models/`) serta track eksperimen alternatif (`medrec_xgboost/`):

1. **`src/` (Engine Pemrosesan & Inferensi):**
   - `src/models/train.py`: Pipeline pelatihan algoritma baseline (Rule, LogReg, RandomForest, XGBoost).
   - `src/models/evaluate.py`: Kalkulator metrik evaluasi medis (ROC-AUC, PR-AUC, Brier score, Top-20% Recall).
   - `src/models/predict.py`: Modul inferensi produksi yang menghasilkan probabilitas terkalibrasi.
   - `src/models/inference_guard.py`: **Pengawal Keamanan Data**. Menolak eksekusi jika input mengandung salah satu dari 6 `FORBIDDEN_FEATURES` (anti-data leakage).
   - `src/explainability/shap_explainer.py`: Ekstraksi nilai TreeSHAP untuk menghitung kontribusi spesifik setiap fitur pasien terhadap skor risiko.
   - `src/features/clinical_features.py` & `medication_features.py`: Transformasi data mentah menjadi 10 `SAFE_FEATURES`.
   - `src/rules/discrepancy_engine.py`: Mesin deterministik pemeriksa omisi dan duplikasi obat berbasis aturan baku.
   - `src/rules/safety_flags_engine.py`: Pemeriksa obat berisiko terhadap registri ISMP High-Alert 2024, FDA NTI, dan AGS Beers Criteria 2023.
   - `src/llm/service.py`: Layanan LLM dengan mekanisme pertahanan *exponential backoff* dan fallback multi-model (Gemini 2.5 Flash $\rightarrow$ Gemini 1.5 Flash 8b $\rightarrow$ Groq LLaMA 3.3 70B $\rightarrow$ Rule-based text generator).
   - `src/llm/validators/output_validator.py`: **6 Guardrail Klinis**. Memeriksa teks keluaran LLM agar tidak mengubah angka probabilitas, tidak memalsukan nama obat, dan tidak mengeluarkan instruksi terapi otonom.

2. **`models/` (Artefak Model Produksi Aktif):**
   - `priomed_prioritization_model.pkl`: Model XGBoost terlatih versi `model-0.3.0`.
   - `priomed_prioritization_model_calibrated.pkl`: Model XGBoost yang telah dikalibrasi menggunakan *Isotonic Regression*.
   - `thresholds.json`: Ambang batas probabilitas operasional (`HIGH`: $\ge 0.70$, `MEDIUM`: $0.40–0.69$, `LOW`: $< 0.40$).
   - `feature_manifest.json`: Urutan baku 10 fitur aman yang diakui oleh model.
   - `metadata.json`: Metadata waktu pembuatan, versi label (`labels-3.0.0`), dan skor validasi.
   - `eval_report_v4.json`: Laporan metrik performa komparatif lengkap pada data uji independen.

3. **`medrec_xgboost/` (Candidate / Research Sandbox):**
   - `xgboost_PrioMedRec.ipynb`: Notebook eksperimen eksploratif pada data mentah Synthea alternatif.
   - `Output/`: Menyimpan hasil pipeline alternatif seperti `xgb_medrec_pipeline.joblib`, grafik evaluasi, dan worklist simulasi.
   - *Status:* Bersifat terisolasi. Tidak boleh langsung menimpa file di `models/` tanpa adaptor inferensi resmi.

---

### 2.5 Folder Orkes & Agen (`langflow/`, MCP / IBM Bob)

- `langflow/priomedrec_orchestrator.json`: Diagram visual alur orkestrasi Langflow untuk menerima query pengguna, melakukan resolusi identitas pasien, memanggil endpoint `/analyze`, dan meminta narasi ringkas dari LLM.
- `langflow/priomedrec_review.json`: Diagram alur untuk menangkap tindakan apoteker (APPROVE / REJECT / EDIT) dan menyimpannya ke audit log.
- `langflow/priomedrec_agentic_v2.json`: Konfigurasi alur interaktif multi-agen eksperimental.
- `mcp_server.py`: Server Model Context Protocol (FastMCP) yang menjembatani asisten AI eksternal (seperti IBM Bob) dengan backend PrioMed-Rec melalui 3 tools terstandarisasi:
  1. `rank_admission_risk`: Memanggil pemeringkatan prioritas batch.
  2. `detect_medication_discrepancy`: Memanggil audit diskrepansi deterministik.
  3. `record_pharmacist_review`: Mencatat hasil telaah akhir apoteker ke basis data audit.

---

### 2.6 Folder Pengetahuan & Konfigurasi (`configs/`, `knowledge/`)

- `configs/discrepancy_rules.json`: Pengaturan aturan audit diskrepansi (definisi omisi tidak terdokumentasi, duplikasi substansi aktif, jendela waktu admisi).
- `configs/high_alert_medications.json`: Registri lokal obat kewaspadaan tinggi (High-Alert Medications).
- `configs/drug_class_map.json`: Kamus pemetaan nama obat ke kelas farmakologi/terapi.
- `configs/model_thresholds.json`: Nilai cut-off batas bawah dan atas pengelompokan triase risiko.
- `knowledge/interactions.json`: Basis pengetahuan terkurasi pasangan interaksi obat penting (DDInter) lengkap dengan tingkat keparahan, mekanisme, saran pemantauan, dan referensi literatur.

---

### 2.7 Folder Data Klinis (`data/`)

- `data/raw/synthea/`: Data mentah hasil generator rekam medis sintetis Synthea (mencakup `patients.csv`, `encounters.csv`, `conditions.csv`, `medications.csv`, `medication_administrations.csv`, `medication_requests.csv`, `allergies.csv`, `observations.csv`).
- `data/interim/`: Hasil ekstraksi sementara berupa kohort rawat inap (`admission_cohort.csv`), garis waktu obat (`medication_timeline.csv`), dan obat pra-admisi (`pre_admission_meds.csv`).
- `data/processed/`: Matriks fitur akhir (`feature_matrix.csv`) dan dataset siap latih (`model_ready.csv`).
- `data/drug_risk_lookup.csv`: Basis data terpadu pengenal obat risiko tinggi (ISMP, NTI, Beers).
- `data/priomed.db`: Database SQLite operasional lokal yang menyimpan catatan BPMH, log audit, status alur kerja pasien, dan konfigurasi bangsal.

---

### 2.8 Folder Dokumentasi Proyek (`docs/`)

Kumpulan dokumen spesifikasi teknis dan tata kelola klinis:
- `architecture.md`: Penjelasan arsitektur sistem dan batas interaksi antar komponen.
- `API_contract.md`: Spesifikasi lengkap skema request, response, dan status kode HTTP.
- `DECISION_LOG.md`: Log keputusan arsitektur mengikat (DQI untuk kualitas data, ENG untuk rekayasa perangkat lunak, MDL untuk pemodelan, CLN untuk keselamatan klinis).
- `MODEL_CARD.md`: Model Card formal sesuai standar tata kelola AI kesehatan.
- `RULEBOOK.md`: Aturan deterministik CDSS dan pencegahan risiko.
- `LANGFLOW_AND_IBM_BOB.md`: Panduan tata cara setup dan import flow Langflow serta registrasi MCP IBM Bob.
- `WEBSITE_RUNBOOK.md`: Panduan operasional pengembangan lokal dan deployment Docker.
- `database_schema.md`: Rancangan skema tabel SQLite.
- `data_dictionary.md` & `data_provenance.md`: Kamus data mentah dan silsilah data Synthea.
- `feature_dictionary.md` & `feature_provenance.md`: Kamus fitur ML dan analisis pencegahan kebocoran data (*leakage analysis*).
- `evaluation_protocol.md` & `ML_AUDIT_REPORT.md`: Protokol pengujian performa model dan hasil audit matematis.
- `usability_test_script.md`: Skenario uji coba kegunaan aplikasi (*usability testing*) bersama apoteker.

---

### 2.9 Folder Pengujian (`tests/`)

Rangkaian 240+ automated test menggunakan `pytest` yang menjamin keselamatan klinis dan kestabilan perangkat lunak:
- `test_api.py`: Pengujian seluruh endpoint FastAPI.
- `test_model.py`: Pengujian integritas model, kalibrasi, dan reproduktibilitas skor.
- `test_guardrails.py`: Pengujian 6 lapis filter keamanan keluaran LLM.
- `test_rules.py` & `test_rules_disposition.py`: Pengujian keakuratan deteksi omisi dan duplikasi obat dengan memperhitungkan status disposisi apoteker.
- `test_safety_flags_engine.py`: Pengujian pencocokan obat High-Alert, NTI, dan Beers Criteria.
- `test_langflow_integration.py`: Pengujian ketahanan integrasi Langflow dan mekanisme fallback ke API.
- `test_e2e.py`: Pengujian skenario end-to-end dari admisi hingga pencatatan review.

---

### 2.10 Folder Arsip (`_archive/`)

Menyimpan artefak pengembangan masa lalu yang telah digantikan untuk keperluan jejak historis:
- `_archive/streamlit_app/`: Antarmuka prototipe lama berbasis Streamlit (tidak digunakan lagi di runtime).
- `_archive/UIUXLengkapFigma/`: Ekspor kode prototipe desain awal dari Figma.
- Dokumen perencanaan awal (`PROJECT_CONTEXT.md`, blueprint versi 2, roadmap pra-stabilisasi).

---

## 3. DOKUMENTASI FITUR FRONTEND (REACT / VITE / TYPESCRIPT)

Aplikasi web PrioMed-Rec dibangun dengan standar antarmuka klinis modern yang mengutamakan kecepatan akses informasi, kontras visual yang ergonomis bagi petugas medis, dan navigasi bebas hambatan.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PRIOMED-REC NAVIGATION BAR                         │
│  [Logo PrioMed-Rec]   | Worklist | BPMH | Analisis Pasien | Audit Log | ... │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Worklist Page (Daftar Antrean Prioritas Dinamis)
Halaman ini adalah **pintu masuk harian apoteker** saat memulai shift kerja:
- **Tabel Antrean Pasien Berbobot Risiko:** Menampilkan daftar pasien rawat inap yang diurutkan otomatis oleh model XGBoost berdasarkan *Predicted Discrepancy Likelihood* (dari risiko tertinggi ke terendah).
- **Badge Tingkat Prioritas (Color-Coded):**
  - `HIGH` (Merah): Discrepancy Likelihood $\ge 0.70$. Pasien wajib ditelaah dalam batas waktu SLA admisi (<12–24 jam).
  - `MEDIUM` (Kuning): Discrepancy Likelihood $0.40–0.69$. Pasien ditelaah pada putaran kedua.
  - `LOW` (Hijau): Discrepancy Likelihood $< 0.40$. Skrining cepat; jika kapasitas terbatas, telaah mendalam dapat didelegasikan setelah kelompok High & Medium selesai.
- **Filter Klinis Multifaset:**
  - Filter berdasarkan Bangsal Perawatan (ICU, HCU, Penyakit Dalam, Bedah, Kardiologi, Geriatri).
  - Filter Polifarmasi ($\ge 5$ obat).
  - Filter Pasien Pengguna Obat *High-Alert*.
  - Pencarian instan berdasarkan Nama Pasien, No Rekam Medis (RM), atau ID Encounter.
- **Indikator Beban Kerja Bangsal (Ward Capacity Indicator):** Menampilkan perbandingan jumlah apoteker yang bertugas di bangsal tertentu dengan jumlah pasien berisiko tinggi yang menunggu ulasan.
- **Aksi Cepat 1-Klik:** Tombol langsung menuju pengisian BPMH atau telaah analisis pasien terpilih.

---

### 3.2 BPMH Page (Form Penelusuran Riwayat Obat Terbaik)
Mengakomodasi pelaksanaan standar Tahap 2 dalam asuhan kefarmasian:
- **Pencatatan Multi-Sumber Riwayat Obat Rumah:** Apoteker atau Tenaga Teknis Kefarmasian (TTK) menginput daftar obat yang dikonsumsi pasien di rumah sebelum masuk rumah sakit (Bawahan Pasien, Catatan Keluarga, Resep Luar, atau Rekam Apotek Komunitas).
- **Entri Spesifikasi Dosis & Rute:** Nama obat, sediaan, dosis, frekuensi penggunaan, rute pemberian, dan kepatuhan terakhir diminum.
- **Kolom Disposisi Klinis Apoteker:**
  Apoteker dapat menandai status obat rumah terhadap terapi rawat inap baru:
  - `DILANJUTKAN` (Terapi rumah diteruskan di rawat inap dengan regimen sama).
  - `DITUNDA` (Terapi rumah dihentikan sementara selama kondisi akut rawat inap, misal antidiabetik oral diganti insulin geser).
  - `DIGANTI` (Diganti dengan obat setara formularium rumah sakit).
  - `DIHENTIKAN` (Dihentikan permanen karena kontraindikasi atau terapi telah selesai).
- **Penyimpanan Terstruktur ke Basis Data:** Data tersimpan aman di tabel SQLite `bpmh_records` dan mengubah status pasien menjadi `BPMH_TERISI`, siap untuk dieksekusi oleh mesin deteksi diskrepansi.

---

### 3.3 Patient Analysis Page (Analisis Mendalam 1 Pasien & Draf SBAR)
Halaman kerja analitis utama apoteker saat melakukan rekonsiliasi satu per satu:
- **Header Profil Pasien & Ringkasan Klinis:** Identitas teranonimasi, usia, jenis kelamin, diagnosis aktif admisi, lama rawat, dan riwayat alergi.
- **Panel Skor Risiko & Visualisasi Kontribusi Fitur (SHAP Breakdown):**
  - *Risk Gauge Bar* menampilkan skor probabilitas terkalibrasi [0.00 – 1.00].
  - Grafik batang kontribusi faktor risiko (TreeSHAP) yang menjelaskan secara transparan *mengapa* pasien mendapat prioritas tinggi (misalnya: usia 72 tahun [+0.18], polifarmasi 8 obat [+0.22], ada antikoagulan warfarin [+0.15]).
- **Kartu Audit Diskrepansi Deterministik (Rule-Based Flags):**
  - **POTENTIAL_UNDOCUMENTED_OMISSION:** Obat rutin di rumah yang tidak tercantum pada resep admisi tanpa adanya keterangan disposisi yang sah.
  - **POSSIBLE_SUBSTITUTION:** Deteksi pergantian obat dalam kelas terapi yang sama (misal Captopril di rumah diganti Ramipril di rumah sakit).
  - **POTENTIAL_DUPLICATION:** Duplikasi zat aktif atau kelas terapi ganda pada resep baru.
  - Label keamanan wajib: Seluruh kartu diskrepansi memuat badge peringatan `Verifikasi Diperlukan` (*verification_required = True*).
- **Kartu Peringatan Keamanan Obat (Safety & Interaction Flags):**
  - ISMP High-Alert Drug alert (misal: Insulin, Heparin, Narkotika).
  - FDA Narrow Therapeutic Index (NTI) alert (misal: Digoxin, Phenytoin).
  - AGS Beers Criteria PIM alert untuk pasien usia $\ge 65$ tahun.
  - Kartu Interaksi Obat Terkurasi (DDInter) lengkap dengan rekomendasi monitoring laboratorium.
- **Clinical Copilot: Draf Laporan SBAR Otomatis (Grounded LLM):**
  Menyintesis draf komunikasi medis terstruktur:
  - **S (Situation):** Identitas pasien, bangsal, dan alasan admisi.
  - **B (Background):** Riwayat obat rumah dan riwayat penyakit relevan.
  - **A (Assessment):** Temuan potensi omisi, duplikasi, atau interaksi obat berisiko.
  - **R (Recommendation):** Saran rekomendasi teknis farmasi siap diskusi ke DPJP.
  - Dilengkapi tombol **"1-Click Copy SBAR"** untuk kemudahan pasting ke lembar Catatan Perkembangan Pasien Terintegrasi (CPPT) di SIMRS.
- **Bilah Aksi Telaah Apoteker (Action Bar):**
  Apoteker melakukan konfirmasi akhir dengan memilih:
  - `APPROVE` (Menyetujui temuan dan rekomendasi).
  - `EDIT` (Memodifikasi rekomendasi atau menambahkan catatan khusus sebelum disetujui).
  - `REJECT` (Menolak telaah jika diskrepansi yang ditandai ternyata disengaja secara klinis oleh DPJP).

---

### 3.4 Audit Log Page (Rekam Jejak Keputusan & Medicolegal Compliance)
- Menampilkan riwayat seluruh keputusan telaah rekonsiliasi yang pernah dibuat oleh apoteker.
- Menyimpan identitas Apoteker (`pharmacist_id`), stempel waktu (*timestamp* ISO), ID Kasus/Encounter, tindakan yang diambil, catatan telaah, versi model ML yang digunakan (`model_version`), dan versi aturan deterministik (`rule_version`).
- Memenuhi persyaratan akreditasi rumah sakit (KARS / JCI) terkait keterlacakan intervensi farmasi klinis.

---

### 3.5 Settings Page (Kapasitas Bangsal & Registri High-Alert)
- **Manajemen Alokasi Apoteker per Bangsal:** Mengatur kapasitas kuota telaah per shift untuk menyesuaikan beban kerja riil di bangsal.
- **Registri High-Alert Lokal:** Menampilkan dan menyesuaikan daftar obat kewaspadaan tinggi sesuai formularium rumah sakit setempat.

---

### 3.6 Tutorial Page (Onboarding Apoteker & Edukasi Alur Kerja)
- Modul pelatihan mandiri terintegrasi di dalam aplikasi untuk memandu apoteker baru memahami:
  - Filosofi *AI as Copilot, not Prescriber*.
  - Cara membaca skor probabilitas dan kontribusi faktor SHAP.
  - Tata cara pengisian form BPMH dan penetapan disposisi obat.
  - Prosedur penulisan catatan CPPT berstandar SBAR.

---

### 3.7 Mode Eksekusi: Synthetic vs Live Mode
Aplikasi frontend dirancang fleksibel dengan konfigurasi sakelar `VITE_DATA_MODE`:
- **Mode `synthetic`:** Menggunakan basis data tiruan lokal (`clinicalData.ts`). Sangat ideal untuk demo cepat, presentasi UI/UX, dan pelatihan tanpa perlu mengaktifkan server backend.
- **Mode `live`:** Menghubungkan antarmuka secara penuh ke backend FastAPI melalui reverse proxy `/api` dan Langflow melalui `/langflow`. Memuat data encounter riil dan mencatat log audit ke SQLite.

---

## 4. DOKUMENTASI FITUR BACKEND (FASTAPI & SERVICES)

Backend PrioMed-Rec dibangun menggunakan framework performa tinggi **FastAPI**, memanfaatkan validasi tipe data ketat Pydantic v2, arsitektur asinkron, dan sistem logging berstandar medis.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FASTAPI SERVICE LAYER                            │
│  [API Routers] ──► [Clinical Services] ──► [Engines / Models / Database]    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Routing & Endpoint Catalog

| HTTP Method | Endpoint | Router File | Deskripsi & Fungsi Klinis |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | `routes/health.py` | Liveness check status server, versi API, versi model aktif, dan versi rule engine. |
| `GET` | `/patient/{patient_id}` | `routes/patient.py` | Mengambil detail encounter pasien, demografi, dan riwayat obat terkait. |
| `GET` | `/patients/sample` | `routes/patient.py` | Mengambil daftar ID pasien sampel untuk kebutuhan pengujian cepat. |
| `POST` | `/prioritize` | `routes/prioritization.py` | Menghitung *Predicted Discrepancy Likelihood* untuk 1 pasien menggunakan model XGBoost. |
| `POST` | `/prioritize/batch` | `routes/prioritization.py` | Memeringkat daftar massal pasien ($N$ pasien) sekaligus dan mengurutkannya berdasarkan risiko. |
| `POST` | `/discrepancies` | `routes/discrepancy.py` | Mengeksekusi audit deterministik diskrepansi obat (omisi, duplikasi, substitusi). |
| `POST` | `/analyze` | `routes/analyze.py` | **Endpoint Utama One-Shot**. Menjalankan inferensi ML, ekstraksi SHAP, audit diskrepansi, pengecekan interaksi obat, dan penyusunan draf SBAR dalam satu pemanggilan API. |
| `POST` | `/bpmh/{patient_id}` | `routes/bpmh.py` | Menyimpan formulir riwayat obat sebelum admisi (BPMH) beserta disposisi klinis apoteker. |
| `GET` | `/bpmh/{patient_id}` | `routes/bpmh.py` | Mengambil data riwayat obat BPMH yang tersimpan untuk pasien tertentu. |
| `POST` | `/review` | `routes/review.py` | Menyimpan aksi telaah akhir apoteker (APPROVE / REJECT / EDIT) ke dalam audit trail permanen. |
| `GET` | `/reviews` | `routes/review.py` | Mengambil riwayat log audit keputusan apoteker (dengan pagination). |
| `GET` | `/wards` | `routes/wards.py` | Mengambil daftar kapasitas tempat tidur dan alokasi apoteker per bangsal. |
| `POST` | `/wards/config` | `routes/wards.py` | Memperbarui parameter kapasitas bangsal. |
| `POST` | `/interactions/check` | `routes/interactions.py` | Memeriksa potensi interaksi antara dua obat pada basis data terkurasi DDInter. |
| `POST` | `/interactions/safety` | `routes/interactions.py` | Mengevaluasi daftar obat admisi terhadap registri ISMP High-Alert, NTI, dan Beers Criteria. |

---

### 4.2 Layer Layanan Klinis (`api/services/`)

Untuk menjaga prinsip *Clean Architecture* dan pemisahan tanggung jawab (*Separation of Concerns*), router tidak mengeksekusi logika bisnis secara langsung, melainkan mendelegasikannya ke layer layanan:
- **`prioritization_service.py`:** Memuat artefak model XGBoost (`.pkl`), file konfigurasi ambang batas (`thresholds.json`), dan metadata secara singleton. Bertanggung jawab mengekstrak 10 `SAFE_FEATURES`, memanggil pelindung `InferenceGuard`, mengeksekusi fungsi prediksi, dan menghitung nilai TreeSHAP.
- **`discrepancy_service.py`:** Menginisialisasi `DiscrepancyEngine` dengan konfigurasi aturan baku dari `configs/discrepancy_rules.json`. Menangani pemetaan normalisasi nama obat dan mengevaluasi status omisi berdasar disposisi apoteker.
- **`patient_service.py`:** Mengakses repositori data encounter Synthea/SIMRS untuk menyatukan demografi, daftar obat berjalan, dan diagnosa aktif pasien.
- **`llm_service.py`:** Mengelola orkestrasi pemanggilan Large Language Model dengan proteksi penuh terhadap halusinasi medis.

---

### 4.3 Database & State Persistence (`api/database.py`)

PrioMed-Rec menggunakan basis data SQLite lokal (`data/priomed.db`) yang dioptimalkan dengan mode **Write-Ahead Logging (WAL)** dan penegakan kunci asing (*foreign keys*). Hal ini menjamin persistensi data yang cepat, handal, dan tidak memerlukan instalasi database server yang rumit untuk implementasi *edge* di rumah sakit:
- **Tabel `bpmh_records`:** Menyimpan data riwayat obat rumah pasien, asal informasi, stempel waktu, dan JSON serialisasi daftar obat beserta disposisinya.
- **Tabel `audit_entries`:** Menyimpan rekam jejak telaah apoteker secara tidak dapat diubah (*immutable audit trail*) untuk kepentingan audit mutu dan hukum medis.
- **Tabel `ward_configs`:** Menyimpan konfigurasi bangsal perawatan.
- **Tabel `patient_status`:** Menyimpan status alur kerja terkini setiap pasien (`Menunggu BPMH`, `Siap dianalisis`, `Perlu verifikasi`, `Disetujui`, `Ditolak`).
- **Tabel `local_high_alert`:** Menyimpan daftar penyesuaian obat kewaspadaan tinggi lokal rumah sakit.

---

### 4.4 Multi-Provider LLM Service & 6 Guardrail Checks

Untuk menyusun draf narasi klinis SBAR yang akurat tanpa risiko terhentinya layanan akibat pembatasan kuota API (*rate limit* 429/503), backend menerapkan sistem **Multi-Provider Fallback Chain**:
1. **Primary Provider:** Google Gemini 2.5 Flash (sangat cepat dan pemahaman instruksi klinis tinggi).
2. **Secondary Provider:** Google Gemini 1.5 Flash 8b (hemat kuota, latensi rendah).
3. **Tertiary Provider:** Groq LLaMA 3.3 70B Versatile (cadangan lintas penyedia jika Google AI Studio mengalami pemadaman).
4. **Deterministic Fallback:** Template Generator Deterministik berbasis aturan (menghasilkan draf SBAR terstruktur murni dari data JSON tanpa memanggil LLM sama sekali jika seluruh akses internet terputus).

#### 6 Lapis Guardrail Klinis (`src/llm/validators/output_validator.py`)
Setiap teks yang dihasilkan oleh LLM wajib lolos dari 6 uji filter sebelum dikirim ke frontend:
1. **Model Output Preservation Check:** LLM dilarang keras mengubah angka probabilitas risiko (`predicted_discrepancy_likelihood`) atau kategori prioritas (`medication_review_priority`) yang telah dihitung oleh XGBoost.
2. **Medication Inventory Grounding Check:** LLM dilarang menyebutkan nama obat baru yang tidak tercantum dalam daftar riwayat obat rumah maupun resep admisi pasien (mencegah fabrikasi resep).
3. **Discrepancy Consistency Check:** LLM dilarang mengklaim adanya diskrepansi selain yang telah diverifikasi oleh Rule Engine.
4. **No Autonomous Clinical Direction Check:** LLM dilarang memberikan kalimat instruksi mandiri seperti *"Berikan obat X sekarang"* atau *"Hentikan obat Y segera"*. Kalimat wajib bersifat rekomendasi telaah seperti *"Disarankan konfirmasi ke DPJP mengenai kelanjutan obat X"*.
5. **PII Anonymization Check:** Memastikan tidak ada data identitas pribadi sensitif (NIK, Alamat, No Kontak) yang lolos ke prompt eksternal atau laporan.
6. **Structure & SBAR Format Check:** Memastikan respons mematuhi struktur 4 seksi formal SBAR.

---

## 5. DOKUMENTASI MACHINE LEARNING & EXPLAINABILITY

Komponen Machine Learning pada PrioMed-Rec berfungsi sebagai **Mesin Pengurut Antrean Telaah (Prioritization Sorter)**, bukan penentu diagnosis penyakit.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ML PRIORITIZATION PIPELINE                         │
│  Patient Data ──► Feature Engineering ──► InferenceGuard (Safe Features)    │
│                         │                                                   │
│                         ▼                                                   │
│                 XGBoost Classifier ──► Isotonic Calibration                 │
│                         │                                                   │
│                         ├──► Predicted Discrepancy Likelihood [0.0 - 1.0]   │
│                         ├──► Medication Review Priority {HIGH, MED, LOW}   │
│                         └──► TreeSHAP Explainer ──► Top Feature Drivers     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.1 Definisi Masalah & Target Prediksi
- **Tugas Pemodelan:** Klasifikasi Biner (*Supervised Binary Classification*).
- **Variabel Target ($y$):** `has_discrepancy` (Nilai 1 = pasien memiliki probabilitas tinggi mengalami ketidaksesuaian resep omisi/duplikasi; Nilai 0 = resep selaras).
- **Output Model:**
  1. *Predicted Discrepancy Likelihood*: Nilai kontinu $[0.00 – 1.00]$.
  2. *Medication Review Priority*: Pengelompokan triase menjadi `HIGH`, `MEDIUM`, atau `LOW`.

---

### 5.2 Fitur Leakage-Safe (10 SAFE_FEATURES vs 6 FORBIDDEN_FEATURES)

Salah satu keunggulan teknis paling signifikan dari PrioMed-Rec adalah penerapan pemisahan fitur yang ketat guna mencegah **Data Leakage (Kebocoran Data Target)**.

#### 10 SAFE_FEATURES (Diizinkan untuk Inferensi)
Fitur-fitur ini mencerminkan kompleksitas klinis pasien yang sah diketahui pada saat pasien mendaftar di admisi, tanpa membocorkan jawaban ada/tidaknya kesalahan resep:
1. `age`: Usia pasien dalam satuan tahun.
2. `age_65_plus`: Flag biner apakah pasien tergolong geriatri ($\ge 65$ tahun).
3. `gender_encoded`: Jenis kelamin pasien (0/1).
4. `polypharmacy_flag`: Flag biner polifarmasi ($\ge 5$ obat sebelum admisi).
5. `high_alert_flag`: Flag biner adanya konsumsi minimal 1 obat risiko tinggi.
6. `high_alert_count`: Jumlah akumulatif obat risiko tinggi yang dikonsumsi.
7. `active_condition_count`: Jumlah penyakit atau diagnosa aktif pasien saat masuk.
8. `prior_encounter_count`: Jumlah riwayat kunjungan rawat inap pasien sebelumnya.
9. `allergy_count`: Jumlah riwayat alergi terdokumentasi (saat ini bernilai 0 berdasar keputusan DQI-001).
10. `has_drug_allergy`: Flag biner adanya riwayat alergi obat khusus.

#### 6 FORBIDDEN_FEATURES (Ditolak oleh `InferenceGuard`)
Fitur-fitur berikut **dilarang keras** digunakan dalam pelatihan maupun inferensi karena secara matematis identik dengan definisi label ketidaksesuaian resep:
1. `discontinued_medication_count`: Merefleksikan langsung logika deteksi omisi.
2. `potential_duplicate_candidates`: Merefleksikan langsung logika deteksi duplikasi.
3. `pre_admission_medication_count`: Berdekatan langsung dengan kalkulasi omisi.
4. `admission_medication_count`: Berdekatan langsung dengan kalkulasi duplikasi.
5. `new_medication_count`: Mengindikasikan penambahan resep baru yang berkorelasi artifisial.
6. `total_medication_count`: Penjumlahan langsung dari fitur-fitur adjacent di atas.

Jika ada permintaan API yang mencoba menyertakan salah satu dari 6 fitur terlarang ini, modul `InferenceGuard` akan langsung menolak proses kalkulasi (*fail-fast*) guna menjamin integritas saintifik hasil prediksi.

---

### 5.3 Model XGBoost & Kalibrasi Isotonik
- **Algoritma Terpilih:** **Extreme Gradient Boosting (XGBoost Classifier)**.
- **Alasan Pemilihan:** XGBoost menunjukkan performa diskriminasi risiko terbaik dibanding baseline Logistic Regression dan Random Forest pada data tabular klinis, dengan kemampuan menangani interaksi non-linear antara usia geriatri, komorbiditas ganda, dan akumulasi obat *High-Alert*.
- **Kalibrasi Probabilitas:** Karena pohon keputusan (*tree-based models*) cenderung menghasilkan probabilitas yang menumpuk di dekat nilai 0 dan 1, sistem menerapkan **Isotonic Regression Calibration**. Hal ini memastikan bahwa jika model mengeluarkan nilai probabilitas 0.70, maka secara empiris sekitar 70% dari kelompok pasien tersebut benar-benar memiliki ketidaksesuaian resep yang membutuhkan telaah.

---

### 5.4 Evaluasi Model & Baseline Comparison

Berdasarkan hasil uji pada dataset uji independen (*held-out test set* 15% pasien, $N = 4.744$ encounters):

| Metrik Evaluasi | Baseline LogReg | Random Forest | XGBoost Terkalibrasi (Aktif) |
| :--- | :--- | :--- | :--- |
| **ROC-AUC** | 0.8396 | 0.8891 | **0.8967** |
| **PR-AUC** | 0.9576 | 0.9696 | **0.9666** |
| **F1-Score** | 0.7879 | 0.8260 | **0.8410** |
| **Precision** | 0.9879 | 0.9715 | **0.9454** |
| **Recall** | 0.6552 | 0.7184 | **0.7574** |
| **Brier Score** | 0.1623 | 0.1386 | **0.1322** (Makin rendah makin baik) |
| **Top-20% Worklist Recall** | 0.2545 | 0.2545 | **0.2635** |

*Catatan Validasi:* Uji permutasi 1000-seed membuktikan bahwa sinyal prediksi model memiliki signifikansi statistik $p = 0.0000$ ($11.72\sigma$ di atas nilai acak), membuktikan bahwa pemeringkatan didorong oleh faktor klinis riil, bukan artefak data.

---

### 5.5 Explainability dengan TreeSHAP
Untuk mencegah fenomena *black box AI* yang membahayakan dalam dunia medis, setiap prediksi didampingi oleh penjelasan **SHAP (SHapley Additive exPlanations)**:
- Sistem menghitung kontribusi marjinal masing-masing dari 10 fitur terhadap peningkatan atau penurunan probabilitas risiko pasien.
- Frontend menerjemahkan nilai numerik SHAP menjadi bahasa klinis sederhana (misal: *"Jumlah komorbiditas aktif (4 penyakit) menyumbang +24% terhadap prioritas ulasan pasien ini"*).
- Apoteker dapat segera memahami alasan rasional di balik pemeringkatan sistem.

---

### 5.6 Analisis Track Ganda: `models/` vs `medrec_xgboost/`
Di dalam repositori saat ini terdapat dua direktori model:
1. **`models/` (Track Produksi Aktif):** Berisi `priomed_prioritization_model.pkl` (v0.3.0). Ini adalah model resmi yang terhubung dengan backend FastAPI, dilindungi oleh `InferenceGuard`, dan memiliki kontrak data yang telah lolos pengujian `pytest`.
2. **`medrec_xgboost/` (Track Riset Eksperimental):** Berisi notebook `xgboost_PrioMedRec.ipynb` dan output model `.joblib`. Track ini mengeksplorasi skema data Synthea yang lebih luas dengan jumlah fitur yang berbeda.
- **Rekomendasi Arsitektur:** Track `medrec_xgboost` **TIDAK BOLEH** langsung disalin atau ditimpa ke folder `models/` karena akan merusak kompatibilitas skema API FastAPI. Track ini harus diperlakukan sebagai lingkungan riset R&D terisolasi hingga dibuatkan modul adaptor khusus.

---

## 6. DOKUMENTASI INTEGRASI LANGFLOW & IBM BOB (MCP SERVER)

PrioMed-Rec mengadopsi arsitektur agen modern berbasis standar industri: visualisasi alur agen menggunakan **Langflow** dan integrasi asisten AI menggunakan **Model Context Protocol (MCP)** yang kompatibel dengan **IBM Bob**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AGENTIC & MCP INTEGRATION                          │
│                                                                             │
│   [IBM Bob / Copilot Client]                                                │
│              │                                                              │
│              ▼ (stdio MCP Protocol)                                         │
│     mcp_server.py (FastMCP)                                                 │
│              │                                                              │
│              ▼ (HTTP JSON-RPC)                                              │
│     FastAPI Backend (/prioritize/batch, /analyze, /review)                  │
│              ▲                                                              │
│              │ (Reverse Proxy / HTTP)                                       │
│   [Langflow Visual Orchestrator] ◄── [React Web Frontend]                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.1 Peran Langflow dalam Arsitektur
Langflow bertindak sebagai **Visual Orchestration Layer** yang menyusun pipa pemrosesan data klinis:
- Memungkinkan dokter, apoteker, dan perekayasa AI meninjau secara visual bagaimana data pasien mengalir dari input obrolan/permintaan web, diteruskan ke endpoint analisis, digabungkan dengan konteks prompt, hingga menghasilkan respons narasi.
- Memberikan fleksibilitas bagi pengembang untuk mengubah parameter LLM tanpa harus memodifikasi source code aplikasi web.

---

### 6.2 Alur Orkes Visual: Orchestrator vs Review Flows
Sistem menyediakan 2 template alur Langflow utama di folder `langflow/`:
1. **Flow A — `priomedrec_orchestrator.json` (ID: `ab69172c-78ec-45bd-85cd-83ddbcb6cc50`):**
   - Menerima `patient_id` dari antarmuka pengguna.
   - Melakukan panggilan HTTP POST ke endpoint FastAPI `/analyze`.
   - Mengambil data hasil prediksi ML, daftar diskrepansi, dan bendera keamanan.
   - Mengirimkan payload terstruktur ke modul prompt LLM untuk menyusun draf SBAR.
   - Mengembalikan respons envelope ke frontend.
2. **Flow B — `priomedrec_review.json` (ID: `e903f5fc-3a3e-4cd3-9773-dca76018f5a6`):**
   - Menerima aksi telaah akhir apoteker (`APPROVE`, `REJECT`, atau `EDIT`).
   - Meneruskan data ulasan ke endpoint FastAPI `/review` untuk dicatat ke database SQLite.
   - Mengembalikan konfirmasi status penyimpanan.

*Mekanisme Ketahanan Frontend:* Pada file `web/src/api/client.ts`, frontend dilengkapi logika proteksi: jika server Langflow belum diaktifkan atau mengalami gangguan jaringan, aplikasi secara transparan dan otomatis langsung mengalihkan panggilan ke backend FastAPI tanpa memunculkan error pada layar apoteker.

---

### 6.3 IBM Bob Integration via FastMCP (`mcp_server.py`)
Untuk menghubungkan PrioMed-Rec dengan platform asisten cerdas IBM Bob (atau klien MCP lainnya seperti Claude Desktop), repositori menyertakan file `mcp_server.py` yang dibangun di atas pustaka `FastMCP`:
- Server MCP berjalan menggunakan protokol komunikasi standar input/output (`stdio`).
- Terdaftar secara otomatis melalui file konfigurasi `mcp_settings.json`.

#### 3 Tools Auditable yang Disediakan untuk IBM Bob:
1. **`rank_admission_risk(patient_id: str, limit: int = 1)`:**
   - Meminta pemeringkatan prioritas admisi pasien ke FastAPI `/prioritize/batch`.
   - IBM Bob tidak menghitung skor sendiri, melainkan mengambil hasil komputasi model XGBoost.
2. **`detect_medication_discrepancy(patient_id: str, encounter_id: str, question: str)`:**
   - Meminta deteksi diskrepansi omisi dan duplikasi ke FastAPI `/analyze`.
   - Mengembalikan daftar temuan yang wajib diverifikasi apoteker.
3. **`record_pharmacist_review(case_id, pharmacist_id, action, ai_result, pharmacist_note, edited_result)`:**
   - Meneruskan tindakan persetujuan/penolakan apoteker ke FastAPI `/review`.

---

### 6.4 Prinsip Anti-Halusinasi & Zero Autonomous Action
Arsitektur MCP dan Langflow di PrioMed-Rec dikunci dengan prinsip keselamatan:
- **Server MCP tidak memiliki hak cipta model mandiri.** MCP server hanya bertindak sebagai jembatan (*bridge*) ke FastAPI.
- **Agen IBM Bob dilarang merevisi resep.** Agen hanya menyajikan opsi telaah untuk dipertimbangkan oleh apoteker manusia.
- Setiap entri telaah yang masuk melalui IBM Bob tetap diverifikasi oleh layer autentikasi dan dicatat identitasnya ke log audit.

---

## 7. ALUR KERJA END-TO-END (END-TO-END WORKFLOW)

Bagian ini menguraikan bagaimana PrioMed-Rec bekerja dalam alur pelayanan rumah sakit sehari-hari, menghubungkan fase penerimaan pasien hingga penyelesaian telaah rekonsiliasi.

### 7.1 Alur Makro Rumah Sakit (Admisi ke Pulang)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. ADMISI & UGD                                                             │
│    Pasien Masuk ──► Pendaftaran Admisi ──► Input Resep Admisi Baru (Dokter) │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. PENELUSURAN RIWAYAT OBAT (BPMH)                                          │
│    Wawancara Pasien/Keluarga ──► Input Obat Bawaan Rumah di Web PrioMed-Rec │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. REKONSILIASI OBAT ADMISI (TITIK FOKUS UTAMA PRIOMED-REC)                │
│    • ML XGBoost: Urutkan Antrean Berdasarkan Risiko (WHO FIRST)             │
│    • Rule Engine: Deteksi Omisi, Duplikasi, Interaksi (WHAT TO CHECK)       │
│    • LLM Copilot: Sajikan Draf Telaah SBAR Otomatis                         │
│    • Apoteker: Verifikasi Klinis & Komunikasi ke DPJP (WHAT TO DO)          │
│    • Audit Log: Rekam Keputusan Telaah (< 24 Jam Pasca-Admisi)              │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. PERAWATAN DI BANGSAL                                                     │
│    Pemberian Obat Terverifikasi (UDD) ──► Pemantauan Terapi Obat (PTO)      │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. PEMULANGAN PASIEN (DISCHARGE)                                            │
│    Rekonsiliasi Obat Pulang ──► Edukasi / Konseling Obat ke Pasien          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 7.2 Alur Mikro Apoteker dalam Aplikasi PrioMed-Rec

Ketika apoteker membuka aplikasi web PrioMed-Rec pada awal giliran jaga (*shift*):
1. **Langkah 1 (Skrining & Triage):**
   - Apoteker membuka menu **Worklist**.
   - Model XGBoost secara otomatis memeringkat puluhan pasien baru yang masuk bangsal.
   - Apoteker memfilter bangsal yang menjadi tanggung jawabnya (misal: Bangsal Penyakit Dalam).
   - Apoteker langsung memproses pasien teratas yang berlabel **HIGH PRIORITY**.
2. **Langkah 2 (Pengumpulan & Disposisi Obat Rumah):**
   - Apoteker mengklik pasien dan masuk ke menu **BPMH**.
   - Apoteker menginput obat yang diminum pasien sebelum masuk RS berdasarkan wawancara atau bukti kemasan fisik obat.
   - Apoteker menetapkan disposisi awal (`DILANJUTKAN`, `DITUNDA`, `DIGANTI`, atau `DIHENTIKAN`).
   - Apoteker menekan tombol simpan BPMH.
3. **Langkah 3 (Telaah Mendalam & Audit Diskrepansi):**
   - Apoteker masuk ke menu **Analisis Pasien**.
   - Sistem menampilkan skor risiko beserta grafik SHAP penyebab risiko.
   - Sistem menyajikan kartu diskrepansi: jika obat rutin di rumah tidak diresepkan kembali di admisi tanpa disposisi yang jelas, sistem menandainya sebagai `POTENTIAL_UNDOCUMENTED_OMISSION`.
   - Sistem menampilkan kartu peringatan jika ada obat berstatus *High-Alert*, *NTI*, atau interaksi berbahaya.
4. **Langkah 4 (Sintesis SBAR & Diskusi Interprofesional):**
   - Apoteker meninjau draf laporan klinis berstandar **SBAR** yang telah disusun oleh LLM terlindungi.
   - Apoteker menekan tombol **"1-Click Copy"** dan menghubungi Dokter DPJP (via telepon, WhatsApp resmi rumah sakit, atau catatan CPPT elektronik) untuk mengonfirmasi apakah penghentian obat disengaja atau tidak.
5. **Langkah 5 (Penyelesaian & Pencatatan Audit):**
   - Jika dokter mengonfirmasi resep telah disesuaikan: Apoteker menekan tombol **APPROVE**.
   - Jika dokter memberikan instruksi modifikasi tambahan: Apoteker menekan tombol **EDIT** lalu menambahkan catatan telaah.
   - Keputusan tersimpan secara permanen di menu **Audit Log**, memenuhi standar pelaporan akreditasi rumah sakit (Permenkes 72/2016).

---

### 7.3 Diagram Alur Data & State Machine Pasien

```
                 [Pasien Baru Masuk RS]
                           │
                           ▼
                 Status: Menunggu BPMH
                           │
               (Apoteker mengisi form BPMH)
                           │
                           ▼
                 Status: Siap dianalisis
                           │
             (Sistem mengeksekusi /analyze)
                           │
                           ▼
                Status: Perlu verifikasi
                           │
        ┌──────────────────┴──────────────────┐
        ▼                                     ▼
(Apoteker Setuju)                     (Apoteker Tolak)
        │                                     │
        ▼                                     ▼
 Status: Disetujui                     Status: Ditolak
        │                                     │
        └──────────────────┬──────────────────┘
                           │
                           ▼
                  [Tercatat di Audit Log]
```

---

## 8. EVALUASI KRITIS & GAP ANALYSIS (TEMUAN LAPANGAN)

Berdasarkan audit mendalam terhadap seluruh struktur file, logika kode, dan konteks pelayanan kesehatan di Indonesia, berikut adalah temuan kesenjangan (*gaps*) yang perlu diperhatikan sebelum sistem diimplementasikan di rumah sakit nyata:

### 8.1 Kesenjangan Standar Data (Synthea US EHR vs Kemenkes / SIMRS)
- **Kondisi Saat Ini:** Pipeline saat ini dilatih menggunakan dataset sintetis Synthea berbasis standar kode medis Amerika Serikat (RxNorm untuk obat, SNOMED CT untuk diagnosis, LOINC untuk lab).
- **Tantangan Rumah Sakit Indonesia:** SIMRS di Indonesia menggunakan format penamaan lokal bebas (*free-text*) atau kode formularium lokal yang kini sedang distandarisasi oleh Kementerian Kesehatan RI melalui **Kamus Farmasi dan Alat Kesehatan (KFA)** serta platform **SatuSehat (HL7 FHIR)**.
- **Dampak:** Fungsi pencocokan string obat pada `medication_normalizer.py` membutuhkan penambahan tabel alias lokal agar dapat mengenali nama dagang obat di Indonesia (misalnya: *Amaryl* $\rightarrow$ *Glimepiride*, *Plavix* $\rightarrow$ *Clopidogrel*).

### 8.2 Sinkronisasi Dual ML Track
- **Kondisi Saat Ini:** Terdapat dua jalur ML yang terpisah: pipeline produksi aktif di `src/models/` + `models/` (XGBoost 10 fitur aman) dan sandbox riset di `medrec_xgboost/` (notebook eksperimen dengan skema dataset yang lebih luas).
- **Tantangan:** Adanya dua track yang berbeda berpotensi membingungkan tim pengembang jika sewaktu-waktu seseorang secara keliru menyalin artefak `.joblib` dari folder `medrec_xgboost/` ke folder produksi `models/`, yang dapat menyebabkan *InferenceGuard Error* atau *Schema Mismatch*.
- **Solusi:** Harus ada penegasan batas arsitektur bahwa `medrec_xgboost` adalah modul eksperimental independen, atau segera dibuatkan adapter schema terpadu.

### 8.3 Kesiapan Infrastruktur Rumah Sakit (On-Premise vs Cloud)
- **Kondisi Saat Ini:** Penyusunan narasi SBAR LLM mengandalkan API cloud eksternal (Google AI Studio Gemini / Groq).
- **Tantangan:** Banyak rumah sakit pemerintah atau daerah memiliki regulasi ketat mengenai kerahasiaan data medis (*data sovereignty*) yang melarang data pasien keluar dari jaringan lokal (*air-gapped intranet*), meskipun data telah dianonimkan oleh modul `anonymizer.py`.
- **Solusi:** Sediakan opsi menjalankan LLM lokal berbobot ringan di server on-premise rumah sakit (seperti Ollama LLaMA 3.1 8B atau Gemma 2 9B lokal) sebagai penyedia cadangan internal.

### 8.4 User Acceptance & Alert Fatigue
- **Kondisi Saat Ini:** Mesin aturan menandai seluruh omisi dan potensi duplikasi.
- **Tantangan:** Jika terlalu banyak bendera peringatan sepele yang muncul untuk obat-obat non-esensial (misalnya suplemen vitamin atau tetes mata pelembap), apoteker dapat mengalami kelelahan peringatan (*alert fatigue*) dan mulai mengabaikan seluruh saran sistem secara refleks (*alert overriding*).
- **Solusi:** Perlu implementasi pembobotan keparahan diskrepansi (*Severity Tiering*): pisahkan diskrepansi obat kritis (*Critical/High Risk*) dengan obat pendukung (*Low Risk/Supportive*).

---

## 9. MASUKAN, SARAN, & ROADMAP PENYEMPURNAAN (LANGKAH DEMI LANGKAH)

Untuk membawa PrioMed-Rec dari fase prototipe matang menuju sistem yang siap digunakan apoteker secara nyata di bangsal rumah sakit, disarankan mengadopsi roadmap 4 tahap berikut:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ROADMAP IMPLEMENTASI PRODUKSI                         │
│                                                                             │
│ [Fase 1: Hardening] ──► [Fase 2: Standarisasi KFA] ──► [Fase 3: Shadow Pilot] ──► [Fase 4: SIMRS Enterprise] │
│   (1 - 2 Bulan)              (2 - 3 Bulan)                 (3 - 4 Bulan)               (4 - 6 Bulan)         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### FASE 1: Hardening & Konsolidasi Internal (Jangka Pendek, 1–2 Bulan)
1. **Unifikasi Track Machine Learning:**
   - Evaluasi apakah model di `medrec_xgboost/` memiliki performa lebih unggul dari `models/` v0.3.0.
   - Jika iya, buatkan modul konversi schema dan jalankan uji validasi `pytest tests/test_model.py`.
   - Jika tidak, dokumentasikan `medrec_xgboost/` secara resmi sebagai arsip eksperimental agar pengembang baru tidak bingung.
2. **Penyempurnaan Penanganan Kesalahan Jaringan di UI:**
   - Pada halaman `WorklistPage.tsx` dan `PatientAnalysisPage.tsx`, lengkapi tampilan pesan kesalahan dengan tombol *Retry/Muat Ulang* otomatis jika server API atau koneksi lokal sempat terputus.
3. **Penyelarasan Tipe Data Antarmuka:**
   - Pastikan seluruh interface pada `web/src/types/clinical.ts` 100% konsisten dengan skema Pydantic di `api/schemas.py`.

---

### FASE 2: Standarisasi Data Indonesia & Kemenkes KFA (Jangka Menengah, 2–3 Bulan)
1. **Integrasi Kamus Farmasi dan Alat Kesehatan (KFA) Kemenkes:**
   - Tambahkan modul pemetaan kode KFA pada `src/rules/medication_normalizer.py`.
   - Dengan kode KFA, sistem dapat memetakan nama dagang obat generik berlogo (OGB) maupun obat paten di Indonesia ke dalam kelas terapi ATC secara otomatis.
2. **Hierarki Peringatan Berbobot (Severity Tiering):**
   - Tambahkan klasifikasi dampak klinis pada `configs/discrepancy_rules.json`:
     - *Tier 1 (Kritis):* Omisi obat kardiovaskular, antikoagulan, insulin, antikonvulsan.
     - *Tier 2 (Signifikan):* Omisi antibiotik, antihipertensi non-kritis.
     - *Tier 3 (Minor):* Omisi vitamin, suplemen, obat simtomatik ringan.
   - Hal ini akan mencegah *alert fatigue* apoteker secara drastis.
3. **Opsi Local LLM via Ollama:**
   - Tambahkan opsi provider `ollama` pada `api/services/llm_service.py` untuk rumah sakit yang mewajibkan zero-internet connectivity.

---

### FASE 3: Shadow Testing & Clinical Pilot di RS Pendidikan (Pra-Produksi, 3–4 Bulan)
1. **Metode Retrospective Shadow Testing:**
   - Uji sistem menggunakan 500–1.000 data rekam medis historis teranonimasi di rumah sakit mitra pendidikan.
   - Bandingkan urutan triase PrioMed-Rec dengan catatan intervensi riil apoteker masa lalu.
   - Hitung metrik keberhasilan: Berapa banyak diskrepansi berbahaya yang berhasil diprioritaskan di kuartil teratas ($Top-20\%$).
2. **Uji Kegunaan Lapangan (*Usability Testing*):**
   - Lakukan uji coba langsung bersama 5–10 apoteker klinis menggunakan skrip panduan di `docs/usability_test_script.md`.
   - Ukur skor kemudahan penggunaan menggunakan kuesioner baku *System Usability Scale (SUS)* (target skor $> 80$).
   - Catat umpan balik apoteker terkait kenyamanan antarmuka web, kecepatan copy SBAR, dan kejelasan grafik SHAP.

---

### FASE 4: Integrasi Penuh SIMRS & SatuSehat (Enterprise Ready, 4–6 Bulan)
1. **Konektivitas HL7 FHIR Bridge:**
   - Bangun REST API listener berbasis HL7 FHIR untuk menerima event pendaftaran pasien admisi baru (`Encounter` status `in-progress`).
   - Ekstrak daftar resep otomatis dari resource `MedicationRequest` dan riwayat obat dari `MedicationStatement`.
2. **Kirim Balik Rekomendasi SBAR ke CPPT SIMRS:**
   - Sediakan tombol kirim langsung (*Direct EMR Injection*) yang memasukkan teks SBAR yang telah disetujui apoteker ke modul CPPT SIMRS rumah sakit melalui API internal.
3. **Peningkatan Database Enterprise:**
   - Migrasikan layer persistensi dari SQLite ke **PostgreSQL** dengan replikasi aktif jika sistem diakses bersamaan oleh lebih dari 50 apoteker klinis di berbagai gedung rawat inap.

---

## 10. KESIMPULAN & PENUTUP

Proyek **PrioMed-Rec** telah memiliki landasan arsitektur perangkat lunak, dasar klinis, dan integritas data yang luar biasa matang. Repositori ini bukan sekadar prototipe antarmuka main-main, melainkan sistem *Clinical Decision Support* hibrida yang dirancang dengan pertimbangan keselamatan pasien yang sangat mendalam:

1. **Integritas Machine Learning Teruji:** Pemisahan ketat antara 10 `SAFE_FEATURES` dan 6 `FORBIDDEN_FEATURES` via `InferenceGuard` membuktikan komitmen saintifik bebas data leakage, dengan performa XGBoost ROC-AUC 0.897 dan kalibrasi isotonik yang valid.
2. **Arsitektur Hibrida Seimbang:** Penerapan prinsip *"AI decides WHO FIRST, Rules surface WHAT TO CHECK, Pharmacist decides WHAT TO DO"* adalah formulasi paling aman dan realistis untuk adopsi teknologi kesehatan di rumah sakit.
3. **Ketahanan Multi-Lapis:** Dukungan fallback multi-penyedia LLM, 6 lapis guardrail anti-halusinasi, antarmuka web modern React/Vite yang cepat, serta integrasi standar terbuka MCP untuk IBM Bob dan Langflow menjadikan sistem ini sangat adaptif terhadap perkembangan teknologi masa depan.

Dengan mengikuti roadmap penyempurnaan di atas—khususnya standarisasi kamus obat Indonesia (KFA) dan uji coba retrospektif di rumah sakit pendidikan—PrioMed-Rec berpeluang besar menjadi solusi pelopor rekonsiliasi obat digital di Indonesia yang secara nyata memangkas beban kerja apoteker dan menyelamatkan nyawa pasien dari risiko kesalahan obat.

---
*Dokumen ini disusun sebagai aset dokumentasi resmi dan panduan perancangan end-to-end bagi tim pengembang dan pemangku kepentingan klinis proyek PrioMed-Rec.*
