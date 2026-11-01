# Changelog

All notable changes to PrioMed-Rec are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

## [Unreleased]

### Added
- LF-001 Langflow-first audit, verification matrix, implementation backlog, and ADR-01b/02b/11b/13–18.
- Isolated, pinned Langflow 1.13.0 image configuration with explicit credentials and server-managed custom-component path.
- LF-001 code audit corrected to reflect the existing partial `priomedrec_core`, 19 PMR adapters, legacy flows, and runtime blockers.

### Security
- Browser-to-Langflow direct access remains prohibited; the Langflow demo port is loopback-only and API keys stay server-side.
- Langflow runtime health remains unverified because the Docker daemon is unavailable; no runtime claim is made.

## [3.0.0] - 2025 (Fase 3 — Orkestrasi AI selesai)

### Added — AI Orchestration (Fase 3)
- **A-301**: `web/src/api/langflow.ts` ditulis ulang — semua panggilan AI dialihkan dari
  browser→Langflow menjadi browser→`/api/v1/ai/*` (AI Gateway). Pelanggaran ADR-02/S7 **DIPERBAIKI**.
  Legacy stubs dipertahankan untuk backward compat (deprecated). `web/src/lib/apiClient.ts`
  ditambah `apiGet<T>()` + `apiPost<T>()` generic helpers.
- **A-302**: `api/services/guardrail_service.py` — 9 cek keselamatan:
  #1 forbidden clinical phrases (EN+ID), #2+#9 prompt injection, #3 confirmed error,
  #4 priority reassignment, #5 interaction claim (warning), #6 schema format (warning),
  #7 dose fidelity (warning), #8 non-Latin language detection;
  `sanitize_user_note()` + `record_call()` + `get_metrics()`.
- **A-303**: `api/routes/v1/health.py` — `GET /api/v1/health` (liveness) +
  `GET /api/v1/health/deps` (auth required) — dependency health check: DB, ML model,
  LLM providers, **Langflow flow SHA-256 hashes**, guardrail version, knowledge base files.
- **A-304/F-214**: `web/src/components/CopilotDrawer.tsx` — Copilot AI Drawer (slide-in FAB)
  di `CaseWorkspacePage`. Quick questions, chat UI, source label, AI Draft Label (S12).
  Semua call ke `/api/v1/ai/copilot` (ADR-02 compliant).
- **A-306**: `api/services/llm_chain_service.py` — LLM fallback chain berbasis konfigurasi:
  gemini→groq→watsonx→ollama→template. Model TIDAK di-hardcode (semua dari env).
  Re-prompt maks 2× saat guardrail gagal; template deterministik sebagai fallback terakhir.
- **A-307**: `mcp_server.py` ditulis ulang — 5 tools:
  `get_worklist` (read), `rank_admission_risk` (read), `detect_medication_discrepancy` (read),
  `lookup_drug_knowledge` (read), `draft_pharmacist_review` (**DRAFT only**, actor_type=agent_via_mcp).
  `record_pharmacist_review` (final) **DIHAPUS** — sesuai ADR-07/S6.
- **A-307b**: `api/routes/v1/knowledge.py` — `POST /api/v1/knowledge/lookup` —
  endpoint lookup knowledge base (alias/interaction/allergy/high_alert).
- **A-308**: `sanitize_user_note()` + `<user_note>` wrapper sudah di `guardrail_service.py`
  dan dipakai di semua AI calls (copilot endpoint + copilot_answer()).
- **A-309**: `prompts/sbar_v1.md` + `prompts/copilot_v1.md` — prompt berversi sesuai Lampiran C.
- **A-310**: `docs/BOB_USAGE_LOG.md` — log lengkap peran IBM Bob per fase (7 peran, 3 fase).

### Changed (Fase 3)
- `api/main.py`: tambah health_v1_router, knowledge_v1_router.
- `web/src/pages/CaseWorkspacePage.tsx`: integrasi `CopilotDrawer` + FAB button.
- `web/src/api/client.ts`: fix `langflowAnalyze` call (param 3 dihapus, sesuai API baru).

### Security (Fase 3)
- **ADR-02 violation DIPERBAIKI**: `langflow.ts` tidak lagi memanggil Langflow dari browser.
  Semua AI calls: `UI → POST /api/v1/ai/sbar|copilot → FastAPI → LLM chain → guardrail → UI`.
- **ADR-07 violation DIPERBAIKI**: MCP tool `record_pharmacist_review` (final) diganti dengan
  `draft_pharmacist_review` (DRAFT only + actor_type=agent_via_mcp).

