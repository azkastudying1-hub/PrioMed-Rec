# PrioMed-Rec — Dokumentasi Analisis End-to-End & Peran Langflow

**Versi dokumen:** 1.0  
**Tanggal:** 29 Oktober 2026  
**Lingkup:** seluruh repositori `D:\Hacktiv8\priomed-rec` — frontend, backend, domain core, ML, database, antrean, audit, MCP, dan Langflow.  
**Sifat:** dokumen analisis teknis + rekomendasi maksimisasi Langflow. Bukan dokumen validasi klinis.

> **Cara membaca:** bagian 1–8 menjelaskan sistem apa adanya (as-is). Bagian 9–11 menjelaskan peran Langflow saat ini, apa yang dapat digantikan/dimaksimalkan, roadmap, risiko, dan temuan. Bagian 12 berisi lampiran operasional.

---

## 1. Ringkasan Eksekutif

### 1.1 Identitas produk

| Item | Nilai |
|---|---|
| Nama | **PrioMed-Rec** |
| Kategori | Clinical decision support — **prioritas telaah rekonsiliasi obat admisi** |
| Pengguna utama | Apoteker klinis, teknisi farmasi, koordinator farmasi, admin, auditor |
| Masalah | Kapasitas apoteker terbatas; pasien berisiko diskrepansi obat bisa terlewat |
| Solusi | Peringkat risiko diskrepansi (XGBoost + aturan deterministik + SLA), temuan diskrepansi, draf SBAR, copilot, antrean kerja, audit |
| Batasan penting | **Bukan triase medis darurat**; bukan diagnosis; bukan penentu terapi; keputusan akhir tetap pada apoteker |
| UI resmi | React 19 + Vite + Tailwind (`web/`) |
| Backend | FastAPI (`api/`) + SQLAlchemy/SQLite + APScheduler |
| Inti deterministik | Paket `priomedrec_core/` (prioritas, antrean, kontrak, pipeline) |
| Orkestrasi AI | Langflow 1.13.0 (Docker), **opsional** dan saat ini baru mencakup sebagian kecil pipeline |
| Integrasi agent | `mcp_server.py` (FastMCP) untuk IBM Bob / MCP client |
| Model | XGBoost `model-0.3.0`, label `labels-3.0.0`, fitur `features-0.3.0` |

### 1.2 Status snapshot (terverifikasi pada 29-10-2026)

| Aspek | Status | Bukti/catatan |
|---|---|---|
| Tes Python terkumpul | **562 tes** | `pytest --collect-only -q` |
| Build frontend | **GAGAL** | `npx tsc -b` → 4 error sintaks di `web/src/api/client.ts` baris 38–40, 59 |
| Runtime Langflow | **BELUM TERVERIFIKASI** | Docker daemon tidak tersedia; lihat `docs/LANGFLOW_VERIFICATION.md` |
| Flow target 00–06 | **Belum ada** | Yang ada hanya 3 flow lama/eksperimental |
| Cakupan Langflow pipeline | **≈10%** (1 dari 10 langkah) | Langflow terutama membungkus panggilan HTTP ke FastAPI |
| Streamlit | **Legacy, masih ada di repo** | `streamlit_app/` (7 file) + `tests/test_streamlit.py` (20 tes); bukan jalur UI yang didukung |
| Dokumentasi arsitektur | **Sebagian usang** | `docs/architecture.md` masih menyebut Streamlit sebagai UI utama |

### 1.3 Tiga kesimpulan utama

1. **Produk sudah berjalan sebagai sistem website-first** dengan inti deterministik yang kuat: ML + aturan + prioritas + antrean + audit hash-chain + RBAC. Nilai keselamatan utamanya tidak bergantung pada LLM.
2. **Langflow saat ini belum menjadi mesin orkestrasi utama.** Ia baru menjadi pembungkus tipis: flow memanggil endpoint FastAPI (`/analyze`, `/review`) atau AI Gateway. Pipeline nyata tetap di `api/services` dan `src/`.
3. **Untuk memaksimalkan Langflow tanpa menurunkan keselamatan**, logika deterministik harus diekstrak ke `priomedrec_core` (pure Python), lalu dipakai bersama oleh dua jalur: **flow Langflow** dan **fallback lokal**, dengan **uji paritas** dan **output verifier** di FastAPI.

---

## 2. Peta Repositori & Inventaris

### 2.1 Struktur tingkat atas

```text
priomed-rec/
├── api/                     FastAPI: routes, services, auth, db, tasks
├── priomedrec_core/         Inti deterministik: kontrak, prioritas, antrean
├── src/                     Kode ML/LLM/rule engine lama yang masih dipakai sebagian
├── models/                  Artefak model + metadata + evaluasi
├── configs/                 Aturan diskrepansi, alergi, high-alert, threshold
├── knowledge/               Alias obat, interaksi obat
├── prompts/                 Prompt SBAR & copilot (versi)
├── langflow/                Flow JSON + komponen kustom PMR
├── web/                     React/Vite UI
├── tests/                   Tes Python (562 tes terkumpul)
├── docs/                    Dokumen teknis, runbook, audit, decision log
├── scripts/                 Validasi data, utilitas
├── simulator/               Simulator antrean/kapasitas
├── medrec_xgboost/          MVP XGBoost terisolasi (kontrak berbeda)
├── streamlit_app/           UI lama (legacy, bukan jalur resmi)
├── alembic/                 Migrasi database
├── mcp_server.py            FastMCP server untuk IBM Bob/MCP
├── docker-compose.yml       API + Langflow
├── Dockerfile.api
├── Dockerfile.langflow
└── requirements.txt
```

### 2.2 File penting per lapisan

| Lapisan | File | Fungsi |
|---|---|---|
| **UI** | `web/src/App.tsx` | Routing halaman, mode data, idle lock, login gate |
| | `web/src/pages/WorklistPageV2.tsx` | Worklist v1 (antrean baru) |
| | `web/src/pages/QueuePage.tsx` | Antrean berbasis queue engine |
| | `web/src/pages/CaseWorkspacePage.tsx` | Ruang kerja kasus: bandingkan, temuan, SBAR, riwayat |
| | `web/src/pages/PatientAnalysisPage.tsx` | Analisis pasien, SHAP, SBAR, safety flags |
| | `web/src/pages/BpmhPage.tsx` | Input BPMH |
| | `web/src/pages/AuditLogPageV2.tsx` | Audit log + verifikasi rantai |
| | `web/src/pages/SettingsPage.tsx` | Konfigurasi high-alert |
| | `web/src/pages/DashboardPage.tsx` | KPI/ringkasan |
| | `web/src/pages/CommandCenterPage.tsx` | Command center antrean |
| | `web/src/components/queue/*` | Komponen antrean (tier, SLA, klaim, aging) |
| | `web/src/lib/apiClient.ts` | Klien API terautentikasi (Bearer + refresh) |
| | `web/src/api/langflow.ts` | AI Gateway client (bukan Langflow langsung) |
| **API** | `api/main.py` | Aplikasi FastAPI, mount router legacy + `/api/v1`, SPA |
| | `api/routes/*.py` | Endpoint legacy (kompatibilitas) |
| | `api/routes/v1/*.py` | Endpoint versi baru |
| **Layanan** | `api/services/analysis_orchestrator.py` | Pilih jalur Langflow vs lokal |
| | `api/services/langflow_client.py` | HTTP client + circuit breaker |
| | `api/services/output_verifier.py` | Validasi ulang hasil Langflow |
| | `api/services/llm_chain_service.py` | Rantai fallback LLM + template |
| | `api/services/guardrail_service.py` | 9 cek guardrail |
| | `api/services/normalizer_service.py` | Normalisasi nama obat 5 tahap |
| | `api/services/queue_service.py` | Operasi antrean |
| | `api/services/sla_service.py` | Perhitungan/eskalasi SLA |
| | `api/services/audit_service.py` | Audit hash-chain |
| | `api/services/case_state_service.py` | State machine kasus |
| | `api/services/priority_service.py` | Komposisi prioritas |
| | `api/services/discrepancy_service.py` | Rule engine diskrepansi |
| **Core** | `priomedrec_core/contracts.py` | Kontrak `AnalysisInput`, `AnalysisResult`, `Medication` |
| | `priomedrec_core/pipeline.py` | `run_phase_a`, `run_phase_b`, `run_full` |
| | `priomedrec_core/priority.py` | `compute_priority` = max(ML, rules, SLA, current) |
| | `priomedrec_core/queue_config.py` | Bobot, kuota, SLA, lease (berversi) |
| | `priomedrec_core/queue_engine.py` | Skor 0–100, tier, kuota, histeresis |
| | `priomedrec_core/queue_transitions.py` | Transisi status antrean |
| **Data/ML** | `models/priomed_prioritization_model.pkl` | Model terlatih |
| | `models/priomed_prioritization_model_calibrated.pkl` | Model terkalibrasi |
| | `models/metadata.json` | Versi model/fitur/label + forbidden features |
| | `models/thresholds.json` | Threshold HIGH 0.7 / MEDIUM 0.4 |
| | `configs/model_thresholds.json` | Threshold prioritas 0.7 / 0.4 |
| | `configs/discrepancy_rules.json` | Aturan tier 1/2/3 + high-alert |
| | `configs/allergy_rules.json` | Aturan reaksi silang alergi (DRAFT) |
| | `knowledge/drug_alias.csv` | 257 baris alias obat |
| | `knowledge/interactions.json` | 10 entri interaksi obat |
| **Langflow** | `langflow/components/priomedrec/*.py` | 19 adapter komponen PMR |
| | `langflow/priomedrec_orchestrator.json` | Flow orkestrator (8 node) |
| | `langflow/priomedrec_review.json` | Flow review (5 node) |
| | `langflow/priomedrec_agentic_v2.json` | Flow agentic eksperimental (15 node) |
| **Infra** | `docker-compose.yml` | API + Langflow, env hardening |
| | `Dockerfile.api` | Image API |
| | `Dockerfile.langflow` | Image Langflow 1.13.0 |
| | `.env.example` | Konfigurasi contoh |
| **MCP** | `mcp_server.py` | 5 tool FastMCP → FastAPI |

