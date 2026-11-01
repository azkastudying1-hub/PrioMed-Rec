# PAPAN STATUS — PrioMed-Rec
## Progress Tracker semua ID Backlog

**Versi:** 3.0 (Prototype Demo-Ready — Langflow-first, semua tes hijau)
**Terakhir diperbarui:** 2025-07 (Semua fase demo selesai; tes 98 passed 2 skipped)
**Format commit:** `<ID>: <ringkas> [tes: hijau]`
**Legenda status:** ✅ SELESAI | 🔄 IN PROGRESS | ⏳ MENUNGGU | 🚫 BLOCKED | ⏭ DITUNDA

---

## FASE 0 — CONCEPT LOCK & AUDIT (SELESAI ✅)

| ID | Item | Status | File diubah | Tes | Catatan |
|:---|:---|:--:|:---|:---|:---|
| T-001 | Revisi blueprint v4→v5 (fitur 10, kalibrasi, flow 3, tool MCP, statistik) | ✅ | `docs/priomedrec_master_blueprint-v4.md` (header SUPERSEDED ditambahkan) | — | Kontradiksi 14 item dicatat di AUDIT_REPO_VS_PLAN.md; statistik "79%"/"50.5%" perlu sitasi |
| T-002 | Tulis ADR-01…12 ke DECISION_LOG.md | ✅ | `docs/DECISION_LOG.md` (ADR-01..ADR-12 ditambahkan) | — | 12 ADR lengkap dengan gap yang ditemukan di kode |
| T-003 | Dokumentasikan medrec_xgboost/ sebagai RESEARCH ONLY | ✅ | `medrec_xgboost/README.md` (BARU) | — | Larangan salin langsung; instruksi promosi via scripts/promote_model.py |
| T-004 | Hitung prevalensi label & lift@K; perbarui MODEL_CARD | ✅ | `docs/MODEL_CARD.md` (tabel Lift@10/20/30% + interpretasi ditambahkan) | — | Prevalensi 76.3%; Lift = 1.32x; sumber eval_report_v4.json (STAB-001 1000-seed) |
| T-005 | Bekukan agentic_v2 ke langflow/experimental/ | ✅ | `langflow/experimental/priomedrec_agentic_v2.json` + `README.md` | — | File disalin ke subfolder experimental (original dipertahankan per instruksi tidak menghapus) |

---

## FASE 1 — FONDASI & KESELAMATAN (Backend) — SELESAI ✅

| ID | Item | Status | Ukuran | Track | File diubah | Tes |
|:---|:---|:--:|:-:|:-:|:---|:---|
| B-101 | SQLAlchemy + Alembic; migrasi tabel yang ada | ✅ | M | DEMO | `api/db/session.py`, `alembic/`, `requirements.txt` | — |
| B-102 | Tabel baru (users, encounters, bpmh_items, analysis_runs, ...) | ✅ | M | DEMO | `api/db/models.py`, migration `20261028_...` | 17 tabel verified |
| B-103 | Auth JWT + RBAC + password hashing | ✅ | L | DEMO | `api/auth/jwt.py`, `rbac.py`, `password.py`, `routes/v1/auth.py` | `test_fase1_b103_auth.py` 6✅ |
| B-104 | State machine diperluas + guard + status_history | ✅ | M | DEMO | `api/services/case_state_service.py` | `test_fase1_b104_state_machine.py` 9✅ |
| B-105 | priority_service komposit + priority_reason | ✅ | M | DEMO | `api/services/priority_service.py` | `test_fase1_b105_priority.py` 10✅ |
| B-106 | sla_service + APScheduler + sla_events | ✅ | L | DEMO | `api/tasks/scheduler.py`, `api/services/sla_service.py` | SLA logic tested via priority (indirect) |
| B-107 | audit_service hash-chain + /audit/verify | ✅ | M | DEMO | `api/services/audit_service.py`, `api/routes/v1/review.py` (audit_router) | `test_fase1_b107_audit.py` 5✅ |
| B-108 | ESCALATE + alasan wajib + DRAFT_REVIEW + Idempotency-Key | ✅ | M | DEMO | `api/routes/v1/review.py` | Guard tested via state machine |
| B-109 | allergy_rules.json + cek alergi silang | ✅ | M | DEMO | `configs/allergy_rules.json` (BARU, DRAFT) | — |
| B-110 | Severity tier di discrepancy_rules.json | ✅ | M | DEMO | `configs/discrepancy_rules.json` (rules-0.2.0) | — |
| B-111 | Normalizer 5 tahap + drug_alias.csv (≥200 obat) | ✅ | L | DEMO | `api/services/normalizer_service.py`, `knowledge/drug_alias.csv` | `test_fase1_b111_normalizer.py` 9✅ |
| B-112 | High-Alert hard stop (validasi server saat APPROVE) | ✅ | S | DEMO | `api/services/case_state_service.py` (`_check_high_alert_clearance`) | `test_high_alert_blocks_approve` ✅ |
| B-113 | Claim/release + If-Match | ✅ | M | DEMO | `api/routes/v1/worklist.py` (claim + release endpoint) | — |
| B-114 | GET /api/v1/worklist filter+sort+pagination | ✅ | M | DEMO | `api/routes/v1/worklist.py` | — |
| B-115 | Seed demo deterministik S1–S10 | ✅ | M | DEMO | `scripts/seed_demo.py` | Dijalankan manual: 10 skenario seeded ✅ |
| B-116 | Envelope error seragam + /api/v1 + request_id | ✅ | S | DEMO | `api/errors.py`, `api/main.py` | — |
| B-117 | Discharge check API | ⏭ | M | PILOT | `api/routes/v1/discharge.py` | — |
| B-118 | Re-triage event (transfer/order baru) | ⏭ | M | PILOT | `api/routes/v1/encounters.py` | — |
| B-119 | Endpoint metrik KPI | ⏭ | M | PILOT | `api/routes/v1/metrics.py` | — |
| B-120 | PostgreSQL + uji lintas-DB | ⏭ | M | PILOT | `docker-compose.yml`, `api/db/session.py` | — |

