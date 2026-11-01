# Audit Langflow — LF-001

**Tanggal:** 2026-10-29  
**Status:** audit kode selesai; verifikasi container/runtime BLOCKED karena Docker daemon tidak tersedia.  
**Sumber utama:** `../PRIOMEDREC_LANGFLOW_MAXIMIZATION_PLAN.md`; rencana strategis dan master analysis berada di root repositori, bukan di `docs/` seperti jalur pada instruksi awal.

## Ringkasan kondisi nyata

Repositori sudah memiliki sebagian fondasi Langflow-first, tetapi belum mengoperasikan pipeline melalui Langflow:

- Paket `priomedrec_core` (contracts, pipeline, priority) dan **19 kelas adapter PMR** sudah ada. Adapter belum dipasang ke flow analisis aktif dan sebagian masih memanggil `src/`, `api.services`, atau route FastAPI secara langsung. Karena itu paket belum menjadi satu-satunya sumber deterministik yang pure Python.
- `langflow/` berisi dua flow legacy (orchestrator 8 node dan review 5 node) serta flow agentic eksperimental 15 node; tidak ada flow target `00`–`06` atau direktori `langflow/flows/`.
- Flow orchestrator lama menampilkan panggilan API FastAPI dan narasi, bukan rangkaian node pipeline PMR. Dengan hitungan 10 langkah pipeline pada rencana utama, hanya SBAR yang sebagian terlihat: **sekitar 1/10 (≈10%)**, bukan cakupan Langflow-first.
- Image Docker sebelumnya dipin ke 1.12.2, sedangkan virtualenv proyek berisi Langflow/LFX 1.12.5 dan `lfx-ibm` 0.2.5. Pin Compose/Dockerfile kini diperbarui ke rilis stabil resmi 1.13.0; runtime image belum diuji.
- `docker compose config --quiet` lulus. Docker daemon tidak tersedia, sehingga `docker compose up`, health check Langflow, eksekusi flow, dan verifikasi versi image tidak dapat dijalankan.
- Tes lokal terarah untuk orchestrator, core, dan katalog komponen: **6 passed**. Discovery LFX lokal 1.12.5 menemukan 13 komponen dan satu kegagalan import (`ModuleNotFoundError: _lfx_ext`); discovery penuh pada image pin belum diverifikasi.

## Peta pipeline aktual

| # | Langkah | Pelaksana dalam kode saat ini | Status komponen/flow Langflow |
|---:|---|---|---|
| 1 | Fitur + InferenceGuard | `src/features/`, `src/models/inference_guard.py`, `priomedrec_core/pipeline.py` | Adapter tersedia; belum dirangkai di flow aktif |
| 2 | Skor ML + SHAP | `src/models/predict.py`, `api/services/prioritization_service.py`, `priomedrec_core/pipeline.py` | Adapter tersedia; belum dirangkai di flow aktif |
| 3 | Prioritas final | `api/services/priority_service.py`, `priomedrec_core/priority.py` | Adapter tersedia; belum dirangkai di flow aktif |
| 4 | Normalisasi obat | `api/services/normalizer_service.py` | Adapter tersedia; adapter masih memanggil service API |
| 5 | Rule engine diskrepansi | `src/rules/discrepancy_engine.py`, `priomedrec_core/pipeline.py` | Adapter tersedia; belum dirangkai di flow aktif |
| 6 | Safety, DDI, alergi, severity | `src/rules/safety_flags_engine.py`, `api/routes/interactions.py`, konfigurasi `configs/` | Beberapa adapter masih passthrough/stub; belum ada parity lengkap |
| 7 | SBAR/narasi | Flow legacy `priomedrec_orchestrator.json`; FastAPI `api/routes/v1/ai.py` dan `api/services/llm_chain_service.py` | Sebagian terlihat; Flow 03 target belum ada |
| 8 | Guardrail | `api/services/guardrail_service.py`, `src/llm/validators/` | Adapter tersedia; belum wired pada flow target; verifier API belum melakukan seluruh 7 cek |
| 9 | Review + audit | FastAPI `api/routes/v1/review.py`, `api/services/audit_service.py`; flow legacy review | Review/audit resmi tetap di FastAPI; belum ada Human Input checkpoint di flow |
| 10 | Copilot | `web/src/components/CopilotDrawer.tsx`, `api/routes/v1/ai.py`, LLM chain | UI/API tersedia; belum ada Agent Flow 04 aktif |

### Paket inti dan adapter yang ditemukan

`priomedrec_core/` berisi `contracts.py`, `pipeline.py`, `priority.py` serta modul antrean. `pipeline.py` masih mengimpor model, feature pipeline, SHAP, dan discrepancy engine dari `src/`; adapter di `langflow/components/priomedrec/` juga mengimpor sejumlah service/route dari `api/`. `run_phase_b()` saat ini mengembalikan daftar kosong untuk konflik alergi, interaksi, dan safety flags. Ini berarti extraction/parity belum selesai, meskipun struktur awalnya sudah ada.

Sebanyak 19 kelas PMR terdefinisi di `triage.py`, `audit.py`, dan `safety.py` (di luar base class). Uji katalog hanya memeriksa keberadaan nama dan draft-review marker, bukan seluruh perilaku tiap komponen atau discovery pada image Docker.