### 2.3 Artefak yang perlu diperhatikan

- `langflow/requirements.langflow.txt` **kosong** → komponen yang membutuhkan `xgboost`, `shap`, atau dependensi lain belum tentu tersedia di image Langflow.
- `langflow/components/priomedrec/__pycache__/` ikut terbawa di repo (sebaiknya di-*ignore*).
- `streamlit_app/` dan `tests/test_streamlit.py` masih ada meskipun README menyatakan Streamlit bukan runtime resmi.
- `medrec_xgboost/` adalah lintasan ML terpisah dengan skema lebih luas; **jangan** menyalin modelnya ke `models/` tanpa adapter dan validasi.

---

## 3. Arsitektur Sistem

### 3.1 Diagram runtime

**Mode pengembangan (local):**

```text
Browser (http://localhost:5173)
   │  /api/*      → Vite proxy → FastAPI (http://localhost:8000)
   │  /api/v1/*   → Vite proxy → FastAPI (path dipertahankan)
   ▼
FastAPI
   ├── Auth/RBAC (JWT)
   ├── ML (XGBoost + SHAP)
   ├── Rule engine + safety flags + interaksi + alergi
   ├── Priority composer + queue engine + SLA
   ├── SQLite (state, audit hash-chain)
   ├── LLM chain (Gemini → Groq → watsonx → Ollama → template)
   └── LangflowClient ──HTTP──► Langflow (http://localhost:7860)  [opsional]
```

**Mode Docker:**

```text
Browser → Nginx/SPA (port 80) → /api → FastAPI container (8000)
                                         └──► Langflow container (7860, hanya internal/host-local)
```

### 3.2 Alur data tingkat tinggi

```text
Admisi pasien
   │
   ├─(A) Antrean: encounter masuk → triage ML/aturan → queue_entries
   │
   └─(B) Analisis kasus:
          BPMH + order + alergi + konteks
             → normalisasi obat
             → Fase A: fitur aman → XGBoost → probabilitas → tier ML
             → Fase B: rule engine → temuan + safety flags + DDI + alergi
             → priority composer: max(ML, rules, SLA, current)
             → SBAR (LLM + guardrail, atau template deterministik)
             → output verifier (jika jalur Langflow)
             → analysis_runs + discrepancies
             → Worklist / Case Workspace
             → Apoteker: APPROVE / EDIT / REJECT / ESCALATE
             → audit_entries (hash-chain) + status_history
```

### 3.3 Batas kepercayaan (trust boundaries)

| Batas | Aturan |
|---|---|
| Browser ↔ FastAPI | JWT Bearer; browser **tidak pernah** memegang kunci Langflow/LLM |
| FastAPI ↔ Langflow | Hanya server-side; API key di env; timeout + retry + circuit breaker |
| Langflow ↔ data klinis | Langflow **stateless** untuk data klinis; penyimpanan permanen di FastAPI |
| LLM ↔ fakta klinis | LLM hanya menarasikan konteks terstruktur; tidak mendeteksi/mengarang fakta |
| Apoteker ↔ keputusan | Keputusan akhir selalu manusia; label "Draf AI — wajib diverifikasi apoteker" permanen |

### 3.4 Mode data frontend

| Mode | Nilai env | Perilaku |
|---|---|---|
| Synthetic | `VITE_DATA_MODE=synthetic` (default) | Memakai data mock `web/src/data/clinicalData.ts` |
| Live | `VITE_DATA_MODE=live` | Memanggil FastAPI; login diwajibkan |
| Auth | `VITE_AUTH_REQUIRED` | Menampilkan `LoginPage` bila aktif atau mode live |

---

## 4. Frontend (React/Vite)

### 4.1 Stack & build

- React 19, React Router 7, TanStack Query 5, Zustand 5, Zod 4, Tailwind 4, Lucide.
- Build: `npm run build` = `tsc -b && vite build`.
- Dev server: port 5173, proxy `/api`, `/api/v1`, dan `/langflow` (proxy `/langflow` adalah sisa lama; klien AI resmi memakai `/api/v1`).
- Output build: `web/dist/`, di-*serve* oleh FastAPI melalui `StaticFiles`.

### 4.2 Routing & halaman

`App.tsx` memakai state `page` (bukan URL router murni) dengan `PageId`:

| Halaman | Fungsi | Catatan |
|---|---|---|
| `worklist` | Daftar kerja pasien | `WorklistPageV2` (v1 API) atau `WorklistPage` (legacy) |
| `queue` | Antrean berbasis queue engine | `QueuePage`; klik item → `CaseWorkspacePage` |
| `command_center` | Ringkasan operasional | `CommandCenterPage` |
| `analysis` | Analisis satu pasien | `PatientAnalysisPage` |
| `bpmh` | Input BPMH | `BpmhPage` |
| `audit` | Audit log | `AuditLogPageV2` atau `AuditLogPage` |
| `settings` | Konfigurasi high-alert | `SettingsPage` |
| `tutorial` | Panduan | `TutorialPage` |
| login | Autentikasi | `LoginPage` |

### 4.3 Komponen kunci

| Komponen | Peran |
|---|---|
| `TierBadge` | Menampilkan HIGH/MEDIUM/LOW + sumber tier |
| `SlaCountdown` | Hitung mundur SLA |
| `AiDraftLabel` | Label wajib "Draf AI — wajib diverifikasi apoteker" |
| `ReviewActionBar` | Aksi APPROVE/EDIT/REJECT/ESCALATE/DRAFT_REVIEW |
| `HighAlertConfirmModal` | Konfirmasi eksplisit untuk obat high-alert |
| `CopilotDrawer` | Tanya-jawab AI melalui `/api/v1/ai/copilot` |
| `IdleLockOverlay` | Kunci layar otomatis saat idle |
| `queue/AgingStrip` | Distribusi umur antrean |
| `queue/MyClaimedPanel` | Kasus yang diklaim pengguna |
| `queue/QueueEntryRow` | Baris antrean |
| `queue/TierSourceBadge` | Sumber tier (ML/RULE/SLA) |
| `queue/UpdateBanner` | Notifikasi pembaruan |
| `queue/WardQueuePanel` | Antrean per bangsal |

### 4.4 Autentikasi & sesi

- `web/src/lib/auth.ts` + `lib/apiClient.ts`: access token Bearer, refresh otomatis saat 401, penyimpanan sesi.
- `App.tsx`: bila `AUTH_REQUIRED` atau `DATA_MODE=live`, tampilkan `LoginPage`.
- `IdleLockOverlay`: kunci sesi setelah idle; mengurangi risiko akses tidak sah di workstation bersama.
- RBAC di backend: `PHARMACIST`, `TECHNICIAN`, `COORDINATOR`, `ADMIN`, `AUDITOR`.

### 4.5 Alur UI utama

**Worklist → Kasus:**

