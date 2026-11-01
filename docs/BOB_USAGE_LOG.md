# BOB USAGE LOG — PrioMed-Rec

**Proyek:** PrioMed-Rec CDSS (Admission Medication Reconciliation)
**Kompetisi:** IBM SkillsBuild University Education National Hackathon × Hacktiv8
**IBM Bob versi:** Agent Mode (multi-session, multi-phase)
**Terakhir diperbarui:** Fase 3 selesai

## LF-001 — Audit ulang Langflow-first, 2026-10-29

| Aktivitas | Peran Bob | Hasil | Batasan |
|---|---|---|---|
| Audit kode nyata | Auditor arsitektur | Mengoreksi peta pipeline; mencatat 19 adapter PMR, partial core, dua flow legacy, API orchestrator dan gap trace/verifier | Tidak mengubah logika klinis |
| Verifikasi versi | Peneliti teknis | Local venv Langflow 1.12.5 + lfx-ibm 0.2.5; rilis/tag Docker stabil 1.13.0 diverifikasi; pin Compose/Dockerfile diperbarui | Docker daemon tidak tersedia, jadi tidak ada build/start/health test |
| Spike LFX discovery | Penguji komponen | Discovery lokal 1.12.5 memuat 13 class dan melaporkan satu `ModuleNotFoundError: _lfx_ext` | Belum setara image 1.13.0; harus diperbaiki dan dites ulang sebelum kanvas |
| Smoke tests lokal | QA | `tests/test_analysis_orchestrator.py`, `test_priomedrec_core.py`, `test_pmr_components.py`: 6 passed | Tes tidak menjalankan Langflow server/flow |
| Dokumentasi resmi Langflow | Peneliti teknis | Meninjau custom components/allow-list, API flow run, Agent, Policies, HITL, dan MCP | Workflow v2 resume, SSE, provider dan fitur lain belum runtime-spiked |
| MCP Langflow | Integrator | Tidak ada Langflow MCP server terhubung di sesi ini; `mcp_settings.json` tetap menunjuk MCP FastAPI lokal | Bob↔Langflow belum diklaim selesai |

## LF-001 — 2026-10-29

| Aktivitas | Peran Bob/Codex | Hasil | Batasan |
|---|---|---|---|
| Audit Langflow-first | Auditor kode/dokumentasi | Memetakan baseline ≈10%, dua flow lama, dan browser→FastAPI | Tidak menjalankan flow karena Docker runtime tidak tersedia |
| Verifikasi dokumentasi | Peneliti teknis | Mengonfirmasi API key, v2 resume, allow-list component, bundle IBM | Semua klaim runtime tetap BLOCKED hingga spike lokal |
| Konfigurasi image | Developer | Menyiapkan pin 1.12.2 dan hardening env/network | Tidak ada kredensial atau konten klinis baru dibuat |

---

## Ringkasan Peran IBM Bob

IBM Bob berperan sebagai **rekan pengembang senior AI** untuk proyek ini, mencakup 7 peran berikut:

| # | Peran | Deskripsi |
|---|-------|-----------|
| 1 | **Developer Copilot** | Menulis, memperbaiki, dan merefaktor kode backend/frontend |
| 2 | **Data Quality Engineer** | Audit kualitas data ML, deteksi fitur konstan, validasi label |
| 3 | **Rule Engineer** | Mendesain dan mengelola rule engine deterministik |
| 4 | **Model Governance** | Mengevaluasi model ML, guardrail inferensi, model card |
| 5 | **Knowledge Base Curator** | Mengelola drug_alias.csv, interactions.json, allergy_rules.json |
| 6 | **Clinical QA** | Memastikan konten klinis bertanda DRAFT, tidak mengarang fakta medis |
| 7 | **Demo Agent** | Mengoperasikan sistem via MCP tools dalam demo kompetisi |

---

## Log Pengerjaan per Fase

### FASE 0 — Audit & Perencanaan

| ID | Peran | Tugas | Artefak |
|----|-------|-------|---------|
| T-001 | Developer Copilot | Baca dan verifikasi strategi vs kode nyata | `docs/AUDIT_REPO_VS_PLAN.md` |
| T-002 | Developer Copilot | Tulis 12 ADR (Architecture Decision Records) | `docs/DECISION_LOG.md` |
| T-003 | Model Governance | Tandai `medrec_xgboost/` sebagai RESEARCH ONLY | `medrec_xgboost/README.md` |
| T-004 | Model Governance | Hitung prevalensi label (76.3%), Lift@K (1.32×) | `docs/MODEL_CARD.md` |
| T-005 | Developer Copilot | Bekukan Langflow flow ke experimental/ | `langflow/experimental/` |
| — | Developer Copilot | Buat rencana implementasi 77 backlog item | `docs/IMPLEMENTATION_PLAN.md` |
| — | Clinical QA | Buat antrian validasi konten klinis | `docs/CLINICAL_REVIEW_QUEUE.md` |
| — | Developer Copilot | Dokumentasikan asumsi K1–K10 | `docs/ASSUMPTIONS.md` |