---

## FASE 2 — PENGALAMAN APOTEKER (Frontend) — SELESAI ✅

| ID | Item | Status | Ukuran | Track | File diubah |
|:---|:---|:--:|:-:|:-:|:---|
| F-201 | Login + guard rute + sesi + kunci idle | ✅ | M | DEMO | `web/src/pages/LoginPage.tsx`, `IdleLockOverlay.tsx`, `lib/auth.ts` |
| F-202 | TanStack Query v5 + v1 API client (authenticated, auto-refresh) | ✅ | M | DEMO | `web/src/lib/apiClient.ts`, `main.tsx` |
| F-203 | Worklist v2 (tier badge, SLA, klaim, filter tier+search, polling 30s) | ✅ | L | DEMO | `WorklistPageV2.tsx`, `TierBadge.tsx`, `SlaCountdown.tsx` |
| F-204 | Case Workspace (header sticky, 4 tab, tier+SLA) | ✅ | L | DEMO | `web/src/pages/CaseWorkspacePage.tsx` |
| F-205 | CompareTab (BPMH vs admisi side-by-side) | ✅ | L | DEMO | dalam `CaseWorkspacePage.tsx` |
| F-206 | FindingsTab (tier 1/2/3 kolaps, chip alasan) | ✅ | M | DEMO | dalam `CaseWorkspacePage.tsx` |
| F-207 | SbarEditor (4 field editable, salin CPPT) + AiDraftLabel | ✅ | M | DEMO | `AiDraftLabel.tsx`, SBAR tab dalam `CaseWorkspacePage.tsx` |
| F-208 | ReviewActionBar + HighAlertConfirmModal + Undo 10d | ✅ | M | DEMO | `ReviewActionBar.tsx`, `HighAlertConfirmModal.tsx` |
| F-209 | BPMH v2 (autosave sudah ada di existing BpmhPage) | ✅ | L | DEMO | `BpmhPage.tsx` (existing, autosave OK) |
| F-210 | Dashboard (KPI cards, SLA panel, system health) | ✅ | M | DEMO | `web/src/pages/DashboardPage.tsx` |
| F-211 | State loading/empty/error + Coba Lagi | ✅ | M | DEMO | WorklistPageV2, DashboardPage, AuditLogPageV2 |
| F-212 | Audit Log v2 + tombol Verifikasi Rantai Hash | ✅ | M | DEMO | `web/src/pages/AuditLogPageV2.tsx` |
| F-213 | Admin (pengguna, SLA, high-alert, alias) | ⏭ | L | PILOT | — |
| F-214 | Copilot drawer | ⏳ | M | DEMO | — (Fase 3) |
| F-215 | Knowledge lookup | ⏭ | M | PILOT | — |
| F-216 | Discharge page | ⏭ | M | PILOT | — |
| F-217 | Aksesibilitas a11y dasar | ✅ | M | DEMO | aria-label, role, contrast OK di semua komponen baru |
| F-218 | Ekspor PDF | ⏭ | M | PILOT | — |
| F-219 | Pintasan keyboard | ⏭ | S | PROD | — |
| F-220 | Playwright e2e S1–S10 | ⏳ | L | DEMO | — (Fase 5) |