```text
Worklist/Queue
  → pilih encounter
  → CaseWorkspacePage
      ├─ Tab Bandingkan: BPMH vs order admisi
      ├─ Tab Temuan: diskrepansi + safety flags + interaksi
      ├─ Tab SBAR: draf AI + label + tombol review
      └─ Tab Riwayat: status + audit
  → ReviewActionBar → modal konfirmasi (high-alert) → POST review
  → Undo 10 detik (UI) untuk aksi yang dapat dibatalkan
```

**Analisis pasien:**

```text
PatientAnalysisPage
  → analyzePatient()
      → coba AI Gateway (SBAR) → fallback POST /analyze
  → tampilkan skor, tier, grafik SHAP, flag, SBAR
  → checkSafetyFlags() → POST /interactions/safety
```

### 4.6 Permukaan AI di UI

| Fitur | Endpoint | Perilaku |
|---|---|---|
| Draf SBAR | `POST /api/v1/ai/sbar` | LLM chain + guardrail; fallback template |
| Copilot | `POST /api/v1/ai/copilot` | Jawaban dengan sumber + warning |
| Health AI | `GET /api/v1/ai/health` | Status provider + versi guardrail |
| Analisis | `POST /analyze` atau `/api/v1/analysis/{enc}/run` | ML + rules + SBAR |

Semua panggilan AI melewati FastAPI. Ini sesuai ADR-02/S7.

### 4.7 Temuan frontend

| # | Temuan | Dampak | Rekomendasi |
|---|---|---|---|
| FE-1 | `web/src/api/client.ts` baris 38–40 berisi objek duplikat setelah `headers` ditutup; `useAuthStore` tidak di-import | `npm run build` gagal (terverifikasi) | Hapus blok duplikat baris 38–40 dan import `useAuthStore`, atau alihkan seluruh pemakai ke `lib/apiClient.ts` |
| FE-2 | `client.ts` masih memakai `langflowAnalyze()` yang sebenarnya memanggil `/api/v1/ai/sbar`, lalu di-cast ke `AnalyzeResponse` | Bentuk data tidak cocok; analisis bisa error/fallback aneh | Gunakan `/api/v1/analysis/{enc}/run` atau `/analyze` secara eksplisit |
| FE-3 | Proxy `/langflow` masih ada di `vite.config.ts` | Menyiratkan browser boleh memanggil Langflow | Hapus proxy atau dokumentasikan sebagai khusus debug |
| FE-4 | Dua worklist (legacy vs v1) dan dua audit page | Kompleksitas & risiko inkonsistensi | Tetapkan satu jalur default; legacy hanya untuk kompatibilitas |
| FE-5 | `client.ts` legacy masih diimpor beberapa halaman | Perbaikan build harus menyentuh semua pemakai | Audit impor dan migrasi bertahap |

---

## 5. Backend FastAPI

### 5.1 Entry point & middleware

`api/main.py`:

- Membuat `FastAPI` dengan `lifespan` (startup/shutdown).
- CORS dibatasi oleh `CORS_ALLOWED_ORIGINS` (default `http://localhost:5173,http://localhost`).
- Middleware request-id + logging.
- Mount router legacy (tanpa prefix) dan seluruh `/api/v1`.
- Menyajikan SPA dari `web/dist` (atau `web/` saat dev) di `/`.
- Menyediakan `/app` dan `/app/{full_path}` sebagai fallback SPA.

### 5.2 Katalog endpoint legacy (kompatibilitas Langflow/MCP)

| Method | Path | Fungsi |
|---|---|---|
| GET | `/health` | Health legacy |
| GET | `/patient/{patient_id}` | Profil + encounter pasien |
| GET | `/patients/sample?limit=` | Daftar patient_id contoh |
| POST | `/prioritize` | Prioritas satu pasien |
| POST | `/prioritize/batch` | Peringkat massal |
| GET | `/worklist?limit=` | Worklist legacy |
| POST | `/discrepancies` | Deteksi diskrepansi |
| POST | `/review` | Catat keputusan apoteker |
| GET | `/audit` | Audit log legacy |
| POST | `/analyze` | Analisis lengkap + SBAR |
| POST | `/bpmh/{patient_id}` | Simpan BPMH |
| GET | `/bpmh/{patient_id}` | Ambil BPMH |
| GET | `/wards` | Daftar bangsal |
| POST | `/wards/config` | Konfigurasi bangsal |
| GET | `/settings/high-alert` | Daftar high-alert |
| POST | `/settings/high-alert` | Ubah high-alert |
| POST | `/interactions/check` | Cek interaksi obat |
| POST | `/interactions/safety` | Safety flags (ISMP/NTI/Beers) |

### 5.3 Katalog endpoint `/api/v1`

| Method | Path | Fungsi | Auth |
|---|---|---|---|
| GET | `/api/v1/health` | Liveness v1 | — |
| GET | `/api/v1/version` | Versi API/model/rules | — |
| GET | `/api/v1/health/deps` | DB, model, LLM, hash flow Langflow, guardrail, KB | Ya |
| POST | `/api/v1/auth/login` | Login | — |
| POST | `/api/v1/auth/refresh` | Refresh token | — |
| POST | `/api/v1/auth/logout` | Logout + audit | Ya |
| GET | `/api/v1/auth/me` | Profil pengguna | Ya |
| GET | `/api/v1/worklist` | Worklist v1 | Ya |
| POST | `/api/v1/worklist/{enc}/claim` | Klaim kasus | Ya |
| POST | `/api/v1/worklist/{enc}/release` | Lepas kasus | Ya |
| POST | `/api/v1/encounters/{enc}/review` | Review (APPROVE/EDIT/REJECT/ESCALATE/DRAFT_REVIEW) | Ya |
| GET | `/api/v1/encounters/{enc}/review/history` | Riwayat review | Ya |
| GET | `/api/v1/audit/verify` | Verifikasi rantai hash audit | Ya |
| POST | `/api/v1/ai/sbar` | AI Gateway SBAR | Ya |
| POST | `/api/v1/ai/copilot` | AI Gateway copilot | Ya |
| GET | `/api/v1/ai/health` | Status provider AI | Ya |
| POST | `/api/v1/analysis/{enc}/run` | Analisis Langflow-first | Ya |
| POST | `/api/v1/knowledge/lookup` | Alias/interaksi/alergi/high-alert | — |
| GET | `/api/v1/queue` | Daftar antrean (keyset) | Ya |
| POST | `/api/v1/queue/next` | Ambil & klaim entri teratas | Ya |
| POST | `/api/v1/queue/{enc}/heartbeat` | Perpanjang lease | Ya |
| POST | `/api/v1/queue/{enc}/release` | Lepas klaim | Ya |
| POST | `/api/v1/queue/{enc}/admit` | Ingest encounter | Ya |
| POST | `/api/v1/queue/{enc}/discharge` | Pasien pulang → CLOSED + missed_rec | Ya |
| POST | `/api/v1/queue/{enc}/transfer` | Pindah bangsal → re-triage | Ya |
| POST | `/api/v1/queue/{enc}/bpmh_submit` | BPMH selesai → pindah A→B | Ya |
| POST | `/api/v1/queue/{enc}/cancel` | Batal admisi | Ya |
| POST | `/api/v1/queue/{enc}/lab_critical` | Eskalasi lab kritis | Ya |
| POST | `/api/v1/queue/{enc}/order_change` | Order obat berubah | Ya |
| GET | `/api/v1/queue/metrics` | Metrik antrean | Ya |
| GET | `/api/v1/events/queue` | SSE diff antrean | Ya |

Catatan: `/api/v1/health` terdaftar dua kali (dari `v1_router` dan `health_v1_router`). FastAPI memakai yang pertama; sebaiknya dirapikan agar tidak membingungkan.

### 5.4 Autentikasi & RBAC

- JWT (`api/auth/jwt.py`) + password hashing (`api/auth/password.py`).
- Role: `PHARMACIST`, `TECHNICIAN`, `COORDINATOR`, `ADMIN`, `AUDITOR`.
- Service token untuk integrasi MCP/Langflow: role terbatas `{PHARMACIST, COORDINATOR}`, `actor_type="agent_via_mcp"`.
- Aksi tulis penting (review, claim, release) dibatasi role; audit memerlukan `AUDITOR`/`ADMIN`.
- Header integrasi: `X-Service-Token` untuk layanan, bukan untuk pengguna manusia.

### 5.5 Error, logging, observability

- `api/errors.py` + `parseApiError` di frontend → pesan konsisten.
- Request ID diteruskan ke response/log.
- `api/logging_config.py` mengatur format log.
- Audit hash-chain: setiap entri terhubung ke hash sebelumnya; `GET /api/v1/audit/verify` memeriksa integritas.