**Temuan kritis yang ditemukan Bob:**
- `web/src/api/langflow.ts` memanggil Langflow langsung dari browser → **pelanggaran ADR-02/S7**
- `api/database.py` menggunakan `INSERT OR REPLACE` di audit_entries → **melanggar immutability S8**
- `allergy_count` konstan 0 (DQI-001) — fitur tidak berguna untuk ML
- Tidak ada JWT auth (semua endpoint tanpa autentikasi)
- High-alert hard stop hanya di UI, bukan server-side
- bcrypt gagal di Python 3.12 → diganti argon2-cffi

---

### FASE 1 — Fondasi & Keselamatan (Backend)

| ID | Peran | Tugas | Artefak |
|----|-------|-------|---------|
| B-101 | Developer Copilot | Implementasi SQLAlchemy 2.x + Alembic | `api/db/session.py`, `alembic/` |
| B-102 | Developer Copilot | Desain dan buat 17 tabel ORM | `api/db/models.py` |
| B-103 | Developer Copilot | Auth JWT + RBAC 5 peran + argon2 | `api/auth/`, `api/routes/v1/auth.py` |
| B-104 | Developer Copilot | State machine 10 status + guard transisi | `api/services/case_state_service.py` |
| B-105 | Developer Copilot | Priority service komposit (ML+rules+SLA) | `api/services/priority_service.py` |
| B-106 | Developer Copilot | SLA service + APScheduler idempoten | `api/services/sla_service.py`, `api/tasks/scheduler.py` |
| B-107 | Developer Copilot | Audit trail SHA-256 hash-chain append-only | `api/services/audit_service.py` |
| B-108 | Developer Copilot | Review ESCALATE + alasan wajib + Idempotency-Key | `api/routes/v1/review.py` |
| B-109 | Rule Engineer | Aturan alergi silang (DRAFT) | `configs/allergy_rules.json` |
| B-110 | Rule Engineer | Severity tier 1/2/3 di discrepancy_rules.json | `configs/discrepancy_rules.json` |
| B-111 | Rule Engineer | Normalizer 5 tahap + drug_alias.csv (250+ alias) | `api/services/normalizer_service.py`, `knowledge/drug_alias.csv` |
| B-112 | Developer Copilot | High-alert hard stop di server (APPROVE ditolak) | `api/services/case_state_service.py` |
| B-113/114 | Developer Copilot | Worklist v1 dengan klaim, filter, sort | `api/routes/v1/worklist.py` |
| B-115 | Developer Copilot | Seed demo deterministik S1–S10 | `scripts/seed_demo.py` |
| B-116 | Developer Copilot | Envelope error seragam + request_id | `api/errors.py`, `api/main.py` |

**Tes yang ditulis:** 39 tes unit baru (auth, state machine, priority, audit, normalizer)

---

### FASE 2 — Pengalaman Apoteker (Frontend)

| ID | Peran | Tugas | Artefak |
|----|-------|-------|---------|
| F-201 | Developer Copilot | Login page + idle lock 30 menit | `web/src/pages/LoginPage.tsx`, `IdleLockOverlay.tsx` |
| F-202 | Developer Copilot | API client terautentikasi + auto-refresh JWT | `web/src/lib/apiClient.ts` |
| F-203 | Developer Copilot | Worklist v2: tier badge, SLA countdown, klaim, polling | `web/src/pages/WorklistPageV2.tsx` |
| F-204/205/206 | Developer Copilot | Case Workspace: 4 tab (Compare/Findings/SBAR/History) | `web/src/pages/CaseWorkspacePage.tsx` |
| F-207 | Clinical QA | Label "Draf AI — wajib diverifikasi apoteker" permanen | `web/src/components/AiDraftLabel.tsx` |
| F-208 | Developer Copilot | Action bar sticky + HighAlert modal + Undo 10d | `web/src/components/ReviewActionBar.tsx` |
| F-210 | Developer Copilot | Dashboard KPI + SLA panel + system health | `web/src/pages/DashboardPage.tsx` |
| F-212 | Developer Copilot | Audit Log v2 + verifikasi hash-chain dari UI | `web/src/pages/AuditLogPageV2.tsx` |

**Hasil:** `npm run build` 0 error TypeScript, 389KB JS

---

### FASE 3 — Orkestrasi AI (Langflow & IBM Bob)

