# Rencana Implementasi Langflow-first

S1–S14 tetap berlaku: fakta klinis deterministik, LLM hanya narasi, FastAPI audit resmi, dan fallback lokal wajib.

| ID | Perubahan | Target/dependensi | Kriteria selesai |
|---|---|---|---|
| LF-002 | `priomedrec_core` pure Python; `run_phase_a/b/full`, kontrak tunggal | `src/`, `api/services/` | tes lama hijau dan keluaran tak berubah |
| LF-003 | ≥14 adaptor PMR tipis | `langflow/components/priomedrec/` | unit test; tool mode hanya baca/draft |
| LF-004 | image memuat core/komponen | Dockerfile/compose | komponen tampil; opsi B HTTP bila konflik dependency |
| LF-005 | Flow 01/02/03 + 00 master | `langflow/flows/` | flow JSON tanpa rahasia; Flow 03 guardrail/template |
| LF-006 | client/orchestrator/verifier/trace/SSE | `api/services/` | timeout/retry/circuit breaker; tujuh cek verifier |
| LF-007 | paritas dan fallback | `tests/` | 100% temuan/tier; skor ±1e-6; timeout→lokal |
| LF-008 | Flow 04 Copilot | Agent/tools/memory/KB/policy | adversarial green; sumber wajib; draft approval |
| LF-009 | bukti visual | `web/` + SSE | stepper/badge/trace/fallback; tanpa direct call |
| LF-010 | Flow 05 HITL | Human Input + `/review` | resume atau D3 fallback terdokumentasi |
| LF-011 | Bob↔Langflow MCP | MCP settings/server | semua write DRAFT |
| LF-012 | demo/runbook | docs/scripts | demo 5 menit/checklist/fallback video |

P1 sesudah P0: LF-020 Discharge; 021 A2A; 022 watsonx; 023 OpenTelemetry; 024 AG-UI; 025 Flow Map; 026 webhook; 027 KB; 028 Flow DevOps CI.

Urutan: `001 → 002 → 003 → 004 → 005 → 006/007 → 009 → 008 → 010 → 011 → 012`. Setiap ID: tes dahulu, perubahan minimum, dokumentasi, satu commit. Jangan ubah `models/*.pkl`, `data/raw/`, `medrec_xgboost/`, atau `_archive/`.