---

## 6. Lapisan Domain & Layanan

### 6.1 Pipeline analisis

`priomedrec_core/pipeline.py`:

| Fungsi | Isi | Ketergantungan |
|---|---|---|
| `run_phase_a` | Feature extraction + InferenceGuard + XGBoost + SHAP | `src.models`, `src.explainability` |
| `run_phase_b` | Normalisasi + rule engine + safety flags + interaksi + alergi + SBAR | Masih bergantung pada `src/` dan sebagian `api.services` |
| `run_full` | Fase A + Fase B + komposisi prioritas | Gabungan keduanya |

**Implikasi:** `priomedrec_core` belum sepenuhnya *pure*. Ini adalah blocker utama untuk menjadikan Langflow sebagai orkestrator penuh: komponen Langflow tidak boleh mengimpor FastAPI.

### 6.2 Rantai LLM & guardrail

`api/services/llm_chain_service.py`:

```text
Gemini → Groq → watsonx → Ollama → template deterministik
```

- Setiap provider memiliki timeout/retry/backoff.
- Bila semua gagal, `_build_sbar_template` menghasilkan SBAR deterministik.
- `guardrail_service.py` versi `guardrail-1.1.0` menjalankan 9 pemeriksaan (antara lain: obat di luar konteks, instruksi terapi, PII, panjang, struktur S/B/A/R, sitasi, injeksi prompt).
- `prompts/sbar_v1.md` dan `prompts/copilot_v1.md` menyimpan versi prompt.

### 6.3 Normalisasi obat

`api/services/normalizer_service.py` — 5 tahap:

1. Pembersihan teks (case, spasi, satuan).
2. Pencocokan alias (`knowledge/drug_alias.csv`, 257 baris).
3. Pencocokan kode/nama generik.
4. Fuzzy matching (rapidfuzz) dengan ambang.
5. Penandaan confidence + `UNRESOLVED_MATCH` bila ragu.

### 6.4 Komposisi prioritas

`priomedrec_core/priority.py`:

```text
final_tier = max(ML, RULE, SLA, current_tier)
```

- ML tier dari probabilitas (default core: HIGH ≥ 0.65, MEDIUM ≥ 0.35).
- Rule floor: temuan Tier-1/high-alert → HIGH; Tier-2 → MEDIUM.
- SLA: warning → MEDIUM; breach → HIGH.
- `priority_reasons[]` menyimpan alasan yang dapat diaudit.

### 6.5 Rule engine & safety

- `configs/discrepancy_rules.json` (`rules-0.2.0`, status DRAFT):
  - Omisi: kelas obat Tier-1 (antikoagulan, antiepilepsi, insulin, antiaritmia, digoksin, imunosupresan, antipsikotik depot, NTI).
  - Duplikasi: berdasarkan kode/nama ternormalisasi.
  - Substitusi: padanan terapeutik.
  - High-alert: daftar obat + hard stop.
- `configs/allergy_rules.json`: reaksi silang (DRAFT, owner TBD-apoteker).
- `knowledge/interactions.json`: 10 entri DDI terkurasi.
- `configs/high_alert_medications.json` dan `configs/drug_class_map.json` mendukung klasifikasi.

### 6.6 Queue engine & SLA

`priomedrec_core/queue_config.py` (versi `queue-0.1.0`):

```text
priority_score = 100 × (
    0.40 × sla_pressure
  + 0.25 × ml_percentile
  + 0.15 × severity_load
  + 0.10 × discharge_pressure
  + 0.10 × wait_norm
)
```

- `ml_high_quota_pct = 0.25`: entri HIGH yang hanya berasal dari ML dibatasi 25% per bangsal.
- `tier_hysteresis_margin = 0.05`: mencegah tier naik-turun akibat fluktuasi kecil.
- `claim_ttl_seconds = 900` (15 menit).
- SLA default: HIGH 4 jam (warning 2), MEDIUM 12 jam (warning 6), LOW 24 jam (warning 12).
- `queue_engine.py` menyediakan `compute_queue_score`, `compute_tier_from_ml_score`, `apply_ml_quota`, `apply_hysteresis`, `sort_queue`, `batch_rescore`.
- `api/tasks/queue_tick.py` dijalankan APScheduler setiap 60 detik: rescore batch, eskalasi SLA, expire lease, tulis `queue_events`. Target performa < 800 ms untuk 5.000 entri.
- `api/tasks/scheduler.py` juga menjalankan `sla_check`.

### 6.7 Audit & state machine

- `api/services/audit_service.py`: append-only hash-chain; setiap entri menyimpan hash sebelumnya.
- `api/services/case_state_service.py`: transisi status kasus (mis. BARU → DALAM_TELAAH → SELESAI / DITOLAK / DIESKALASI).
- `status_history` menyimpan jejak perubahan.
- `api/services/sla_service.py`: menghitung waktu tersisa, memicu `sla_events` dan notifikasi.

### 6.8 Knowledge lookup

`POST /api/v1/knowledge/lookup` (read-only):

| `lookup_type` | Sumber | Isi |
|---|---|---|
| `alias` | `knowledge/drug_alias.csv` | Brand → INN, exact/partial |
| `interaction` | `knowledge/interactions.json` | DDI terkurasi |
| `allergy` | `configs/allergy_rules.json` | Reaksi silang (DRAFT) |
| `high_alert` | `configs/discrepancy_rules.json` | Apakah obat high-alert |

Semua konten klinis diberi status `DRAFT_PERLU_VALIDASI_APOTEKER`.

### 6.9 MCP server

`mcp_server.py` (FastMCP) mengekspos 5 tool yang mendelegasikan ke FastAPI:

- `get_worklist`
- `get_case_context`
- `lookup_drug_knowledge`
- `check_interaction`
- `draft_review` (hanya DRAFT, bukan keputusan final)

Env: `PRIOMEDREC_API_URL`, `PRIOMEDREC_API_KEY`; header `X-Service-Token`. Dijalankan dari root repo agar `.venv` dan path resolve.

---

## 7. Data & Model

### 7.1 Database

**Tabel legacy:**

| Tabel | Fungsi |
|---|---|
| `bpmh_records` | BPMH lama |
| `ward_configs` | Konfigurasi bangsal |
| `local_high_alert` | Daftar high-alert lokal |

**Tabel baru:**

| Tabel | Fungsi |
|---|---|
| `users` | Akun + role |
| `encounters` | Episode rawat inap |
| `bpmh_items` | Item BPMH terstruktur |
| `analysis_runs` | Hasil analisis + versi + trace |
| `discrepancies` | Temuan diskrepansi |
| `sbar_drafts` | Draf SBAR |
| `sbar_revisions` | Riwayat revisi SBAR |
| `status_history` | Jejak status kasus |
| `sla_events` | Kejadian SLA |
| `notifications` | Notifikasi |
| `drug_alias` | Alias obat di DB |
| `sla_config` | Konfigurasi SLA |
| `audit_entries` | Audit hash-chain |

**Tabel antrean:**

| Tabel | Fungsi |
|---|---|
| `queue_entries` | Entri antrean + skor + tier + lease |
| `queue_events` | Event perubahan antrean |
| `missed_reconciliations` | Kasus pulang tanpa rekonsiliasi |

### 7.2 Model ML

| Item | Nilai |
|---|---|
| Algoritma | XGBoost |
| Versi | `model-0.3.0` |
| Label | `labels-3.0.0` (target sintetis `has_discrepancy`) |
| Fitur | `features-0.3.0` (10 fitur aman) |
| Kalibrasi | Isotonic (validation set) |
| Data | Synthea sintetis; **bukan** ground truth klinis |

**Fitur aman:** `age`, `age_65_plus`, `gender_encoded`, `polypharmacy_flag`, `high_alert_flag`, `high_alert_count`, `active_condition_count`, `prior_encounter_count`, `allergy_count`, `has_drug_allergy`.

**Fitur terlarang (memicu kegagalan inference):** `discontinued_medication_count`, `new_medication_count`, `total_medication_count`, `pre_admission_medication_count`, `admission_medication_count`, `potential_duplicate_candidates`.

**Metrik test terkalibrasi (XGBoost):**

| Metrik | Nilai |
|---|---|
| ROC-AUC | 0.8899 |
| PR-AUC | 0.9582 |
| F1 | 0.8943 |
| Precision | 0.8572 |
| Recall | 0.9348 |
| Brier | 0.1116 |

**Catatan penting:** `allergy_count` dan `has_drug_allergy` konstan 0 karena kualitas data (DQI-001). Performa tinggi sebagian dipengaruhi label sintetis dan prevalensi tinggi; **bukan bukti validitas klinis**.

