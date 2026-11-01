# Verifikasi Langflow — LF-001

**Tanggal:** 2026-10-29  
**Target image:** `langflowai/langflow:1.13.0`  
**Virtualenv lokal:** Langflow/LFX 1.12.5; `lfx-ibm` 0.2.5  
**Status runtime target:** BLOCKED — Docker daemon tidak tersedia. Jangan menyebut flow/container lulus runtime sampai `docker compose up` dan smoke test diulang pada pin 1.13.0.

## Bukti lokal

- Rilis resmi Langflow terbaru yang ditemukan pada tanggal audit adalah 1.13.0 (`https://github.com/langflow-ai/langflow/releases/latest`, rilis v1.13.0, 2026-10-22); tag image DockerHub 1.13.0 aktif (`https://hub.docker.com/v2/repositories/langflowai/langflow/tags/1.13.0`).
- Package lokal menunjukkan `langflow=1.12.5`, `lfx-ibm=0.2.5`; ini bukan versi image yang dipin.
- `docker compose config --quiet`: lulus. `docker version`: daemon tidak tersedia. Tidak ada container start/health test.
- Tes terarah: `pytest tests/test_analysis_orchestrator.py tests/test_priomedrec_core.py tests/test_pmr_components.py -q` → 6 passed.
- Discovery inline LFX lokal 1.12.5 pada `langflow/components/` → 13 komponen terdaftar, 1 error `ModuleNotFoundError: _lfx_ext`. Import biasa sebagai `langflow.components.priomedrec.*` juga gagal karena jalur itu bukan paket Langflow bawaan. Perlu memperbaiki/test jalur loader yang didukung sebelum mengklaim komponen muncul di kanvas.
- Paket `lfx-ibm` terpasang lokal dan flow eksperimental memuat tipe `WatsonxAIComponent`; keduanya belum diverifikasi pada container pin 1.13.0.

## Matriks fitur

“Tersedia di docs/source” bukan bukti runtime. Semua fitur yang memerlukan server/kanvas diberi status runtime BLOCKED.