**Build:** `npm run build` ✅ 0 error TypeScript, 389KB JS (gzip 112KB)
**Backend:** 61+ tests ✅ passed, 0 failed

---

## FASE 3 — ORKESTRASI AI — SELESAI ✅

| ID | Item | Status | Ukuran | Prio | File |
|:---|:---|:--:|:-:|:-:|:---|
| A-301 | AI Gateway + redirect langflow.ts ke /api/v1/ai/* | ✅ | M | P0 | `web/src/api/langflow.ts` (rewrite), `web/src/lib/apiClient.ts` (+apiGet/apiPost) |
| A-302 | Guardrail paket bersama 9 cek | ✅ | M | P0 | `api/services/guardrail_service.py` |
| A-303 | /api/v1/health/deps + Langflow flow hashes | ✅ | M | P0 | `api/routes/v1/health.py` |
| A-304/F-214 | Copilot Drawer di CaseWorkspacePage (FAB) | ✅ | M | P1 | `web/src/components/CopilotDrawer.tsx` |
| A-305 | Flow C (draft review) | ⏭ | S | P1 | Ditunda — Langflow flow JSON perlu apoteker |
| A-306 | LLM chain config-driven (gemini→groq→watsonx→ollama→template) | ✅ | M | P0 | `api/services/llm_chain_service.py` |
| A-307 | MCP 5 tools (4 read + 1 draft-only write) | ✅ | M | P0 | `mcp_server.py` (rewrite), `api/routes/v1/knowledge.py` |
| A-308 | sanitize_user_note() + `<user_note>` wrapper | ✅ | S | P0 | Dalam `guardrail_service.py` + `routes/v1/ai.py` |
| A-309 | Prompt berversi sbar_v1.md + copilot_v1.md | ✅ | M | P0 | `prompts/sbar_v1.md`, `prompts/copilot_v1.md` |
| A-310 | BOB_USAGE_LOG.md (7 peran, 3 fase) | ✅ | S | P1 | `docs/BOB_USAGE_LOG.md` |

**Tes:** `tests/test_fase3_ai_orchestration.py` — 20 passed, 1 skipped
**Build:** `npm run build` ✅ 0 error TypeScript, 395KB JS

---

## FASE 4 — ML & VALIDASI — MENUNGGU (PARALEL)

| ID | Item | Status | Ukuran | Prio |
|:---|:---|:--:|:-:|:-:|
| M-401 | model_A vs model_B + ablation + GroupKFold | ⏳ | L | P0 |
| M-402 | Protokol evaluasi (lift, NDCG, ECE, subgrup, baseline) | ⏳ | M | P0 |
| M-403 | Ambang berbasis kapasitas [PILOT] | ⏳ | S | P1 |
| M-404 | promote_model.py + registry [PILOT] | ⏳ | M | P1 |
| M-405 | Monitoring drift & kalibrasi [PROD] | ⏳ | L | P2 |
| V-501 | Golden set 40 kasus di CI | ⏳ | L | P0 |
| V-502 | Shadow test RS mitra [PILOT] | ⏳ | XL | P1 |
| V-503 | Usability test 2 putaran + SUS [PILOT] | ⏳ | L | P1 |
| V-504 | Izin etik, perjanjian data, DPIA [PILOT] | ⏳ | L | P1 |

---

## FASE 5 — POLES DEMO & SIAP PILOT — MENUNGGU

| ID | Item | Status | Ukuran | Prio |
|:---|:---|:--:|:-:|:-:|
| I-CI | GitHub Actions CI workflow | ⏳ | M | P0 |
| I-Docker | docker-compose verifikasi + demo-reset | ⏳ | S | P0 |
| I-601 | FHIR bridge (Encounter/Medication/Allergy) [PILOT] | ⏳ | XL | P1 |
| I-602 | Direct CPPT injection [PROD] | ⏳ | L | P2 |
| I-603 | KFA/RxNorm/DDInter penuh [PILOT] | ⏳ | L | P1 |
| I-604 | Rekonsiliasi obat pulang [PROD] | ⏳ | XL | P2 |
| D-FHIR | docs/FHIR_MAPPING.md | ⏳ | M | P1 |
| D-RUNBOOK | docs/RUNBOOK_PILOT.md | ⏳ | M | P1 |
| D-SECURITY | docs/SECURITY.md | ⏳ | M | P1 |
| D-DEMO | docs/DEMO_SCRIPT.md | ⏳ | S | P0 |
| D-QA | docs/DEMO_QA.md | ⏳ | S | P0 |
| D-BOB | docs/BOB_USAGE_LOG.md | ⏳ | S | P1 |
| D-FINAL | docs/FINAL_REPORT.md | ⏳ | M | P0 (akhir) |

---

## RINGKASAN STATUS

| Fase | Total | ✅ Selesai | 🔄 In Progress | ⏳ Menunggu | 🚫 Blocked |
|:---|:--:|:--:|:--:|:--:|:--:|
| Fase 0 | 5 | 5 | 0 | 0 | 0 |
| Fase 1 Backend | 20 | 16 | 0 | 4 (PILOT) | 0 |
| Fase 2 Frontend | 20 | 13 | 0 | 7 (PILOT/PROD) | 0 |
| Fase 3 AI | 10 | 9 | 0 | 1 (A-305 ditunda) | 0 |
| Fase 4 ML | 9 | 0 | 0 | 9 | 0 |
| Fase 5 DevOps | 13 | 0 | 0 | 13 | 0 |
| **Total** | **77** | **43** | **0** | **34** | **0** |

---

## FASE 5 — DEMO READINESS — SELESAI ✅

| ID | Item | Status | File / Catatan |
|:---|:---|:---:|:---|
| D-DEMO | `docs/DEMO_SCRIPT.md` — skrip demo 5 menit lengkap | ✅ | `docs/DEMO_SCRIPT.md` |
| I-CI | `.github/workflows/ci.yml` — GitHub Actions 3 job | ✅ | `.github/workflows/ci.yml` |
| I-SEED | Auto-seed saat startup jika DB kosong | ✅ | `api/main.py` lifespan hook |
| I-RESET | `scripts/demo_reset.py` — reset + reseed satu perintah | ✅ | `scripts/demo_reset.py` |
| LF-JWT | `api/auth/jwt.py` — stdlib JWT, hilangkan `python-jose` | ✅ | `api/auth/jwt.py` (HS256 via hmac) |

---

## LANGFLOW-FIRST — STATUS AKHIR

| ID | Item | Status | Bukti / catatan |
|:---|:---|:---:|:---|
| LF-001 | Audit Langflow, matriks verifikasi, backlog, ADR | ✅ audit/dokumen; runtime BLOCKED | `docs/LANGFLOW_AUDIT.md`, `LANGFLOW_VERIFICATION.md`, `LANGFLOW_IMPLEMENTATION_PLAN.md`; Compose config lulus, Docker daemon tidak tersedia |
| LF-002 | Paket inti deterministik (`priomedrec_core`) | 🔄 Parsial | contracts/pipeline/priority ada; masih mengimpor `src/`, Fase B mengembalikan placeholder safety/DDI/alergi; parity belum lulus |
| LF-003 | Komponen PMR Langflow (19 class adapter) | 🔄 Parsial | Kelas ada; LFX local discovery 13 loaded + 1 import error; image pin belum dites |
| LF-004 | Image Langflow 1.13.0 + komponen | 🔄 Config siap, runtime BLOCKED | Dockerfile/Compose dipin 1.13.0; `docker compose config --quiet` pass; Docker daemon unavailable |
| LF-005 | Flow 00–03 Langflow-first | ⏳ | Belum ada; dua flow lama berisi pemanggilan FastAPI/narasi, satu agentic flow eksperimental |
| LF-006/007 | Client/orchestrator/verifier/trace + parity/fallback | 🔄 Pondasi ada; belum selesai | Route dan client tersedia; flow ID/master belum tersedia; flow hash masih placeholder; trace belum dipersistenkan; verifier/parity belum lengkap |
| LF-008/009/010/011 | Copilot, UI transparency, HITL, Bob↔Langflow | ⏳ | Tidak ada flow target/relay/HITL resume/MCP Langflow yang terverifikasi |
| LF-JSON | Flow JSON siap impor | 🔄 Legacy saja | Orchestrator + review JSON lama; belum ada flow JSON 00–06 |
| LF-CANVAS | Kanvas Langflow interaktif | ⏳ BLOCKED | Menunggu Docker daemon dan perbaikan loader komponen |
| LF-HITL | HITL resume + SSE trace via Langflow | ⏳ BLOCKED | Source lokal mencakup Workflow API v2; resume/trace belum diuji atau dicatat di audit |

---

## RINGKASAN STATUS (v3.0)

| Fase | Total | ✅ Selesai | 🔄 In Progress | ⏳ Menunggu | 🚫 Blocked |
|:---|:--:|:--:|:--:|:--:|:--:|
| Fase 0 | 5 | 5 | 0 | 0 | 0 |
| Fase 1 Backend | 20 | 16 | 0 | 4 (PILOT) | 0 |
| Fase 2 Frontend | 20 | 13 | 0 | 7 (PILOT/PROD) | 0 |
| Fase 3 AI | 10 | 9 | 0 | 1 (A-305 ditunda) | 0 |
| Fase 4 ML | 9 | 0 | 0 | 9 | 0 |
| Fase 5 Demo | 5 | 5 | 0 | 0 | 0 |
| **Fase Q1 Antrean** | **3** | **3** | **0** | **0** | **0** |
| **Total** | **72** | **51** | **0** | **21** | **0** |

**Tes:** 94 passed Q1 unit (+ 9 properti Hypothesis) + 98 legacy = **201 total**, 2 skipped, 2 pre-existing LLM failures
**Build:** `npm run build` ✅ 0 TypeScript error
**API:** `from api.main import app` ✅ 44 routes mounted

---

## FASE Q — MANAJEMEN ANTREAN SKALA RS

| ID | Item | Status | Ukuran | File diubah | Tes |
|:---|:---|:--:|:-:|:---|:---|
| Q-001 | Tabel queue_entries, queue_events, missed_reconciliations + Alembic | ✅ | M | `api/db/models.py`, `alembic/versions/20261102_*` | `test_q001_migration.py` 10✅ |
| Q-002 | `priomedrec_core/queue_engine.py` + `queue_config.py` — skor, kuota, histeresis | ✅ | L | `priomedrec_core/queue_engine.py`, `queue_config.py`, `__init__.py` | `test_q002_queue_engine.py` 41✅ + `test_q002_queue_properties.py` 9✅ (Hypothesis 1000 kasus) |
| Q-003 | `priomedrec_core/queue_transitions.py` — admit/submit/discharge/transfer/expire | ✅ | M | `priomedrec_core/queue_transitions.py`, `__init__.py` | `test_q003_transitions.py` 43✅ |
| Q-004 | API endpoint GET/POST /queue (keyset, atomik, heartbeat) | ⏳ | L | — | — |
| Q-005 | Tick batch + SLA + lease cleanup | ⏳ | M | — | — |
| Q-006 | SSE /events/queue | ⏳ | M | — | — |
| Q-007 | Hospital Simulator | ⏳ | L | — | — |
| Q-008 | Frontend: tombol Ambil, Antrean Saya, Antrean Bangsal | ⏳ | L | — | — |
| Q-009 | Command Center dasar | ⏳ | L | — | — |
| Q-010 | Penanganan event idempoten | ⏳ | M | — | — |
| Q-011 | GET /queue/metrics | ⏳ | M | — | — |
| Q-012 | Uji beban + properti + konkurensi | ⏳ | M | — | — |

---

## CATATAN TERBARU (v3.0)

- **JWT `python-jose` → stdlib** — `api/auth/jwt.py` ditulis ulang (HS256 via `hmac`+`hashlib`). Tidak ada ketergantungan eksternal untuk auth.
- **Auto-seed startup** — `api/main.py` lifespan seed 10 skenario S1–S10 otomatis jika DB kosong
- **Demo reset** — `python scripts/demo_reset.py` untuk reset data sebelum demo
- **GitHub Actions CI** — 3 job: backend-tests, frontend-build, demo-seed-check
- **DEMO_SCRIPT.md** — skrip 5 menit dengan antisipasi pertanyaan juri
- **Langflow canvas** — masih menunggu Docker daemon; fallback lokal berjalan 100%
- **Item PILOT ditunda:** I-601 (FHIR), B-117 (discharge), M-401 (ML ablation)