### 7.3 Inkonsistensi threshold

| Sumber | HIGH | MEDIUM |
|---|---|---|
| `models/thresholds.json` | 0.70 | 0.40 |
| `configs/model_thresholds.json` | 0.70 | 0.40 |
| `priomedrec_core/priority.py` (default) | 0.65 | 0.35 |

**Rekomendasi:** jadikan satu sumber konfigurasi (`configs/model_thresholds.json`) dan oper parameter ke `compute_priority`/`tier_from_score`; tambahkan tes yang memastikan tidak ada drift.

### 7.4 Batasan data

- Data sintetis; tidak boleh dipakai untuk klaim klinis.
- `knowledge/interactions.json` hanya 10 entri → cakupan DDI sangat terbatas.
- `allergy_rules.json` masih DRAFT dan owner TBD.
- Perlu validasi apoteker sebelum pilot.

---

## 8. Alur Kerja End-to-End

### 8.1 Admisi → antrean

```text
[EHR/Admisi] encounter baru
   → POST /api/v1/queue/{enc}/admit
   → hitung fitur aman + ML score
   → tier awal (ML + rules + SLA)
   → queue_entries (status BARU)
   → queue_tick setiap 60 dtk: rescore, kuota, histeresis, eskalasi
   → Worklist/Queue di UI
```

### 8.2 BPMH → analisis

```text
Apoteker/teknisi input BPMH
   → POST /bpmh/{patient_id} (legacy) atau /api/v1/queue/{enc}/bpmh_submit
   → normalisasi obat
   → Fase A: fitur → XGBoost → probabilitas → tier ML
   → Fase B: rule engine → temuan + safety + DDI + alergi
   → priority composer
   → SBAR (LLM/guardrail atau template)
   → analysis_runs + discrepancies
   → tampil di Case Workspace
```

### 8.3 Telaah apoteker → audit

```text
Apoteker membuka kasus
   → membaca temuan + SBAR + label AI
   → (opsional) konfirmasi high-alert
   → pilih aksi:
        APPROVE  → status SELESAI
        EDIT     → simpan revisi SBAR → SELESAI
        REJECT   → wajib alasan → DITOLAK
        ESCALATE → notifikasi → DIESKALASI
   → POST /api/v1/encounters/{enc}/review
   → audit_entries (hash-chain) + status_history
   → queue entry ditutup/diperbarui
```

### 8.4 SLA & eskalasi

```text
sla_check (APScheduler)
   → hitung elapsed vs target per tier
   → warning → naikkan visibilitas
   → breach  → eskalasi HIGH + notifikasi
   → catat sla_events
```

### 8.5 Pasien pulang

```text
POST /api/v1/queue/{enc}/discharge
   → status CLOSED
   → bila belum direkonsiliasi → missed_reconciliations
   → metrik mutu diperbarui
```

### 8.6 Copilot & SBAR

```text
UI → POST /api/v1/ai/sbar
   → context builder (anonim, terikat konteks)
   → LLM chain (Gemini/Groq/watsonx/Ollama)
   → guardrail 9 cek
   → lolos: sbar_text + source
   → gagal: template deterministik + warning

UI → POST /api/v1/ai/copilot
   → konteks kasus + pertanyaan
   → LLM chain + guardrail
   → jawaban + sumber + warning
```

---

## 9. Langflow: Kondisi Saat Ini

### 9.1 Komponen kustom

`langflow/components/priomedrec/` berisi 19 kelas adapter:

| Modul | Komponen | Fungsi |
|---|---|---|
| `base.py` | `PMRJsonComponent` | Basis komponen JSON |
| `triage.py` | `PMRPayloadValidator` | Validasi skema |
| | `PMRFeatureExtractor` | Ekstraksi fitur aman |
| | `PMRInferenceGuard` | Menolak fitur terlarang |
| | `PMRXGBoostScorer` | Skor probabilitas |
| | `PMRSHAPExplainer` | Penjelasan fitur |
| | `PMRThresholdMapper` | Probabilitas → tier |
| `audit.py` | `PMRMedicationNormalizer` | Normalisasi obat |
| | `PMRDiscrepancyRules` | Omisi/duplikasi/substitusi |
| | `PMRSafetyFlags` | ISMP/NTI/Beers |
| | `PMRInteractionChecker` | DDI |
| | `PMRAllergyChecker` | Konflik alergi |
| | `PMRSeverityTiering` | Tier 1/2/3 |
| `safety.py` | `PMRContextBuilder` | Konteks LLM |
| | `PMRGuardrail` | 9 cek |
| | `PMRDeterministicSBARTemplate` | SBAR tanpa LLM |
| | `PMRResultPackager` | Kontrak hasil |
| | `PMRCaseContext` | Konteks kasus untuk agent |
| | `PMRDraftReview` | DRAFT review (tulis) |

**Masalah:** sebagian komponen masih mengimpor `src/` atau `api.services`, sehingga belum bisa dianggap adapter tipis yang mandiri. Ini bertentangan dengan prinsip "satu sumber kode deterministik" (`priomedrec_core`).

### 9.2 Flow yang ada

| Flow | Node | Isi | Status |
|---|---|---|---|
| `priomedrec_orchestrator.json` | 8 node / 5 edge | ChatInput → `PrioMedAnalyzeClient` (HTTP `POST /analyze`) → Prompt → LLM → ChatOutput + notes | **Bukan orkestrasi nyata**; hanya membungkus FastAPI |
| `priomedrec_review.json` | 5 node / 2 edge | ChatInput → `PrioMedReviewClient` (HTTP `/review`) → ChatOutput + notes | **Bukan gate HITL**; hanya relay |
| `priomedrec_agentic_v2.json` | 15 node / 16 edge | Agent + PythonREPL + Watsonx/Gemini + ConditionalRouter | Eksperimental; belum diverifikasi; PythonREPL berisiko |

**Flow target 00–06 belum ada.** Tidak ada master orchestrator yang memanggil sub-flow, tidak ada HITL gate, tidak ada copilot agent dengan tool terbatas.

### 9.3 Jalur eksekusi di backend

```text
POST /api/v1/analysis/{enc}/run
   → analysis_orchestrator.run_analysis()
       ├─ EXECUTION_MODE != local_only
       │    → LangflowClient.run_master(payload)
       │       → POST {LANGFLOW_BASE_URL}/api/v1/run/{LANGFLOW_MASTER_FLOW_ID}
       │       → x-api-key
       │       → timeout LANGFLOW_TIMEOUT_SECONDS (default 25)
       │       → retry 1x
       │       → circuit breaker (3 gagal, reset 60 dtk)
       │    → output_verifier.verify()
       │       ├─ lolos → execution.path = "langflow"
       │       └─ gagal → fallback lokal
       └─ gagal/timeout/circuit open
            → priomedrec_core.pipeline.run_full()
            → execution.path = "local_fallback"
```

**Catatan konfigurasi:**

- `.env.example` mendefinisikan `LANGFLOW_ORCHESTRATOR_FLOW_ID` dan `LANGFLOW_REVIEW_FLOW_ID`, tetapi `LangflowClient` membaca **`LANGFLOW_MASTER_FLOW_ID`**.
- Bila `LANGFLOW_MASTER_FLOW_ID` kosong, semua analisis akan jatuh ke fallback lokal.
- `LANGFLOW_API_KEY` kosong juga memicu fallback.
- `analysis_orchestrator._decorate` masih memakai `flow_version_hash` dummy (`sha256("pending-flow-export")`), bukan hash flow nyata.

### 9.4 Cakupan pipeline

| # | Langkah | Dikerjakan saat ini | Terlihat sebagai node Langflow? |
|---|---|---|---|
| 1 | Validasi payload + InferenceGuard | FastAPI | Parsial (komponen ada, tidak dipakai flow) |
| 2 | XGBoost + SHAP | FastAPI/`src` | Parsial |
| 3 | Komposisi prioritas | FastAPI | Tidak |
| 4 | Normalisasi obat | FastAPI | Parsial |
| 5 | Rule engine | FastAPI | Parsial |
| 6 | Safety flags + DDI + alergi | FastAPI | Parsial |
| 7 | SBAR LLM | Langflow (membungkus `/analyze`) | Ya (tetapi bukan logika) |
| 8 | Guardrail | FastAPI | Parsial |
| 9 | Review + audit | FastAPI | Tidak |
| 10 | Copilot | FastAPI | Tidak |

**Kesimpulan:** Langflow mencakup sekitar **1/10** langkah secara substantif. Target yang disarankan: **≥80% langkah tampak, dapat dijalankan, dilacak, dan didemokan**.

