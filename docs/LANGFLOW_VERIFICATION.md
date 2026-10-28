# Verifikasi Langflow — LF-001

**Tanggal:** 2026-10-29
**Pin kandidat:** `langflowai/langflow:1.12.2`, rilis stabil resmi terverifikasi saat audit.
**Batas bukti:** `docker-compose config --quiet` lulus dengan kredensial audit sementara; Docker daemon tidak aktif. Tidak ada hasil runtime yang diklaim lulus.

| Fitur/butir | Status dokumentasi | Spike lokal | Keputusan/fallback |
|---|---|---|---|
| Image 1.12.2 | tersedia | BLOCKED: Docker daemon tidak aktif | pin 1.12.2, health check saat Docker tersedia |
| Custom components | tersedia | BLOCKED | server-installed component dari `LANGFLOW_COMPONENTS_PATH` |
| `ALLOW_CUSTOM_COMPONENTS=false` | tersedia | BLOCKED | allow-list operator; bukan satu-satunya pengaman |
| Import component | `lfx` modern; `langflow.custom` kompatibel | BLOCKED | gunakan `lfx`, uji legacy |
| `/api/v1/run/{flow_id}` | API key wajib | BLOCKED | FastAPI memakai `x-api-key` |
| Workflow API v2 | beta: sync/stream/background + SSE | BLOCKED | pakai setelah spike; v1 dan lokal tetap fallback |
| Event langkah SSE | `STEP_STARTED`/`STEP_FINISHED` didokumentasikan | BLOCKED | FastAPI relay, bukan browser langsung |
| Resume HITL | `POST /api/v2/workflows/{job_id}/resume`, `request_id` + `decision` | BLOCKED | D3: coba relay API; bila gagal UI→FastAPI, Flow 05 Playground/Bob/MCP |
| Human Input/tool approval | tersedia | BLOCKED | draft_review selalu perlu persetujuan manusia |
| Policies/ToolGuard | beta | BLOCKED | tambahan; guard hasil generate direview/dites/dikomit |
| Traces | tersedia | BLOCKED | LF-006 simpan trace id di run dan audit |
| IBM/watsonx | bundle IBM didokumentasikan | BLOCKED | periksa saat image aktif; `lfx-ibm` P1 jika belum tersedia |

## Konfigurasi keamanan

- Kredensial eksplisit, `LANGFLOW_AUTO_LOGIN=false`, tanpa password bawaan.
- `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false`, `LANGFLOW_ALLOW_PUBLIC_CUSTOM_COMPONENTS=false`, `LANGFLOW_BLOCK_CODE_INTERPRETER_COMPONENTS=true`, dan pembatasan file lokal aktif.
- API key hanya FastAPI/environment; Langflow di jaringan internal dan port demo loopback-only.
- Breaking changes yang ditindaklanjuti: tidak ada bootstrap password/auto-login, Workflow API v2 beta, dan provider/bundle termasuk PyTorch/IBM tidak diasumsikan terpasang.

## Protokol spike setelah runtime tersedia

1. `docker compose config`, build, health check versi 1.12.2.
2. Muat komponen allow-list dan pastikan custom code/editor tidak dapat berjalan.
3. Jalankan v1 dan v2 sync/stream/background dengan `x-api-key`; cek SSE.
4. Pause Human Input, simpan `job_id/request_id`, lalu resume lewat relay FastAPI.
5. Catat hasil HTTP, versi/bundle IBM, dan fallback D3 jika resume tidak layak.

## Bukti eksekusi LF-001

- `docker-compose config --quiet` **lulus** pada 2026-10-29 dengan nilai audit sementara untuk tiga variabel kredensial wajib; tidak ada rahasia repo digunakan.
- `docker info --format {{.ServerVersion}}` **gagal** karena named pipe `dockerDesktopLinuxEngine` tidak ada. Build, `up`, health endpoint, API v1/v2, SSE, dan HITL resume tetap **BLOCKED**, bukan gagal aplikasi.
- `pytest tests/test_fase3_ai_orchestration.py -q` keluar `0` (19 passed, 1 skipped); Windows/pyreadline3 menulis warning destructor setelah tes selesai.
