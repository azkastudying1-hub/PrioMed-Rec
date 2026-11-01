# Rencana Implementasi Langflow-first — LF-001

S1–S14 tetap mengikat: fakta klinis deterministik, apoteker memutuskan, guardrail di flow dan diverifikasi ulang API, audit FastAPI, data sintetis, browser tidak memanggil Langflow langsung, dan fallback lokal.

## Status berdasarkan audit LF-001

| Backlog | Status nyata | Langkah dan kriteria selesai |
|---|---|---|
| LF-002 — core deterministik | Parsial: contracts/pipeline/priority ada; `pipeline.py` masih menggunakan `src/`, Fase B mengembalikan placeholder kosong untuk alergi/DDI/safety | Ekstrak tanpa perubahan perilaku; adapter tanpa dependensi FastAPI/Langflow; parity test lama dan baru; uji S5/S6 |
| LF-003 — komponen PMR | 19 class adapter ada; discovery LFX lokal hanya 13 dan satu import gagal | Tes discovery/import semua class pada image pin; test perilaku per adapter; tandai Tool Mode hanya untuk baca/draft |
| LF-004 — image/runtime | Dockerfile khusus ada; dependencies kosong; Docker pin 1.13.0; runtime terblokir | Bangun image yang memuat core/komponen dan dependency kompatibel; health pass; komponen terdaftar; layanan web/API tetap mulai saat Langflow gagal |
| LF-005 — flow 00–03 | Belum ada flow target; dua JSON lama memanggil API FastAPI | Bangun Flow 01–03 dan master 00; ekspor JSON tanpa secret; uji import, skema, subflow, hash |
| LF-006 — client/orchestrator/verifier/trace | Client, mode, circuit breaker, route, verifier awal sudah ada | Lengkapi master flow config; timeout/retry/breaker; 7 cek verifier; jangan simpan hasil sebelum verified; persist execution path/hash/trace/duration/steps di analysis_runs dan audit |
| LF-007 — paritas/fallback | Tes unit awal ada; belum ada flow runtime/parity golden set | 100% findings/tier identik, skor toleransi 1e-6; uji Langflow off/timeout/malformed/verifier reject → local fallback |
| LF-009 — UI transparency | Belum ada relay SSE analisis/panel node | FastAPI relay node steps, badge Langflow/fallback, trace ID; e2e web |
| LF-008 — Copilot Agent | Drawer/API dan adapter awal ada; Flow 04 tidak ada | Agent + tools baca + RAG/sumber + Policies; adversarial; review tool wajib draft/HITL |
| LF-010 — Review HITL | Flow 05 tidak ada; belum ada resume API test | Uji pause/resume API eksternal; bila gagal, keputusan UI→FastAPI resmi; Flow 05 tetap untuk Playground/Bob/MCP |
| LF-011 — Bob↔Langflow MCP | MCP server saat ini lima tool FastAPI; tidak ada Langflow MCP | Daftarkan tools read/draft, pastikan actor audit; tidak ada final write |
| LF-012 — demo/docs | Demo script ada, belum ada demo Langflow-first end-to-end | Skrip 5 menit, reset, offline fallback, checklist dan bukti trace |

P1 sesudah gerbang P0: LF-020 Discharge, LF-021 A2A, LF-022 watsonx, LF-023 OpenTelemetry, LF-024 AG-UI, LF-025 Flow Map, LF-026 Webhook, LF-027 KB lengkap, LF-028 Flow DevOps CI.

## Urutan kritis dan risiko

`LF-002 → LF-003 → LF-004 → LF-005 → LF-006/LF-007 → LF-009 → LF-008 → LF-010 → LF-011 → LF-012`.

Risiko awal: (1) Docker daemon tidak tersedia sehingga runtime target belum diverifikasi; (2) virtualenv 1.12.5 berbeda dari image 1.13.0; (3) LFX inline discovery gagal pada satu import; (4) `LANGFLOW_MASTER_FLOW_ID` belum ada di `.env.example` dan flow master belum tersedia; (5) placeholder hash trace dan metadata execution belum disimpan; (6) web menunggu health Langflow meski fallback di API tersedia; (7) satu flow eksperimental memiliki PythonREPL tool berlabel LogReview dan tidak boleh dijadikan flow aktif.

## Keputusan teknis awal (tanpa mengubah keselamatan)

- **D2:** pertahankan opsi A (komponen memanggil `priomedrec_core`) hanya setelah tes dependency/import pada image lulus. Saat ini core belum murni; jika xgboost/shap/pydantic berbenturan, lakukan spike opsi B (`/internal/tools/*` dengan service token), jangan menggandakan logika.
- **D3:** belum dapat memilih berdasarkan runtime. Uji resume Workflow API v2 terlebih dulu; jika gagal/tidak layak, UI→FastAPI tetap pencatat keputusan resmi dan Flow 05 dipakai untuk Playground/Bob/MCP.
- Policies tetap tambahan dan hasil generated code harus direview serta dikomit. Model Provider dan RAG tidak menjadi sumber fakta deteksi klinis.

## Definition of done LF-001

- Audit pipeline, flow, UI/API/MCP, dan gap runtime dikoreksi berdasarkan kode nyata.
- Matriks verifikasi menyebut status dokumentasi, spike, dan fallback tanpa mengklaim runtime yang belum dijalankan.
- Backlog LF-002…LF-012 disesuaikan dengan pekerjaan yang sudah ada dan gerbang terukur.
- ADR-01b/02b/11b/13–18 sinkron, ADR lama terkait ditandai digantikan/diterangkan.
- Image pin stabil ≥1.11 tercatat; `docker compose config --quiet` pass. Health container tetap BLOCKED sampai Docker daemon tersedia.