### 9.5 Verifikasi runtime

- Image target: `langflowai/langflow:1.13.0`.
- `docker compose config --quiet`: lulus.
- `docker version`: daemon tidak tersedia → **tidak ada uji start/health/flow**.
- Discovery lokal LFX 1.12.5: 13 komponen ditemukan, 1 error `ModuleNotFoundError: _lfx_ext`.
- Tes terarah: 6 passed (`test_analysis_orchestrator`, `test_priomedrec_core`, `test_pmr_components`).
- **Jangan menyatakan flow/container lulus runtime** sampai Docker tersedia dan smoke test diulang pada 1.13.0.

### 9.6 Gap utama

| # | Gap | Dampak |
|---|---|---|
| G1 | `priomedrec_core` belum pure (masih impor `src/` dan `api.services`) | Komponen tidak bisa dipakai mandiri di Langflow |
| G2 | Flow hanya membungkus HTTP ke FastAPI | Langflow tidak benar-benar mengorkestrasi |
| G3 | Tidak ada flow 00–06 | Tidak ada master orchestrator, HITL, copilot agent |
| G4 | `LANGFLOW_MASTER_FLOW_ID` tidak diisi | Jalur Langflow selalu fallback |
| G5 | `requirements.langflow.txt` kosong | Dependensi (xgboost/shap) belum tentu ada di image |
| G6 | Import loader gagal (`_lfx_ext`) | Komponen belum tentu muncul di kanvas |
| G7 | Tidak ada uji paritas | Tidak ada jaminan hasil Langflow = lokal |
| G8 | Tidak ada trace_id nyata di audit | Observabilitas belum terpenuhi |
| G9 | `flow_version_hash` dummy | Audit versi flow tidak valid |
| G10 | Runtime belum diuji | Klaim kesiapan belum boleh dibuat |

---

## 10. Apa yang Bisa Digantikan / Dimaksimalkan oleh Langflow

### 10.1 Prinsip desain

| Prinsip | Konsekuensi |
|---|---|
| **P1 — Langflow-first** | Master flow menjadi jalur utama analisis; FastAPI tetap gerbang |
| **P2 — Deterministik tetap deterministik** | Logika klinis hanya "dikemas" sebagai komponen; tidak dipindah ke LLM |
| **P3 — Satu kode, dua jalur** | `priomedrec_core` dipakai Langflow dan fallback lokal |
| **P4 — FastAPI pemilik state** | Auth, audit, persistensi, SLA tetap di FastAPI |
| **P5 — Browser tidak memanggil Langflow** | Semua lewat relay FastAPI |
| **P6 — HITL kelas satu** | Gerbang keputusan apoteker terlihat di flow |
| **P7 — Bukti kerja terlihat** | Trace, node stepper, versi flow di UI/audit |
| **P8 — Degradasi anggun** | Langflow mati → fallback lokal + banner |

### 10.2 Matriks: apa yang bisa digantikan

| Kapabilitas saat ini | Pemilik sekarang | Peran Langflow yang disarankan | FastAPI tetap |
|---|---|---|---|
| Orkestrasi pipeline analisis | `analysis_orchestrator` | **Master flow 00** memanggil sub-flow 01–03 | Menyediakan payload, verifier, fallback |
| Ekstraksi fitur + guard | `priomedrec_core`/`src` | Komponen `PMRFeatureExtractor`, `PMRInferenceGuard` | Menyimpan versi & validasi akhir |
| Skor ML + SHAP | `src.models` | Komponen `PMRXGBoostScorer`, `PMRSHAPExplainer` | Verifikasi skor & versi |
| Komposisi prioritas | `priority.py` | Komponen `PMRPriorityComposer` | Verifikasi tier final |
| Normalisasi obat | `normalizer_service` | Komponen `PMRMedicationNormalizer` | Simpan hasil |
| Rule engine | `discrepancy_service` | Komponen `PMRDiscrepancyRules` | Verifikasi temuan |
| Safety/DDI/alergi | service + config | Komponen `PMRSafetyFlags`, `PMRInteractionChecker`, `PMRAllergyChecker` | Simpan & audit |
| SBAR | `llm_chain_service` | **Flow 03** (prompt + LLM + guardrail + template) | Guardrail ulang + simpan |
| Guardrail | `guardrail_service` | Komponen `PMRGuardrail` di flow | Verifikasi ulang (defense in depth) |
| Review gate | UI + `review.py` | **Flow 05 HITL** (opsional/resume) | Pencatat resmi & audit |
| Copilot | `ai.py` + LLM chain | **Flow 04 Agent + Tools + Memory + KB** | Relay, auth, guardrail |
| Discharge check | `case_state_service` | **Flow 06** | State final |
| Observability | log/audit | **Traces + OTel** | Simpan trace_id di audit |
| Integrasi agent | `mcp_server.py` | Langflow MCP server/client | Tool FastAPI terbatas |

### 10.3 Yang **tidak** boleh digantikan Langflow

| Hal | Alasan |
|---|---|
| Keputusan akhir apoteker | Prinsip S1; HITL hanya gerbang, bukan pengganti |
| Audit hash-chain | Harus tetap di FastAPI (append-only, terverifikasi) |
| Auth/RBAC | Langflow bukan identity provider |
| Penyimpanan data klinis permanen | Langflow stateless untuk data klinis |
| Deteksi fakta klinis oleh LLM | LLM hanya narasi; fakta dari komponen deterministik |
| Penulisan status final tanpa persetujuan | Tool tulis hanya DRAFT + HITL |
| Perhitungan SLA/antrean | ADR-20: tidak ada LLM/Langflow di jalur antrean |

### 10.4 Tujuh flow target

| Flow | Nama | Isi | Prioritas |
|---|---|---|---|
| 00 | `00_master_orchestrator` | Validator → Run Flow 01 → Run Flow 02 → Priority Composer → Router → Run Flow 03 → Result Packager | P0 |
| 01 | `01_admission_triage` | Feature Extractor → InferenceGuard → XGBoost → SHAP → Threshold Mapper | P0 |
| 02 | `02_medrec_audit` | Normalizer → (paralel) rules/safety/DDI/alergi → Severity Tiering → Finding Formatter | P0 |
| 03 | `03_sbar_guardrail` | Context Builder → Prompt → LLM → Structured Output → Guardrail → Router (retry/template) | P0 |
| 04 | `04_pharmacist_copilot` | Agent + 7 tool + Memory + KB/RAG + Policies + HITL tool approval | P0 |
| 05 | `05_review_gate_hitl` | High-Alert Checker → Human Input (Approve/Edit/Reject/Escalate) → Tool `/review` | P0 |
| 06 | `06_discharge_gatekeeper` | Case Status → Discharge Rules → Router → LLM opsional → Output | P1 |

### 10.5 Fitur Langflow yang paling bernilai

| Fitur | Nilai untuk PrioMed-Rec | Status verifikasi |
|---|---|---|
| Custom Components | Membungkus logika deterministik sebagai node | Perlu loader fix |
| Agent + Tools | Copilot dengan tool baca/draft | Belum diuji runtime |
| Run Flow (flow-as-tool) | Master flow memanggil sub-flow | Belum ada |
| Human-in-the-Loop | Gerbang keputusan apoteker | Perlu uji resume API |
| Policies (ToolGuard) | Pagar tambahan untuk tool copilot | Beta; review kode |
| MCP server/client | Bob ↔ Langflow ↔ FastAPI | Belum ada sesi |
| Traces | Bukti eksekusi per node | Belum ada trace nyata |
| Workflow API v2/SSE | Progres node live di UI | Perlu uji stabilitas |
| Memory | Memori copilot per encounter | Belum ada |
| Knowledge Base/RAG | Sitasi penjelasan | Belum ada |
| Global model provider | Ganti LLM mudah (watsonx/Gemini/Groq/Ollama) | Belum diuji |
| `lfx-ibm` (watsonx) | Keselarasan ekosistem IBM | Belum dikonfirmasi di image |

### 10.6 Roadmap prioritas

