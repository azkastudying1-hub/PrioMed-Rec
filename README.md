# PrioMed-Rec

> **AI-assisted Admission Medication Reconciliation Prioritization for Clinical Pharmacists**

> **Website-first:** antarmuka yang didukung adalah React/Vite di `web/`, dengan FastAPI sebagai backend. Streamlit bukan bagian runtime proyek ini. Panduan terbaru: [`docs/WEBSITE_RUNBOOK.md`](docs/WEBSITE_RUNBOOK.md).

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-1.1.0-009688)]()
[![Tests](https://img.shields.io/badge/tests-518%20passed-brightgreen)]()
[![Model](https://img.shields.io/badge/model-0.3.0--labels--3.0.0-orange)]()
[![LLM](https://img.shields.io/badge/LLM-Gemini%20%7C%20Groq%20%7C%20AutoFallback-purple)]()

---

## 📌 Apa Itu PrioMed-Rec?

**PrioMed-Rec** adalah sistem *clinical decision support* berbasis AI yang membantu **farmasis rumah sakit** dalam proses **admission medication reconciliation** — yaitu menentukan **urutan prioritas (priority queue)** puluhan hingga ratusan pasien rawat inap yang harus direview terlebih dahulu ketika kapasitas farmasis terbatas.

> ⚠️ **PrioMed-Rec TIDAK mentriage pasien untuk perawatan medis darurat.**  
> Sistem ini memprioritaskan **urutan review rekonsiliasi obat** oleh farmasis — bukan menentukan siapa yang mendapat perawatan darurat medis terlebih dahulu.

### Masalah
Farmasis harus memverifikasi resep puluhan/ratusan pasien rawat inap setiap hari. Tanpa sistem pemeringkatan:
- Pasien dengan risiko ketidaksesuaian resep (*medication discrepancy*) tinggi bisa terlewat.
- Waktu farmasis terbuang untuk pasien dengan risiko discrepancy rendah.
- Potensi kesalahan obat (*omisi*, *duplikasi*) baru terdeteksi secara lambat.

### Solusi
PrioMed-Rec secara otomatis:
1. **Peringkat Massal (Batch Prioritization)**: Memeringkat daftar puluhan hingga ratusan pasien secara simultan berdasarkan *Predicted Discrepancy Likelihood*.
2. **Prioritaskan Review**: Pengelompokan tingkat prioritas (*HIGH / MEDIUM / LOW*).
3. **Deteksi Diskrepansi Otomatis**: Mengidentifikasi diskrepansi deterministik via Rule Engine (*OMISSION*, *DUPLICATION*).
4. **Laporan Klinis SBAR (Situation, Background, Assessment, Recommendation)**: Menyusun draf telaah klinis formal berstandar SBAR siap telaah bagi apoteker, baik secara otomatis via LLM maupun via *rule-based fallback*.
5. **Multi-Provider LLM & Auto-Fallback**: Sistem secara otomatis mengalihkan penyusunan narasi LLM (Gemini 2.5 Flash $\rightarrow$ Gemini 1.5 Flash 8b $\rightarrow$ Groq Llama 3.3 70B) jika terjadi batasan kuota API (429/503).

---

## 💡 Fitur Unggulan Sistem

- **📋 Tab 1: Ranked Priority Queue (Worklist Pasien)**  
  Menampilkan tabel urutan kerja (*worklist*) puluhan/ratusan pasien yang diprioritaskan otomatis dari risiko tertinggi hingga terendah, dilengkapi filter tingkat prioritas, status polifarmasi, dan ringkasan KPI.
- **🔍 Tab 2: Analisis Detail 1 Pasien & Draf SBAR**  
  Menampilkan hasil analisis mendalam 1 pasien yang dipilih, mencakup skor risiko, grafik kontribusi fitur SHAP, kartu diskrepansi obat, dan laporan Draf SBAR lengkap dengan tombol 1-click copy.
- **🛡️ Resilience & Auto-Fallback LLM**  
  Layanan LLM dilengkapi proteksi *exponential backoff* dan rantai pencadangan (*multi-provider fallback*) tanpa perlu menghentikan atau merestart aplikasi.

---

## 🏗️ Arsitektur & Alur Kerja

```
 React/Vite Website (UI Worklist, BPMH, Analisis, Audit)
        │
        ├──> POST /prioritize/batch ──> XGBoost (Batch Ranking N Pasien)
        │
        └──> POST /analyze ──> InferenceGuard (Safe Features Only)
                                  ├──> XGBoost Model + SHAP Explainer
                                  ├──> Rule Engine (Omission & Duplication)
                                  └──> LLM Service (Auto-Fallback: Gemini / Groq)
                                            └──> Draf Laporan Klinis SBAR
```

---

## 🚀 Langkah Menjalankan Proyek

### 1. Prasyarat System
- Python 3.10+ (disarankan Python 3.12)
- Git installed

### 2. Clone & Setup Environment
```bash
git clone https://github.com/azkastudying1-hub/PrioMed-Rec.git
cd PrioMed-Rec

# Buat virtual environment
python -m venv .venv

# Aktivasi virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# Install dependensi
pip install -r requirements.txt
```

### 3. Setup File Konfigurasi (.env)
Salin file konfigurasi contoh:
```bash
# Windows:
copy .env.example .env
# Linux / macOS:
# cp .env.example .env
```

Isi file `.env` dengan API Key Anda (Dapatkan API Key gratis di [Google AI Studio](https://aistudio.google.com/app/apikey) dan/atau [Groq Console](https://console.groq.com)):
```env
LLM_PROVIDER=gemini
LLM_API_KEY=your_provider_key_here
LLM_MODEL_NAME=gemini-2.5-flash
LLM_FALLBACK_MODEL=gemini-1.5-flash-8b
LLM_GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
LLM_GROQ_MODEL=llama-3.3-70b-versatile
```

### 4. Menjalankan Layanan

#### A. Jalankan Backend FastAPI (Port 8000)
```bash
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
- Dokumentasi API Swagger: `http://localhost:8000/docs`
- Healthcheck Endpoint: `http://localhost:8000/health`

#### B. Jalankan Frontend Website React (Port 5173)
Buka terminal baru (pastikan virtualenv aktif) dan jalankan:
```bash
cd web
npm ci
# PowerShell
$env:VITE_DATA_MODE="live"
npm run dev
```
Akses dashboard di browser: `http://localhost:5173`

---

## 🧪 Pengujian Unit & Integrasi (Test Suite)

Seluruh komponen API, ML Guardrails, Rule Engine, dan skenario LLM telah diuji dan diverifikasi secara komprehensif:

```bash
# Menjalankan seluruh test suite (44/44 passed)
.\.venv\Scripts\python.exe -m pytest tests/test_api.py -v
```

---

## 📁 Struktur Repositori

```
PrioMed-Rec/
├── api/                        # FastAPI Router, Services, dan Schema API
│   ├── routes/                 # Endpoint (/analyze, /prioritize, /discrepancies, dll)
│   ├── services/               # Logic Prioritisasi, Patient Resolver, LLM Wrapper
│   └── schemas.py              # Pydantic Schemas
├── configs/                    # Rule Engine & Model Thresholds JSON
├── docs/                       # Dokumentasi Arsitektur, API Contract, Model Card
├── models/                     # Artifact Model XGBoost, Manifest Fitur & Metadata
├── src/                        # Core ML, Feature Engineering, Rule Engine, & LLM Prompting
│   ├── data/                   # Patient Resolver & Data Loader
│   ├── llm/                    # Service LLM, Prompt Templates SBAR, & Guardrail Validators
│   ├── models/                 # Inference Guard & Prediction Engine
│   └── rules/                  # Discrepancy Rule Evaluator
├── web/                        # Frontend React/Vite untuk website
│   ├── src/pages/              # Worklist, BPMH, Analisis, Audit, Settings
│   └── src/api/                # Kontrak HTTP menuju FastAPI
├── tests/                      # Unit & Integration Tests (pytest)
├── .env.example                # Template File Environment
├── .gitignore                  # Konfigurasi Ignored Files untuk Git
├── requirements.txt            # Dependensi Python
└── README.md                   # Dokumentasi Utama Proyek
```

---

## ⚠️ Disclaimer & Safety Notice

1. **PrioMed-Rec adalah Decision-Support Prototype**: Sistem ini ditujukan sebagai alat bantu pengambilan keputusan (*clinical decision support*), **bukan** pengganti profesional kesehatan.
2. **Human-in-the-Loop Wajib**: Setiap hasil rekomendasi, prioritas, dan draf laporan SBAR **wajib diverifikasi** oleh apoteker klinis sebelum keputusan medis final dibuat.
3. **Data Sintetis**: Model dikembangkan dan diuji menggunakan kumpulan data sintetis (Synthea) untuk keperluan demonstrasi dan riset.