### Tests (Fase 3)
- `tests/test_fase3_ai_orchestration.py`: 20 passed, 1 skipped (MCP introspection)
  - S5: 5 tes LLM down → template (no exception)
  - S6: 4 tes guardrail rejection (forbidden phrase EN/ID, injection, confirmed error)
  - 3 tes guardrail warnings (interaction claim, dose fidelity)
  - 4 tes sanitize_user_note
  - 2 tes MCP safety (draft status, actor_type)
- **Total tes**: 57 passed + 1 skipped (semua Fase 1+3 tes gabungan)

### Known Issues / Pending (setelah Fase 3)
- Fase 4: ML ablation, model_A vs model_B, golden test set (V-501)
- Fase 5: CI GitHub Actions, docker-compose validation, DEMO_SCRIPT.md
- SSE notifikasi real-time belum ada (polling masih dipakai)
- Playwright e2e tests belum dibuat (F-220)


## [2.0.0] - 2025 (Fase 1–2 Demo-Ready)

### Added — Backend (Fase 1)
- **B-101/B-102**: SQLAlchemy 2.x ORM + Alembic migrations; 17 tabel baru
  (users, encounters, bpmh_items, analysis_runs, discrepancies, sbar_drafts, sbar_revisions,
  status_history, sla_events, notifications, drug_alias, sla_config, audit_entries)
  + `session_scope()` context manager untuk script/service non-FastAPI
- **B-103**: JWT HS256 (access 15m + refresh 7d) + RBAC 5 peran
  (PHARMACIST, TECHNICIAN, COORDINATOR, ADMIN, AUDITOR) + argon2-cffi password hashing;
  `POST /api/v1/auth/login|refresh|logout|me`
- **B-104**: State machine 10 status + guard transisi + `status_history`;
  `api/services/case_state_service.py`
- **B-105**: Composite priority `max(ml_tier, rules_floor, sla_floor)` + `priority_reasons[]`;
  `api/services/priority_service.py`
- **B-106**: SLA service (2h/8h/24h default) + APScheduler 60s idempoten + Notification model;
  `api/services/sla_service.py`, `api/tasks/scheduler.py`
- **B-107**: Audit hash-chain SHA-256 append-only + `GET /api/v1/audit/verify?full=true`;
  `api/services/audit_service.py`
- **B-108**: `POST /api/v1/encounters/{id}/review` — APPROVE/EDIT/REJECT/ESCALATE/DRAFT_REVIEW
  + alasan wajib + Idempotency-Key + If-Match; `api/routes/v1/review.py`
- **B-109**: `configs/allergy_rules.json` — aturan reaksi silang (DRAFT)
- **B-110**: Severity tier 1/2/3 pada `configs/discrepancy_rules.json` (rules-0.2.0)
- **B-111**: Normalizer 5 tahap (exact→alias→fuzzy→KFA stub→unresolved) +
  `knowledge/drug_alias.csv` (250+ alias obat Indonesia, DRAFT)
- **B-112**: High-Alert hard stop server-side: APPROVE ditolak 422 jika HA belum dikonfirmasi
- **B-113/B-114**: `GET /api/v1/worklist` (filter/sort/pagination) + claim/release + If-Match;
  `api/routes/v1/worklist.py`
- **B-115**: `scripts/seed_demo.py --reset` — 10 skenario demo deterministik S1–S10
- **B-116**: Envelope error seragam + request_id + `/api/v1` router; `api/errors.py`
- **Config**: `JWT_SECRET_KEY`, `DATABASE_URL`, `SERVICE_API_KEY_*` di `.env.example`
- `argon2-cffi` ditambahkan ke `requirements.txt`

### Added — Frontend (Fase 2)
- **F-201**: `LoginPage` + `IdleLockOverlay` + auth store (Zustand);
  JWT dari backend, idle lock 30 menit
- **F-202**: TanStack Query v5 + `apiClient.ts` (authenticated, auto-refresh);
  `QueryClientProvider` di `main.tsx`
- **F-203**: `WorklistPageV2` — tier badges, SLA countdown, klaim, filter tier+search, polling 30s,
  loading/empty/error states + "Coba Lagi"; `TierBadge`, `SlaCountdown`
- **F-204/205/206**: `CaseWorkspacePage` — header sticky, tab Bandingkan/Temuan/SBAR/Riwayat,
  tier badge + SLA, temuan kolaps tier-3, timeline riwayat audit