| ID | Item | Ukuran | Prioritas |
|---|---|---|---|
| LF-001 | Audit kondisi Langflow + verifikasi fitur + pin versi | M | Selesai (runtime blocked) |
| LF-002 | Ekstrak `priomedrec_core` pure Python | L | Sebagian |
| LF-003 | Bangun komponen PMR + unit test | L | Sebagian (19 kelas, belum semua pure) |
| LF-004 | Image Langflow terpin + dependensi + health | M | Belum |
| LF-005 | Flow 01, 02, 03 + master 00 | L | Belum |
| LF-006 | Client/orchestrator/verifier/trace | L | Sebagian |
| LF-007 | Uji paritas Langflow ↔ lokal + fallback | M | Belum |
| LF-008 | Flow 04 Copilot (Agent + Tools + Memory + KB + Policies + HITL) | L | Belum |
| LF-009 | Frontend Pipeline Panel + badge sumber + SSE | L | Belum |
| LF-010 | Flow 05 Review Gate HITL + uji resume | M | Belum |
| LF-011 | Integrasi IBM Bob ↔ Langflow via MCP | M | Belum |
| LF-012 | Skrip demo + rekaman + dokumentasi | S | Belum |
| LF-020 | Flow 06 Discharge Gatekeeper | M | P1 |
| LF-021 | A2A | M | P1 |
| LF-022 | watsonx via `lfx-ibm` | M | P1 |
| LF-023 | OpenTelemetry | M | P1 |
| LF-024 | AG-UI streaming | M | P1 |
| LF-025 | Halaman Flow Map | M | P1 |
| LF-026 | Webhook trigger | S | P1 |
| LF-027 | Knowledge Base/RAG + sitasi | M | P1 |
| LF-028 | Flow DevOps Toolkit di CI | M | P1 |

**Urutan kritis:** LF-002 → LF-003 → LF-004 → LF-005 → LF-006/007 → LF-009 → LF-008 → LF-010 → LF-011 → LF-012.

### 10.7 Kriteria selesai (definition of done)

| Area | Kriteria |
|---|---|
| Paritas | Golden set ≥40 kasus; temuan, tier, skor (toleransi 1e-6), dan SBAR template identik antara Langflow dan lokal |
| Komponen | ≥90% komponen PMR punya unit test input→output |
| Flow | Setiap flow lulus uji skema input/output di CI |
| Fallback | Langflow dimatikan/dilambatkan/output rusak → verifier menolak → fallback lokal; UI menampilkan banner |
| Guardrail | 100% serangan (obat fiktif, instruksi terapi, prompt injection, PII) ditolak |
| Agent | Copilot tidak memanggil `draft_review` tanpa persetujuan; selalu menyertakan sumber |
| HITL | Checkpoint berhenti; Approve/Edit/Reject/Escalate memicu cabang benar; alasan wajib untuk reject |
| Performa | Master flow P95 < 6 dtk tanpa LLM; < 15 dtk dengan LLM |
| E2E | Pipeline Panel tampil; badge sumber benar; mode cadangan tampil saat Langflow mati |
| Audit | `trace_id`, `flow_version_hash`, `execution.path` tersimpan di `analysis_runs` dan `audit_entries` |

### 10.8 Skenario demo Langflow-centric (5 menit)

| Menit | Adegan | Bukti |
|---|---|---|
| 0:00 | Masalah & solusi | Urgensi |
| 0:20 | Kanvas master flow + komponen PMR | Pipeline terlihat |
| 0:55 | Worklist → kasus → Pipeline Panel (SSE) | Langflow di jalur nyata |
| 1:40 | Temuan Tier-1 + side-by-side + hard stop | Deterministik & aman |
| 2:15 | Trace run per komponen | Observabilitas |
| 2:40 | Copilot → tool terpanggil → HITL approve | Agent + HITL |
| 3:25 | Policies menolak instruksi terapi | Pagar kebijakan |
| 3:50 | IBM Bob membuat/menjalankan flow via MCP | Sinergi |
| 4:15 | Matikan Langflow → banner cadangan, hasil identik | Ketahanan |
| 4:40 | Metrik jujur + roadmap | Kredibilitas |

---

## 11. Temuan, Risiko, dan Rekomendasi

### 11.1 Temuan kritis

| # | Temuan | Bukti | Dampak | Rekomendasi |
|---|---|---|---|---|
| T1 | Build frontend gagal | `npx tsc -b` → TS1005/TS1109/TS1128 di `client.ts` | Tidak bisa `npm run build`; deployment Docker web gagal | Perbaiki `client.ts` (hapus blok duplikat, import store) atau migrasi ke `lib/apiClient.ts` |
| T2 | `LANGFLOW_MASTER_FLOW_ID` tidak diisi | `.env.example` hanya punya ORCHESTRATOR/REVIEW | Jalur Langflow selalu fallback | Tambahkan `LANGFLOW_MASTER_FLOW_ID` setelah flow 00 dibuat |
| T3 | `flow_version_hash` dummy | `analysis_orchestrator._decorate` | Audit versi flow tidak valid | Hitung hash JSON flow nyata; simpan |
| T4 | Threshold drift | 0.65/0.35 vs 0.70/0.40 | Tier tidak konsisten antar jalur | Satu sumber konfigurasi + tes |
| T5 | `priomedrec_core` belum pure | `pipeline.py` impor `src`/`api.services` | Komponen Langflow tidak mandiri | Ekstrak dependensi ke core |
| T6 | Komponen Langflow belum teruji di image | Discovery 13 komponen, 1 import error | Komponen mungkin tidak muncul | Perbaiki loader + uji di 1.13.0 |
| T7 | Docs arsitektur usang | `docs/architecture.md` menyebut Streamlit | Kebingungan kontributor | Perbarui atau tandai superseded |
| T8 | Streamlit legacy masih ada | `streamlit_app/` + 20 tes | Beban pemeliharaan | Arsipkan/hapus setelah migrasi |
| T9 | Proxy `/langflow` di Vite | `vite.config.ts` | Melanggar semangat ADR-02 | Hapus atau tandai debug-only |
| T10 | Duplikasi route `/api/v1/health` | `main.py` include dua router | Perilaku membingungkan | Hapus salah satu |

### 11.2 Risiko Langflow-first

| Risiko | Mitigasi |
|---|---|
| Latensi/kegagalan saat demo | Timeout, circuit breaker, fallback lokal, output freeze, rekaman |
| Hasil Langflow ≠ lokal | Satu paket core + uji paritas di CI |
| Bentrok dependensi (xgboost/shap) di image | Image terpin; opsi B: komponen memanggil `/internal/tools/*` |
| HITL resume dari UI eksternal tidak layak | Fallback: keputusan dicatat di FastAPI; Flow 05 untuk Playground/Bob |
| Policies masih beta | Review & commit kode guard; jadikan lapisan tambahan |
| Versi Langflow berubah | Pin versi + `LANGFLOW_VERIFICATION.md` + CI |
| Scope membengkak | Tegaskan P0 vs P1; A2A/OTel/AG-UI stretch |

### 11.3 Rekomendasi jangka pendek (0–2 minggu)

1. **Perbaiki build frontend** (T1) agar `npm run build` hijau.
2. **Rapikan konfigurasi Langflow** (T2, T3): tambah `LANGFLOW_MASTER_FLOW_ID`, hitung hash flow nyata.
3. **Selesaikan LF-002**: pindahkan dependensi `src/` yang dipakai `priomedrec_core` ke dalam core atau adapter murni.
4. **Perbaiki loader komponen** dan uji di image 1.13.0 saat Docker tersedia.
5. **Buat flow 01–03 + master 00** dan ekspor ke `langflow/flows/`.
6. **Tambahkan uji paritas** untuk mencegah regresi.
7. **Perbarui `docs/architecture.md`** dan tandai Streamlit sebagai legacy.

### 11.4 Rekomendasi jangka menengah (2–6 minggu)

1. Flow 04 Copilot dengan tool baca/draft + Policies + Memory + KB.
2. Flow 05 HITL + uji resume via API; fallback terdokumentasi.
3. Pipeline Transparency Panel + badge sumber + SSE di UI.
4. Integrasi IBM Bob ↔ Langflow via MCP dua arah.
5. Trace/OTel + simpan `trace_id` di audit.
6. Flow 06 Discharge Gatekeeper.

### 11.5 Rekomendasi jangka panjang

- A2A untuk flow Audit/Copilot.
- Knowledge Base/RAG dengan sitasi (hanya penjelasan).
- Flow DevOps Toolkit di CI.
- Kalibrasi ulang antrean dengan simulator dan data nyata tervalidasi.
- Evaluasi klinis prospektif sebelum pilot.

---

## 12. Lampiran

### A. Environment variables penting