| Fitur/butir | Dokumentasi resmi / source | Spike dan hasil | Keputusan/fallback |
|---|---|---|---|
| Pin image Langflow | Release resmi v1.13.0 dan tag DockerHub aktif | Compose config valid; Docker daemon unavailable | Pin 1.13.0; health/build test menunggu Docker |
| Custom Components & import LFX | [Custom components](https://docs.langflow.org/components-custom-components); LFX 1.12.5 loader source | 13 ditemukan, satu import error; bukan lulus | Perbaiki bundle imports; uji loader image 1.13.0 |
| `LANGFLOW_COMPONENTS_PATH` + `LANGFLOW_ALLOW_CUSTOM_COMPONENTS` | [Block custom components / allow-list](https://docs.langflow.org/deployment-block-custom-components) | Semantik docs: path operator-managed tetap diizinkan saat kode custom flow diblokir; runtime belum diuji | Pertahankan flag false, path read-only server-managed; uji path dan penolakan custom code |
| Agent + Tools/Tool Mode | [Agent](https://docs.langflow.org/agents) | Ada Agent/PythonREPL pada flow eksperimental; adapter PMR tertentu menandai `tool_mode`; belum dirun | Bangun Flow 04 hanya dengan tools baca atau draft; jangan aktifkan PythonREPL write |
| Run Flow / flow-as-tool | Katalog fitur plan; belum ada target flow 00–06 | Belum ada flow run-to-flow dalam flow aktif | P0 setelah subflow 01–03 diekspor; fallback lokal |
| Human Input / tool approval | [HITL](https://docs.langflow.org/human-in-the-loop) | Docs mengonfirmasi checkpoint/branch; belum ada Flow 05 | Tool review tetap DRAFT; verifikasi checkpoint dan cabang saat runtime |
| Resume HITL eksternal | API v2 route tersedia pada source package lokal 1.12.5: `POST /api/v2/workflows/{job_id}/resume` | Tidak dipanggil; pin 1.13.0 tidak berjalan | D3: spike resume melalui relay FastAPI; jika gagal, UI→FastAPI untuk keputusan resmi dan Flow 05 untuk Playground/Bob/MCP |
| Workflow API v2 + streaming/SSE | Source lokal 1.12.5 memiliki mode sync/stream/background, job dan events | Tidak ada request runtime; docs/source saja bukan bukti kestabilan | Smoke test tiap mode dan SSE pada 1.13.0; fallback v1/client lokal |
| `/api/v1/run/{flow_id}` + API key | [Run a flow](https://docs.langflow.org/api-flows-run) | Client mengirim `x-api-key`; tidak ada server call; master flow ID belum disediakan di `.env.example` | Pertahankan key server-side; tambahkan ID hanya setelah flow 00 tersedia |
| Policies / ToolGuard | [Policies](https://docs.langflow.org/policies) | Docs menyatakan guard dibuat pada Generate dan dipakai saat Guard; tidak ada node/policy di flow repo | Lapisan tambahan; hasil generate ditinjau, dites adversarial, dikomit; guardrail API tetap wajib |
| MCP server dan MCP client | [MCP server](https://docs.langflow.org/mcp-server), [MCP client](https://docs.langflow.org/mcp-client) | Repo hanya mengonfigurasi MCP lokal ke FastAPI; sesi tidak memiliki Langflow MCP | Belum ada Bob↔Langflow atau flow→MCP; pertahankan FastAPI API tools dengan token terbatas |
| Traces per run/komponen | Fitur didokumentasikan oleh Langflow | Tidak ada `trace_id` dari runtime; API hanya mem-forward field bila tersedia | Trace FastAPI/audit belum terpenuhi; simpan saat LF-006 |
| Memory per encounter | Fitur Langflow tersedia pada dokumentasi produk | Tidak ada node Memory aktif atau uji retensi | P1 untuk Copilot; memori sintetis per encounter dan retensi terbatas |
| Knowledge Base/RAG | Fitur Langflow tersedia pada dokumentasi produk | Tidak ada node KB/RAG aktif | P1; hanya sumber penjelasan dengan sitasi, bukan detektor klinis |
| Router, Conditional, Loop, Parser, Structured Output, Prompt | Komponen bawaan tersedia pada produk | Router ada di flow eksperimental; belum ada flow target yang diuji | Pakai untuk routing/narasi saja; hasil klinis tetap fungsi deterministik |
| Global model providers | Dokumentasi Agent menunjuk konfigurasi provider global | Provider flow eksperimental belum dijalankan | Nama model dari konfigurasi; template deterministik sebagai fallback akhir |
| `lfx-ibm` / watsonx | Paket lokal `lfx-ibm` 0.2.5; komponen watsonx disebut pada flow eksperimental | Ada di venv saja, tidak dikonfirmasi dalam Docker 1.13.0 | P1; bila tidak ada, install bundle IBM secara eksplisit setelah uji dependency |
| Flow DevOps Toolkit SDK | Fitur pada rencana; belum ada SDK/CI flow test yang terkonfirmasi | Tidak ada spike | P1; sampai itu tersedia, JSON flow terversi dan tes API eksplisit |
| A2A | API/fitur pada versi Langflow modern | Belum ada A2A flow/config | P1; tidak menghalangi P0 |
| OpenTelemetry | Fitur produk terdokumentasi | Belum ada export OTLP diuji | P1; default tidak mengirim prompt/PII |
| AG-UI | Workflow streaming terdokumentasi pada rencana versi | Belum ada klien/stream diuji | P1; SSE relay FastAPI sebagai pilihan P0 |
| Breaking changes 1.11 | Catatan migrasi perlu dicocokkan dengan image pin | Kredensial pada Compose diwajibkan melalui env; belum cek startup 1.13.0/PyTorch bundle | Verifikasi clean startup, tidak ada password default, dan availability komponen PyTorch sebelum mengandalkan flow lama |

## Konfigurasi dan langkah uji setelah Docker tersedia

1. Pastikan Dockerfile/Compose tetap pada tag 1.13.0; jalankan `docker compose config --quiet`, build, `docker compose up -d langflow`, dan `/health`; catat versi container aktual.
2. Pastikan hanya komponen server-managed dari path read-only yang dimuat saat `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false`; pastikan custom code pengguna ditolak. Perbaiki `ModuleNotFoundError: _lfx_ext` pada loader 1.12.5 lalu ulangi pada image target.
3. Import flow JSON; jalankan `/api/v1/run/{flow_id}` dengan `x-api-key` server-side dan uji mode Workflow v2 sync/stream/background serta event SSE.
4. Pause Human Input, simpan `job_id`/`request_id`, resume melalui FastAPI relay, lalu validasi permission, idempotensi, dan cabang yang berjalan.
5. Catat versi, status, respons HTTP, hasil step, dan trace tanpa menulis secret/PII atau data klinis riil ke log/dokumen.

## Referensi resmi yang ditinjau

- [Langflow releases](https://github.com/langflow-ai/langflow/releases/latest)
- [Docker image 1.13.0](https://hub.docker.com/v2/repositories/langflowai/langflow/tags/1.13.0)
- [Custom components](https://docs.langflow.org/components-custom-components) dan [custom-component security/allow-list](https://docs.langflow.org/deployment-block-custom-components)
- [Agent](https://docs.langflow.org/agents), [HITL](https://docs.langflow.org/human-in-the-loop), [Policies](https://docs.langflow.org/policies)
- [Flow run API](https://docs.langflow.org/api-flows-run), [MCP server](https://docs.langflow.org/mcp-server), [MCP client](https://docs.langflow.org/mcp-client)