- **F-207**: `AiDraftLabel` — label permanen "Draf AI — wajib diverifikasi apoteker" (S12)
- **F-208**: `ReviewActionBar` (APPROVE/EDIT/REJECT/ESCALATE/DRAFT_REVIEW + undo 10d) +
  `HighAlertConfirmModal` (blok APPROVE jika HA belum konfirmasi)
- **F-210**: `DashboardPage` — KPI cards (total/HIGH/MEDIUM/LOW), SLA panel (breach/warning),
  system health (DB/ML/Rules/API)
- **F-212**: `AuditLogPageV2` — tabel audit + tombol "Verifikasi Rantai Hash" (ADMIN/AUDITOR saja)
- **Vite proxy**: `/api/v1` → FastAPI (no-rewrite) + legacy `/api` → FastAPI (strip prefix)
- `@tanstack/react-query`, `zustand`, `react-router-dom`, `zod` ditambahkan ke `package.json`
- `web/.env.example` diperbarui (VITE_DATA_MODE, VITE_API_KEY)

### Changed
- `api/main.py`: mount scheduler startup/shutdown di lifespan; daftarkan auth/worklist/review/audit v1 routers
- `api/config.py`: tambah `JWT_SECRET_KEY`, `DATABASE_URL`, `SERVICE_API_KEY_*`
- `web/src/types/clinical.ts`: tambah `WorklistItemV1`, perluas `ActionType` (ESCALATE, DRAFT_REVIEW)
- `web/src/App.tsx`: integrasi auth guard + WorklistPageV2/CaseWorkspacePage/DashboardPage/AuditLogPageV2

### Security
- Identitas aktor selalu dari JWT token, tidak dari body request (ADR-08)
- Browser tidak pernah memanggil Langflow/LLM langsung (ADR-02) — masih ada `langflow.ts` legacy
  yang akan dipindahkan ke AI Gateway di Fase 3 (A-301)

### Known Issues / Pending
- `web/src/api/langflow.ts` masih memanggil Langflow dari browser (ADR-02 violation) → A-301
- SSE notifikasi real-time belum diimplementasikan (APScheduler + Notification ada) → F-203+
- Playwright e2e tests belum dibuat → F-220

## [1.2.0] - 2026-10-26

### Added
- SQLite persistence layer (api/database.py) — BPMH and audit trail now survive server restart
- API key authentication (api/auth.py) — pharmacist and readonly roles
- Drug class map (configs/drug_class_map.json) — 60 Indonesian medications for POSSIBLE_SUBSTITUTION detection
- LLM anonymization layer (src/llm/anonymizer.py) — PII redacted before sending to external LLM
- LLM disclaimer watermark — all LLM outputs now carry mandatory verification notice
- GET /audit endpoint — filter audit log by patient, action, date range
- GET /worklist endpoint — real-time patient status from database
- GET/POST /settings/high-alert — hospital-specific high-alert medication management
- Centralized config (api/config.py) — all settings from environment variables
- Structured logging (api/logging_config.py)
- Docker deployment (Dockerfile.api, Dockerfile.web, docker-compose.yml)
- User-friendly error messages in Bahasa Indonesia (web/src/api/errors.ts)
- BPMH auto-load in /analyze — dispositions automatically applied to rule engine
- Tutorial content in Bahasa Indonesia
- docs/DEPLOYMENT.md — step-by-step IT guide

### Changed
- BPMH storage: in-memory dict → SQLite (data survives restart)
- Audit storage: in-memory → SQLite
- Ward config: in-memory → SQLite
- /analyze: now auto-loads BPMH and applies dispositions to rule engine
- discrepancy_engine: auto-loads drug_class_map.json if not injected

### Fixed
- Patient status not synced across sessions
- LLM output missing mandatory disclaimer

## [1.1.0] - 2025

### Added
- XGBoost ML model (AUROC 0.89, 10 LEAKAGE_SAFE features)
- Rule engine: disposition-aware omission detection (5 flag types)
- Safety flags engine: ISMP/NTI/Beers PIM (114 medications)
- Output validator: 14 blocked phrases in Indonesian
- React frontend: 6 pages (Worklist, BPMH, Analysis, Audit, Settings, Tutorial)
- FastAPI backend: 11 endpoints
- LLM multi-provider fallback chain (Gemini → Groq)
- Synthetic mode for demo/development

### model_version: xgb_v3_leakage_safe
### rule_version: rules-disposition-v2