## Flow, API, frontend, MCP

| Permukaan | Kondisi aktual | Gap penting |
|---|---|---|
| `langflow/priomedrec_orchestrator.json` | Flow legacy 8 node; panggilan FastAPI, prompt, LLM | Bukan master flow dan tidak menjalankan fase A/B sebagai PMR nodes |
| `langflow/priomedrec_review.json` | Flow legacy 5 node | Bukan Human Input checkpoint; tidak membuktikan resume eksternal |
| `langflow/priomedrec_agentic_v2.json` | 15 node agentic eksperimental; ada `PythonREPLTool` bernama “LogReview” | Jangan aktifkan sebagai flow klinis; write tool harus diganti draft-only dan direview |
| `langflow/components/priomedrec/` | 19 adapter PMR tersedia | Discovery LFX 1.12.5 parsial (13 komponen, satu import error); belum terbukti pada 1.13.0 |
| `api/routes/v1/analysis.py` | `POST /api/v1/analysis/{encounter_id}/run` memanggil Langflow-first orchestrator; `/analyze` tetap ada | ID flow master tidak ada pada `.env.example`; tanpa konfigurasi `LANGFLOW_MASTER_FLOW_ID`, client jatuh ke fallback |
| `api/services/langflow_client.py` | v1 `/api/v1/run/{flow_id}`, header `x-api-key`, timeout default 25 dtk, 2 percobaan, circuit breaker | Belum ada panggilan runtime; retry/circuit breaker belum diuji terhadap server aktual |
| `api/services/analysis_orchestrator.py` | Mode `langflow_first`, `local_only`, `langflow_only`; fallback lokal pada error yang dikenali | `flow_version_hash` masih hash literal `pending-flow-export`; trace hanya ada di respons |
| Output verifier | Memvalidasi skema, ID, rentang skor, versi model/rules, inventaris obat, Tier-1→HIGH | Belum memverifikasi skor terhadap core, guardrail pass, PII, atau seluruh versi/cek yang direncanakan |
| `analysis_runs`/audit | Model `AnalysisRun` tidak memiliki execution path, flow hash, trace ID, duration/steps; orchestrator tidak menyimpan run/audit | ADR-17 belum terpenuhi; trace service belum ada |
| SSE | SSE antrean tersedia di `api/routes/v1/queue_events.py` | Tidak ada SSE relay progres analisis/komponen Langflow |
| `web/src/api/langflow.ts` | Semua AI requests melalui FastAPI `/api/v1/ai/*` | Tidak ditemukan panggilan browser langsung ke endpoint Langflow |
| `mcp_server.py`/`mcp_settings.json` | 5 tool MCP menuju FastAPI; satu tool tulis hanya membuat DRAFT; konfigurasi Bob menjalankan MCP lokal | Tidak ada koneksi MCP Langflow di repo atau tool Langflow MCP yang tersambung pada sesi audit |

## Konfigurasi dan risiko deployment

- `Dockerfile.langflow` dan `docker-compose.yml` kini memakai `langflowai/langflow:1.13.0`, rilis stabil terbaru yang tercatat pada rilis resmi dan memiliki tag Docker aktif saat audit. `docker compose config --quiet` lulus; health check container belum dijalankan.
- Compose menonaktifkan auto-login, meminta superuser/password/secret dari environment, mematikan custom code publik/interpreter, dan memasang `langflow/components` read-only di `LANGFLOW_COMPONENTS_PATH`.
- Dokumentasi Langflow menjelaskan `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false` memblokir kode custom yang disimpan pengguna, sedangkan folder operator-managed di `LANGFLOW_COMPONENTS_PATH` tetap menjadi daftar komponen yang diizinkan. Keduanya perlu dibuktikan pada image 1.13.0.
- `web` saat ini menunggu health check Langflow (`depends_on: service_healthy`). Ini berpotensi menghalangi startup web ketika Langflow gagal, bertentangan dengan S13; ubah/tes saat LF-004, jangan menganggap fallback API saja cukup.
- `.env.example` memuat ID flow lama tetapi belum `LANGFLOW_MASTER_FLOW_ID`; API key Langflow juga perlu dikonfigurasi di backend. Flow target dan key tidak boleh ditulis ke JSON.
- Pemindaian field credential JSON menemukan metadata field Langflow (flag/password-input dan parameter API key), bukan nilai kredensial literal. Pemeriksaan PII/data sintetis tetap perlu diintegrasikan pada validasi artefak flow.

## Penilaian dan jalur berikut

Baseline saat ini adalah **persiapan parsial, belum Langflow-first**. Prioritas berikutnya: bereskan extraction/parity core; perbaiki discovery/import adapter; bangun dan ekspor Flow 01–03 dan master Flow 00; lengkapi API flow ID, verifier, persistensi trace, dan fallback; baru lanjut UI transparency, Agent/Copilot, serta HITL.

S1–S14 tidak berubah. Semua fakta klinis tetap deterministik, keputusan final tetap di apoteker, output AI adalah draf, audit FastAPI tetap resmi, dan fallback lokal harus tetap tersedia.