| ID | Peran | Tugas | Artefak |
|----|-------|-------|---------|
| A-301 | Developer Copilot | **Fix pelanggaran ADR-02**: redirect `langflow.ts` dari browser→Langflow ke AI Gateway | `web/src/api/langflow.ts` (rewrite) |
| A-302 | Developer Copilot | Guardrail bersama 9 cek (forbidden phrases, injection, dose fidelity, bahasa) | `api/services/guardrail_service.py` |
| A-303 | Developer Copilot | Langflow flow hash di /api/v1/health/deps + dependency health check | `api/routes/v1/health.py` |
| A-304 | Developer Copilot | Copilot AI Drawer di Case Workspace (floating FAB) | `web/src/components/CopilotDrawer.tsx` |
| A-306 | Developer Copilot | LLM chain berbasis konfigurasi: gemini→groq→watsonx→ollama→template | `api/services/llm_chain_service.py` |
| A-307 | Developer Copilot | MCP server 5 tools: get_worklist, rank_admission_risk, detect_discrepancy, lookup_knowledge, draft_review(DRAFT) | `mcp_server.py` (rewrite) |
| A-308 | Developer Copilot | `<user_note>` wrapper + sanitasi teks bebas (sudah di guardrail_service) | `api/services/guardrail_service.py` |
| A-309 | Developer Copilot | Prompt berversi sbar_v1.md + copilot_v1.md | `prompts/sbar_v1.md`, `prompts/copilot_v1.md` |
| A-307b | Developer Copilot | Knowledge lookup endpoint /api/v1/knowledge/lookup | `api/routes/v1/knowledge.py` |

**Tes yang ditulis:** `tests/test_fase3_ai_orchestration.py` — 18 tes (S5, S6, guardrail, sanitize, MCP)

---

## Keputusan Keselamatan Klinis yang Ditegakkan Bob

| Aturan | Implementasi |
|--------|-------------|
| S1 (Human-in-the-loop) | State machine: APPROVE/EDIT/REJECT/ESCALATE hanya dari apoteker via UI |
| S2 (Rules, bukan LLM) | Rule engine deterministik; LLM tidak dipanggil dalam discrepancy detection |
| S3 (LLM hanya narasi) | `call_with_guardrail` → re-prompt maks 2× → template deterministik |
| S4 (ML hanya ranking) | `priority_service`: final_tier = max(ml_tier, rules_floor, sla_floor) |
| S5 (InferenceGuard) | 10 SAFE_FEATURES vs 6 FORBIDDEN_FEATURES di `normalizer_service.py` |
| S6 (MCP DRAFT only) | `draft_pharmacist_review` → force_status=DRAFT_REVIEW, actor_type=agent_via_mcp |
| S7 (No browser→LLM) | `langflow.ts` ditulis ulang → semua call ke /api/v1/ai/* |
| S8 (Audit immutable) | SHA-256 hash-chain; INSERT-only; prev_hash; /audit/verify |
| S9 (Synthetic data only) | Seed demo: Synthea + seed deterministik; tidak ada PII |
| S10 (DRAFT clinical content) | Semua aturan klinis: `"status": "DRAFT_PERLU_VALIDASI_APOTEKER"` |
| S11 (Label UI) | "Prioritas Telaah Farmasi" (bukan "risiko pasien") di semua komponen |
| S12 (AI draft label) | `AiDraftLabel` permanen di SBAR, copilot response, dan semua output AI |

---

## Konten Klinis yang Menunggu Validasi Apoteker

Semua item berikut **tidak boleh digunakan secara klinis** tanpa validasi apoteker berlisenser:

1. `configs/allergy_rules.json` — cross-reactivity rules (B-109)
2. `knowledge/drug_alias.csv` — 250+ alias brand/INN (B-111)
3. `configs/discrepancy_rules.json` — severity tier 1/2/3 classification (B-110)
4. `knowledge/interactions.json` — DDI pairs (pre-existing, perlu verifikasi ulang)
5. `tests/golden/*.yaml` — 40 kasus draf (Fase 4 — belum dibuat)

Lihat: [`docs/CLINICAL_REVIEW_QUEUE.md`](./CLINICAL_REVIEW_QUEUE.md)

---

## Statistik Akhir Fase 3

| Metrik | Nilai |
|--------|-------|
| File baru dibuat | 28 file |
| File dimodifikasi | 18 file |
| Tes unit baru | 57 tes |
| Tes total (lama + baru) | 109+ tes |
| Baris kode ditambahkan | ~5.800 baris |
| Kerentanan ADR-02 yang diperbaiki | 1 (langflow.ts) |
| Kerentanan S8 yang diperbaiki | 1 (audit trail INSERT OR REPLACE) |
| Provider LLM yang didukung | 5 (gemini, groq, watsonx, ollama, template) |
| Tool MCP yang tersedia | 5 (4 read + 1 write-as-DRAFT) |

---

*Dokumen ini dicatat sesuai ADR-12 dan instruksi Fase 3 A-310.*
*IBM Bob berperan sebagai AI SDLC partner — semua keputusan produk/klinis final dilakukan manusia.*