| Variabel | Default/contoh | Fungsi |
|---|---|---|
| `VITE_DATA_MODE` | `synthetic` | Mode data frontend |
| `VITE_AUTH_REQUIRED` | — | Paksa login |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://localhost` | Origin CORS |
| `EXECUTION_MODE` | `langflow_first` | `langflow_first` / `langflow_only` / `local_only` |
| `LANGFLOW_URL` | `http://langflow:7860` | Base URL alternatif |
| `LANGFLOW_BASE_URL` | `http://langflow:7860` | Base URL utama |
| `LANGFLOW_API_KEY` | — | API key server-side |
| `LANGFLOW_MASTER_FLOW_ID` | — | Flow 00 (wajib untuk jalur Langflow) |
| `LANGFLOW_ORCHESTRATOR_FLOW_ID` | UUID contoh | Flow lama; belum dibaca client |
| `LANGFLOW_REVIEW_FLOW_ID` | UUID contoh | Flow review lama |
| `LANGFLOW_TIMEOUT_SECONDS` | `25` | Timeout request |
| `LANGFLOW_CIRCUIT_FAILS` | `3` | Ambang circuit breaker |
| `LANGFLOW_CIRCUIT_RESET_SECONDS` | `60` | Waktu reset circuit |
| `LANGFLOW_SUPERUSER` | `langflow-admin` | Akun admin Langflow |
| `LANGFLOW_SUPERUSER_PASSWORD` | wajib diubah | Password admin |
| `LANGFLOW_SECRET_KEY` | wajib diubah | Secret Langflow |
| `LLM_PROVIDER` | `gemini` | Provider utama |
| `LLM_API_KEY` | — | Kunci provider |
| `LLM_MODEL_NAME` | `gemini-2.5-flash` | Model |
| `LLM_FALLBACK_MODEL` | `gemini-1.5-flash-8b` | Fallback |
| `LLM_GROQ_API_KEY` | — | Groq fallback |
| `SERVICE_API_KEY_LANGFLOW` | `changeme-...` | Token layanan |
| `PRIOMEDREC_API_URL` | `http://localhost:8000` | MCP → FastAPI |
| `PRIOMEDREC_API_KEY` | — | MCP service token |

### B. Perintah menjalankan

**Backend:**

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/validate_data_layout.py
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

**Frontend:**

```powershell
Set-Location web
npm ci
$env:VITE_DATA_MODE = "live"
npm run dev
```

**Docker:**

```powershell
docker compose up --build
```

**MCP:**

```powershell
Set-Location D:\Hacktiv8\priomed-rec
.\.venv\Scripts\python.exe .\mcp_server.py
```

**Tes:**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
Set-Location web
npm run build
```

### C. Endpoint quick reference

```text
Legacy:
  GET  /health
  GET  /patient/{id}
  GET  /patients/sample
  POST /prioritize
  POST /prioritize/batch
  GET  /worklist
  POST /discrepancies
  POST /review
  GET  /audit
  POST /analyze
  POST/GET /bpmh/{patient_id}
  GET  /wards
  POST /wards/config
  GET/POST /settings/high-alert
  POST /interactions/check
  POST /interactions/safety

v1:
  GET  /api/v1/health
  GET  /api/v1/version
  GET  /api/v1/health/deps
  POST /api/v1/auth/login
  POST /api/v1/auth/refresh
  POST /api/v1/auth/logout
  GET  /api/v1/auth/me
  GET  /api/v1/worklist
  POST /api/v1/worklist/{enc}/claim
  POST /api/v1/worklist/{enc}/release
  POST /api/v1/encounters/{enc}/review
  GET  /api/v1/encounters/{enc}/review/history
  GET  /api/v1/audit/verify
  POST /api/v1/ai/sbar
  POST /api/v1/ai/copilot
  GET  /api/v1/ai/health
  POST /api/v1/analysis/{enc}/run
  POST /api/v1/knowledge/lookup
  GET  /api/v1/queue
  POST /api/v1/queue/next
  POST /api/v1/queue/{enc}/heartbeat
  POST /api/v1/queue/{enc}/release
  POST /api/v1/queue/{enc}/admit
  POST /api/v1/queue/{enc}/discharge
  POST /api/v1/queue/{enc}/transfer
  POST /api/v1/queue/{enc}/bpmh_submit
  POST /api/v1/queue/{enc}/cancel
  POST /api/v1/queue/{enc}/lab_critical
  POST /api/v1/queue/{enc}/order_change
  GET  /api/v1/queue/metrics
  GET  /api/v1/events/queue
```

### D. Glosarium

| Istilah | Arti |
|---|---|
| BPMH | Best Possible Medication History |
| Diskrepansi | Ketidaksesuaian antara obat sebelum admisi dan order admisi |
| Omisi | Obat yang seharusnya dilanjutkan tetapi tidak ada di order |
| Duplikasi | Dua obat/kelas sama diberikan bersamaan |
| Substitusi | Penggantian obat dengan padanan terapeutik |
| High-alert | Obat berisiko tinggi yang memerlukan konfirmasi ekstra |
| NTI | Narrow Therapeutic Index |
| Beers PIM | Potentially Inappropriate Medication pada lansia |
| SBAR | Situation, Background, Assessment, Recommendation |
| Tier | Tingkat prioritas telaah: HIGH / MEDIUM / LOW |
| SLA | Batas waktu telaah per tier |
| HITL | Human-in-the-Loop |
| DDI | Drug-Drug Interaction |
| RAG | Retrieval-Augmented Generation |
| MCP | Model Context Protocol |

### E. Checklist verifikasi sebelum klaim siap

- [ ] `docker compose config --quiet` lulus.
- [ ] Docker daemon aktif; `docker compose up -d langflow`; `/health` merespons.
- [ ] Versi container = 1.13.0 (catat).
- [ ] Komponen PMR muncul di kanvas; tidak ada error import.
- [ ] Flow 00–03 diimpor; `/api/v1/run/{flow_id}` sukses dengan `x-api-key`.
- [ ] `LANGFLOW_MASTER_FLOW_ID` dan `LANGFLOW_API_KEY` terisi.
- [ ] `EXECUTION_MODE=langflow_first`; `analysis_runs.execution.path="langflow"` teramati.
- [ ] Uji paritas ≥40 kasus lulus.
- [ ] Uji fallback (Langflow mati/timeout/output rusak) lulus.
- [ ] `npm run build` hijau.
- [ ] `pytest -q` hijau.
- [ ] Audit `trace_id` + `flow_version_hash` terisi nyata.
- [ ] UI menampilkan badge sumber + banner mode cadangan.
- [ ] Tidak ada PII/secret di log/dokumen.

### F. Sumber dokumen internal

| Dokumen | Fungsi |
|---|---|
| `README.md` | Gambaran produk & cara menjalankan |
| `docs/WEBSITE_RUNBOOK.md` | Runbook website-first |
| `docs/API_contract.md` | Kontrak API |
| `docs/database_schema.md` | Skema database |
| `docs/MODEL_CARD.md` | Kartu model & batasan |
| `docs/DECISION_LOG.md` | ADR |
| `docs/LANGFLOW_AUDIT.md` | Audit kondisi Langflow |
| `docs/LANGFLOW_IMPLEMENTATION_PLAN.md` | Status backlog LF |
| `docs/LANGFLOW_VERIFICATION.md` | Verifikasi fitur & blocker |
| `docs/LANGFLOW_AND_IBM_BOB.md` | Integrasi MCP/Bob |
| `DOKUMENTASI_MASTER_ANALISIS_PRIOMEDREC.md` | Dokumen master analisis sebelumnya |
| `PRIOMEDREC_LANGFLOW_MAXIMIZATION_PLAN.md` | Rencana maksimisasi Langflow |
| `PRIOMEDREC_STRATEGIC_DEVELOPMENT_PLAN.md` | Rencana strategis |
| `PRIOMEDREC_QUEUE_MANAGEMENT_PLAN.md` | Rencana antrean |
| `priomedrec_master_blueprint-v4.md` | Blueprint produk |

---

## Penutup

PrioMed-Rec memiliki fondasi keselamatan yang baik: keputusan tetap pada apoteker, fakta klinis dihasilkan secara deterministik, audit tidak dapat diubah diam-diam, dan ada fallback saat AI gagal. Peluang terbesar bukan menambah LLM, melainkan **memindahkan orkestrasi pipeline ke Langflow secara bertahap tanpa menduplikasi logika** — dengan `priomedrec_core` sebagai satu-satunya sumber kebenaran deterministik, `output_verifier` sebagai penjaga, dan uji paritas sebagai gerbang CI.

Selama empat syarat itu belum terpenuhi — core pure, komponen termuat, flow 00–06 ada, dan runtime terverifikasi — status Langflow harus dinyatakan **belum siap menjadi jalur utama**, dan sistem tetap mengandalkan jalur lokal yang sudah berjalan.
