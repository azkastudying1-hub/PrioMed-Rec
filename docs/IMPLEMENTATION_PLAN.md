# RENCANA IMPLEMENTASI — PrioMed-Rec
## Fase 1–5: Dari Fondasi ke DEMO-READY → Persiapan Pilot

**Versi:** 1.0 (berdasarkan Fase 0 Audit)
**Sumber:** `PRIOMEDREC_STRATEGIC_DEVELOPMENT_PLAN.md` v5.0 + `docs/AUDIT_REPO_VS_PLAN.md`
**Target tahap:** DEMO-READY (Fase 0–3) + stub PILOT (Fase 4–5)
**Konvensi ukuran:** S ≤ 1 hari · M 2–4 hari · L 1–2 minggu · XL > 2 minggu
**Track:** `[DEMO]` · `[PILOT]` · `[PROD]`

---

## JALUR KRITIS (urutan wajib)
```
T-001..004 → B-101/102 → B-103 → B-104 → B-105/106/107
→ F-201/202 → F-203/204/205
→ B-109/110/111 → F-206/207/208/209
→ A-301/302/303 → B-115 + F-220
→ [DEMO-READY ✓]
→ M-401/402 → V-501
→ B-117/118/120 → I-601
→ [PILOT-READY]
```

**Paralel aman:**
- ML (M-4xx) berjalan independen dari frontend
- Langflow (A-30x) dimulai setelah kontrak `/analysis/{id}/latest` stabil
- Dokumen regulasi (V-504) dimulai sejak Fase 1

---

## FASE 1 — FONDASI & KESELAMATAN (Backend)
**Durasi target:** 2–3 minggu | **Kriteria selesai:** pytest hijau (lama+baru); S3, S7, S8, S9, S10 lulus sebagai tes otomatis; hash-chain terverifikasi; tidak ada endpoint mutasi tanpa auth.

### B-101 — SQLAlchemy + Alembic: migrasi tabel yang ada
| Atribut | Nilai |
|:---|:---|
| Ukuran | M |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | — (langkah pertama) |
| Risiko | Migrasi data SQLite yang sudah ada (bpmh_records, audit_entries, ward_configs, patient_status, local_high_alert) |
| Kriteria selesai | SQLAlchemy session factory berjalan; tabel lama dimigrasikan via Alembic; pytest lama masih hijau |
| File dibuat/diubah | `api/db/__init__.py`, `api/db/session.py`, `api/db/models.py` (tabel lama), `alembic/`, `alembic.ini`, `requirements.txt` (tambah sqlalchemy, alembic) |

### B-102 — Tabel baru (skema lengkap Lampiran B dokumen strategi)
| Atribut | Nilai |
|:---|:---|
| Ukuran | M |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | B-101 |
| Risiko | Skema berubah merusak endpoint lama — gunakan Alembic migration |
| Kriteria selesai | Tabel: users, encounters, bpmh_items, analysis_runs, discrepancies, sbar_drafts, sbar_revisions, status_history, sla_events, notifications, drug_alias, sla_config, audit_entries (versi baru dengan hash) tersedia |
| File dibuat/diubah | `api/db/models.py`, migrasi Alembic baru |

### B-103 — Auth JWT + RBAC + manajemen pengguna
| Atribut | Nilai |
|:---|:---|
| Ukuran | L |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | B-101 |
| Risiko | Memblokir endpoint lama yang tidak ada auth → gunakan dependensi opsional untuk kompatibilitas sementara |
| Kriteria selesai | `POST /auth/login` menghasilkan JWT; RBAC `PHARMACIST/TECHNICIAN/COORDINATOR/ADMIN/AUDITOR` berjalan; endpoint `/api/v1/*` membutuhkan token; endpoint lama (`/analyze`, `/prioritize`) mempertahankan X-API-Key untuk Langflow/MCP |
| File dibuat/diubah | `api/auth/jwt.py`, `api/auth/rbac.py`, `api/auth/password.py`, `api/routes/v1/auth.py`, `api/deps.py`, `requirements.txt` (tambah python-jose, passlib) |

### B-104 — State machine diperluas + transisi sah + status_history
| Atribut | Nilai |
|:---|:---|
| Ukuran | M |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | B-102 |
| Risiko | Merusak logika status lama (BPMH_TERISI, DISETUJUI, dll) |
| Kriteria selesai | 10 status terdefinisi (MENUNGGU_BPMH, BPMH_PROSES, BPMH_SELESAI, PERLU_VERIFIKASI, DALAM_TELAAH, MENUNGGU_DPJP, ESKALASI, SELESAI, PULANG_TERTAHAN, PULANG_SIAP); guard transisi sah di service; setiap perubahan menulis ke status_history |
| File dibuat/diubah | `api/services/case_state_service.py`, `api/db/models.py` (status_history) |

### B-105 — Priority service komposit + priority_reason
| Atribut | Nilai |
|:---|:---|
| Ukuran | M |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | B-102, B-104 |
| Kriteria selesai | `compute_priority(enc, ml, findings, sla_cfg, now)` mengembalikan tier_final = max(ML, aturan, SLA) + `priority_reason[]`; S3 (SLA menaikkan tier) dan S10 (InferenceGuard) lulus |
| File dibuat/diubah | `api/services/priority_service.py` |

### B-106 — SLA service + APScheduler + sla_events + notifikasi SSE
| Atribut | Nilai |
|:---|:---|
| Ukuran | L |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | B-102, B-105 |
| Risiko | APScheduler di lingkungan multi-worker; gunakan `replace_existing=True` + idempoten |
| Kriteria selesai | Scheduler tiap 60 dtk menghitung ulang tier; SLA_WARNING/BREACH ditulis ke sla_events; notifikasi SSE di `GET /events`; S3 (Tn. Budi 13 jam → MEDIUM) lulus otomatis |
| File dibuat/diubah | `api/tasks/scheduler.py`, `api/services/sla_service.py`, `api/routes/v1/notifications.py`, `requirements.txt` (apscheduler) |

### B-107 — Audit service hash-chain + trigger + /audit/verify
| Atribut | Nilai |
|:---|:---|
| Ukuran | M |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | B-102, B-103 |
| Risiko | SQLite tidak mendukung stored trigger se-robust PostgreSQL; gunakan app-level guard dulu, migrasi trigger ke PostgreSQL di B-120 |
| Kriteria selesai | `audit_entries` memiliki kolom `seq`, `prev_hash`, `hash`; `audit_service.append()` menghitung SHA256; app-level guard menolak update; `GET /api/v1/audit/verify` mengembalikan valid/invalid; `actor_id` dan `actor_type` dari token (bukan body) |
| File dibuat/diubah | `api/services/audit_service.py`, `api/routes/v1/audit.py`, migrasi Alembic |

### B-108 — Aksi ESCALATE, alasan wajib (EDIT/REJECT/ESCALATE), DRAFT_REVIEW
| Atribut | Nilai |
|:---|:---|
| Ukuran | M |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | B-103, B-104, B-107 |
| Kriteria selesai | `POST /api/v1/review` menerima action ∈ {APPROVE, EDIT, REJECT, ESCALATE}; EDIT/REJECT/ESCALATE membutuhkan `reason` tidak kosong (422 jika kosong); `DRAFT_REVIEW` tersedia untuk MCP (ADR-07); Idempotency-Key header dihormati |
| File dibuat/diubah | `api/routes/v1/review.py`, `api/schemas/review.py`, pertahankan `/review` lama sebagai alias |

### B-109 — allergy_rules.json + cek alergi + input alergi BPMH
| Atribut | Nilai |
|:---|:---|
| Ukuran | M |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | B-102 |
| Risiko | Konten klinis → WAJIB ditandai DRAFT_PERLU_VALIDASI_APOTEKER |
| Kriteria selesai | `configs/allergy_rules.json` ada (isi DRAFT); cek alergi silang kelas (penisilin–sefalosporin, sulfa, NSAID) berjalan di rule engine; input alergi pada BPMH form; `status: "DRAFT_PERLU_VALIDASI_APOTEKER"`, `owner: "TBD-apoteker"` |
| File dibuat/diubah | `configs/allergy_rules.json` (BARU), `src/rules/discrepancy_engine.py`, `api/routes/v1/bpmh.py`, `docs/CLINICAL_REVIEW_QUEUE.md` |

### B-110 — Severity tier di discrepancy_rules.json + keluaran tier
| Atribut | Nilai |
|:---|:---|
| Ukuran | M |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | — |
| Risiko | Konten klinis DRAFT |
| Kriteria selesai | `discrepancy_rules.json` memiliki `severity_tier: 1/2/3` per tipe aturan; rule engine menghasilkan `severity_tier` di setiap temuan; Tier-1 menaikkan prioritas ke HIGH (terintegrasi B-105) |
| File dibuat/diubah | `configs/discrepancy_rules.json`, `src/rules/discrepancy_engine.py`, `api/schemas/` |

### B-111 — Normalizer 5 tahap + drug_alias.csv (≥200 obat Indonesia)
| Atribut | Nilai |
|:---|:---|
| Ukuran | L |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | B-102 |
| Risiko | Konten alias klinis DRAFT; akurasi fuzzy threshold perlu tuning |
| Kriteria selesai | `NormalizerService`: exact → alias → rapidfuzz(ambang tinggi) → KFA/RxNorm stub → antrean tak dikenali; `knowledge/drug_alias.csv` ≥ 200 entri (merek dagang Indonesia → generik); confidence rendah ditandai "perlu verifikasi"; S9 (Plavix→clopidogrel) lulus |
| File dibuat/diubah | `api/services/normalizer_service.py`, `knowledge/drug_alias.csv` (BARU, DRAFT), `requirements.txt` (rapidfuzz) |

### B-112 — High-Alert hard stop (validasi server)
| Atribut | Nilai |
|:---|:---|
| Ukuran | S |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | B-108 |
| Kriteria selesai | `POST /api/v1/review` dengan action=APPROVE ditolak 422 jika `high_alert_unconfirmed_count > 0`; S1 (hard stop warfarin+Clexane) lulus |
| File dibuat/diubah | `api/routes/v1/review.py`, `api/services/audit_service.py` |

### B-114 — GET /api/v1/worklist dengan filter, indeks, sort komposit
| Atribut | Nilai |
|:---|:---|
| Ukuran | M |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | B-102, B-105 |
| Kriteria selesai | Endpoint ada; filter: ward, tier, status, assignee, q; sort: tier_final ↓ + sisa_SLA ↑ + skor ML ↓; paginasi kursor; P95 < 500ms (100 encounter); kolom `latest_tier` denormalisasi |
| File dibuat/diubah | `api/routes/v1/worklist.py` (BARU) |

### B-115 — Seed demo deterministik skenario S1–S10
| Atribut | Nilai |
|:---|:---|
| Ukuran | M |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | B-102, B-109, B-110 |
| Kriteria selesai | Script `scripts/seed_demo.py`; `make demo-reset` atau `python scripts/seed_demo.py`; memuat 10+ encounter sesuai skenario S1–S10; idempoten |
| File dibuat/diubah | `scripts/seed_demo.py` (BARU), `Makefile` atau `scripts/demo_reset.sh` |

### B-116 — Envelope galat seragam + /api/v1 versioning + request_id
| Atribut | Nilai |
|:---|:---|
| Ukuran | S |
| Track | [DEMO] |
| Prio | P0 |
| Dependensi | — |
| Kriteria selesai | Semua error mengembalikan `{error:{code,message,details,request_id}}`; `/api/v1/*` prefix aktif; endpoint lama tetap berjalan (alias) |
| File dibuat/diubah | `api/errors.py` (BARU), `api/main.py`, `api/routes/v1/__init__.py` |

### B-113 — Penguncian kasus (claim/release) + If-Match [PILOT]
| Track | [PILOT] | Prio | P1 |
|:---|:---|:---|:---|
| File | `api/routes/v1/encounters.py` | Ukuran | M |

### B-117 — Discharge check API [PILOT]
| Track | [PILOT] | Prio | P1 |

### B-118 — Re-triage event (transfer/order baru) [PILOT]
| Track | [PILOT] | Prio | P1 |

### B-120 — PostgreSQL + uji lintas-DB [PILOT]
| Track | [PILOT] | Prio | P1 |

---

## FASE 2 — PENGALAMAN APOTEKER (Frontend)
**Durasi target:** 2–3 minggu | **Kriteria selesai:** Alur worklist → keputusan ≤ 3 klik; e2e S1, S2, S7 hijau; build produksi tanpa error; tidak ada dead-end.

### F-201 — Login + guard rute + sesi + kunci idle
| Ukuran | M | Track | [DEMO] | Dependensi | B-103 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | Halaman `/login`, JWT disimpan (httpOnly cookie atau memory), guard semua rute, kunci idle 15 mnt |
| File | `web/src/pages/Login.tsx`, `web/src/hooks/useAuth.ts`, `web/src/router.tsx`, `web/package.json` (+react-router) |

### F-202 — TanStack Query + Zod (selaraskan tipe dengan backend)
| Ukuran | M | Track | [DEMO] | Dependensi | F-201 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | TanStack Query untuk semua fetch; Zod schema untuk semua response; `web/src/types/clinical.ts` sinkron dengan `api/schemas/` |
| File | `web/package.json` (+@tanstack/react-query, zod), `web/src/api/client.ts` (refaktor), `web/src/types/clinical.ts` |

### F-203 — Worklist v2 (tier badge, SLA countdown, alasan, klaim, filter, SSE)
| Ukuran | L | Track | [DEMO] | Dependensi | F-202, B-114, B-106 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | Badge tier (warna+ikon+teks), SLA countdown hidup, chip alasan prioritas, klaim kasus, filter bangsal/tier/status, penyegaran SSE/polling, loading/empty/error state |
| File | `web/src/pages/Worklist.tsx`, `web/src/components/PriorityBadge.tsx`, `web/src/components/SlaCountdown.tsx` |

### F-204 — Case Workspace (header sticky, dua kolom, tab)
| Ukuran | L | Track | [DEMO] | Dependensi | F-203, B-104 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | Satu layar terpadu; header sticky (nama, tier, SLA, alergi); dua kolom ≥1280px; tab Bandingkan/Temuan/SBAR/Keputusan |
| File | `web/src/pages/CaseWorkspace.tsx`, `web/src/components/CaseHeader.tsx` |

### F-205 — CompareTable + CoupletRow (side-by-side order couplets)
| Ukuran | L | Track | [DEMO] | Dependensi | F-204 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | Tabel dua kolom Obat Rumah vs Order Admisi; couplets LANJUT/TUNDA/GANTI/STOP/BARU/TIDAK ADA; warna per severity tier; panel detail per baris |
| File | `web/src/components/CompareTable.tsx`, `web/src/components/CoupletRow.tsx` |

### F-206 — Tab Temuan bertingkat + umpan balik relevan
| Ukuran | M | Track | [DEMO] | Dependensi | F-204 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | Tier 1 kritis merah (di atas), Tier 2 kuning, Tier 3 abu-abu dilipat; tombol Relevan/Tidak relevan per kartu |
| File | `web/src/components/FindingsPanel.tsx`, `web/src/components/DiscrepancyCard.tsx` |

### F-207 — SbarEditor (edit, revisi, salin CPPT, status guardrail)
| Ukuran | M | Track | [DEMO] | Dependensi | F-204, A-301 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | 4 bagian S/B/A/R editable; badge "Draf AI" permanen; indikator guardrail (lolos/fallback); salin CPPT 1-klik; tandai terkirim ke DPJP |
| File | `web/src/components/SbarEditor.tsx` |

### F-208 — ReviewActionBar + HighAlertConfirmModal + Undo 10 detik
| Ukuran | M | Track | [DEMO] | Dependensi | F-204, B-108, B-112 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | Bilah aksi sticky bawah (APPROVE/EDIT/REJECT/ESCALATE); modal konfirmasi high-alert wajib; Undo 10 detik sebelum dikunci |
| File | `web/src/components/ReviewActionBar.tsx`, `web/src/components/HighAlertConfirmModal.tsx` |

### F-209 — BPMH v2 (autosave, autocomplete, alergi, sumber & keandalan)
| Ukuran | L | Track | [DEMO] | Dependensi | F-201, B-109 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | Autosave setiap 5 detik; autocomplete obat (generik+merek+KFA); input alergi wajib atau "tidak ada alergi diketahui"; sumber + keandalan; disposisi + alasan; penanda normalisasi; pernyataan "tidak minum obat rutin" |
| File | `web/src/components/BpmhForm.tsx`, `web/package.json` (+react-hook-form) |

### F-210 — Dashboard (KPI, SLA, coverage, kesehatan sistem) [DEMO/PILOT]
| Ukuran | M | Track | [DEMO] sebagian | Prio | P1 |
|:---|:---|:---|:---|:---|:---|
| File | `web/src/pages/Dashboard.tsx` |

### F-211 — State error/empty/offline universal + Coba lagi
| Ukuran | M | Track | [DEMO] | Dependensi | F-202 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | Semua halaman punya skeleton, empty state dengan ajakan, error state + Coba lagi; offline banner |
| File | `web/src/components/ui/EmptyState.tsx`, `web/src/components/ui/ErrorState.tsx` |

### F-220 — Playwright e2e S1, S2, S3, S7 (minimal)
| Ukuran | L | Track | [DEMO] | Dependensi | F-201..F-209, B-115 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | 4 alur e2e hijau: S1 (HIGH + hard stop), S2 (disposisi sah), S3 (SLA naik), S7 (dua apoteker) |
| File | `tests/e2e/`, `web/package.json` (+@playwright/test) |

### F-212..F-219 — Fitur tambahan [PILOT/PROD]
| ID | Item | Track |
|:---|:---|:---|
| F-212 | Audit Log v2 + verifikasi rantai + ekspor | [PILOT] |
| F-213 | Admin (pengguna, SLA, high-alert, alias) | [PILOT] |
| F-214 | Copilot drawer | [DEMO] P1 |
| F-215 | Knowledge lookup | [PILOT] |
| F-216 | Discharge page | [PILOT] |
| F-217 | Aksesibilitas a11y | [PILOT] |
| F-218 | Ekspor PDF | [PILOT] |
| F-219 | Pintasan keyboard | [PROD] |

---

## FASE 3 — ORKESTRASI AI (Langflow & IBM Bob)
**Durasi target:** 2 minggu | **Kriteria selesai:** S5 (LLM mati → template) dan S6 (obat fiktif ditolak) lulus; demo end-to-end via UI dan MCP; tidak ada kunci API di browser.

### A-301 — AI Gateway (ADR-02) + hapus panggilan langsung browser→Langflow
| Ukuran | M | Track | [DEMO] | Prio | P0 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | `POST /api/v1/ai/sbar` dan `/ai/copilot` di FastAPI; `web/src/api/langflow.ts` TIDAK lagi dipanggil langsung; `source` field di response (langflow/llm/template) |
| File | `api/routes/v1/ai.py` (BARU), `api/services/ai_gateway.py` (BARU), `web/src/api/langflow.ts` (refaktor ke proxy) |

### A-302 — Refaktor guardrail jadi paket bersama + cek #7–#9
| Ukuran | M | Track | [DEMO] | Prio | P0 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | 9 cek aktif: 6 lama + (7) fidelitas angka dosis, (8) deteksi bahasa instruksi, (9) deteksi prompt-injection; `guardrail_fail_total{check}` metrik; paket bisa diimpor Langflow dan FastAPI |
| File | `src/llm/validators/output_validator.py`, `src/llm/validators/guardrail_metrics.py` |

### A-303 — Flow A final (Orchestrator+SBAR) + uji kontrak + hash di /health/deps
| Ukuran | M | Track | [DEMO] | Prio | P0 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | Flow A menghasilkan SBAR yang lulus guardrail; hash JSON flow tampil di `/health/deps`; uji fallback ketika Langflow mati |
| File | `langflow/priomedrec_orchestrator.json` (update), `tests/test_langflow_integration.py` |

### A-304 — Flow B (Copilot) + Knowledge tool [P1]
### A-305 — Flow C (draft review) [P1]

### A-306 — LLM chain config-driven + health check + Ollama opsional
| Ukuran | M | Track | [DEMO] | Prio | P0 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | Rantai LLM baca dari `LLM_CHAIN` env; health check tiap 60 dtk; watsonx.ai opsional (aktif jika env ada); Ollama opsional |
| File | `src/llm/service.py`, `.env.example` |

### A-307 — MCP final (5 tool; tulis=DRAFT) + pengujian dengan Bob
| Ukuran | M | Track | [DEMO] | Prio | P0 |
|:---|:---|:---|:---|:---|:---|
| Kriteria | `mcp_server.py` memiliki 5 tool: `get_worklist`, `rank_admission_risk`, `detect_medication_discrepancy`, `lookup_drug_knowledge`, `draft_pharmacist_review` (bukan final); `actor_type=agent_via_mcp` dicatat audit |
| File | `mcp_server.py`, `mcp_settings.json` |

### A-308 — Defense prompt-injection + pembungkus `<user_note>`
| Ukuran | S | Track | [DEMO] | Prio | P0 |
|:---|:---|:---|:---|:---|:---|
| File | `src/llm/validators/output_validator.py`, `api/services/ai_gateway.py` |

### A-309 — Prompt berversi (prompts/sbar_v1.md) + golden test SBAR
| Ukuran | M | Track | [DEMO] | Prio | P0 |
|:---|:---|:---|:---|:---|:---|
| File | `prompts/sbar_v1.md` (BARU), `prompts/copilot_v1.md` (BARU), `tests/test_sbar_golden.py` |

### A-310 — Dokumentasi penggunaan Bob (8 peran → artefak) [P1]
| File | `docs/BOB_USAGE_LOG.md` (BARU) |

---

## FASE 4 — ML & VALIDASI (demo-grade)
**Durasi target:** paralel dengan Fase 1–3 | **Kriteria selesai:** MODEL_CARD jujur; lift@K terlaporkan; golden set berjalan di CI.

### M-401 — Latih model_A (fitur registrasi) vs model_B + ablation + GroupKFold
| Ukuran | L | Prio | P0 |
|:---|:---|:---|:---|
| Kriteria | model_A: fitur tersedia saat registrasi (age, age_65_plus, gender_encoded, active_condition_count, prior_encounter_count); model_B: semua 10 SAFE_FEATURES; bandingkan Lift@10/20/30%; GroupKFold per patient_id |
| File | `scripts/train_model_ab.py` (BARU), `models/registry/` |

### M-402 — Protokol evaluasi (lift, NDCG, ECE, subgrup, baseline aturan)
| Ukuran | M | Prio | P0 |
|:---|:---|:---|:---|
| Kriteria | Laporkan: Lift@10/20/30%, NDCG@K, recall Tier-1 pada Top-K, ECE/reliability diagram, subgrup (usia, gender), CI bootstrap, vs FIFO, vs aturan sederhana |
| File | `docs/MODEL_CARD.md` (update), `docs/ML_AUDIT_REPORT.md` (update) |

### M-403 — Ambang berbasis kapasitas [P1]
### M-404 — promote_model.py + registry [P1]

### V-501 — Golden set 40 kasus (kerangka + draf) di CI
| Ukuran | L | Prio | P0 |
|:---|:---|:---|:---|
| Kriteria | 40 kasus YAML di `tests/golden/`; status="menunggu_validasi_apoteker"; berjalan di CI; output ditandai DRAFT |
| File | `tests/golden/*.yaml` (40 file), `tests/test_golden.py` |

---

## FASE 5 — POLES DEMO & PERSIAPAN PILOT
**Durasi target:** paralel akhir | **Kriteria selesai:** `docker compose up` dari nol berjalan; G1–G9 hijau; seed demo termuat.

### I-CI — GitHub Actions CI
| Ukuran | M | Prio | P0 |
|:---|:---|:---|:---|
| Kriteria | Workflow: lint (ruff, mypy, eslint, tsc) → pytest → golden → web build+vitest → Playwright inti → pip-audit/npm audit → pemindaian rahasia |
| File | `.github/workflows/ci.yml` (BARU) |

### I-Docker — docker-compose verifikasi + .env.example lengkap
| Ukuran | S | Prio | P0 |
|:---|:---|:---|:---|
| Kriteria | `docker compose up` memulai api+web+langflow; seed demo termuat otomatis; `.env.example` memiliki semua variabel yang dibutuhkan |
| File | `docker-compose.yml`, `.env.example`, `scripts/seed_demo.py` |

### Dokumen pilot (stub)
| ID | Dokumen | Keterangan |
|:---|:---|:---|
| D-FHIR | `docs/FHIR_MAPPING.md` | Pemetaan resource FHIR ↔ skema |
| D-RUNBOOK | `docs/RUNBOOK_PILOT.md` | Prosedur operasional pilot RS |
| D-SECURITY | `docs/SECURITY.md` | Model ancaman, kontrol, kontak insiden |
| D-DEMO | `docs/DEMO_SCRIPT.md` | Skrip demo 5 menit (Bagian 16.2) |
| D-QA | `docs/DEMO_QA.md` | Antisipasi pertanyaan juri (Bagian 16.3) |
| D-BOB | `docs/BOB_USAGE_LOG.md` | Log 8 peran Bob + artefak |

---

## RINGKASAN BACKLOG PER FASE

| Fase | Item DEMO (P0) | Item PILOT (P1) | Item PROD (P2) | Total |
|:---|:--:|:--:|:--:|:--:|
| Fase 1 Backend | 12 | 4 | 0 | 16 |
| Fase 2 Frontend | 10 | 8 | 1 | 19 |
| Fase 3 AI/Langflow | 7 | 3 | 0 | 10 |
| Fase 4 ML/Validasi | 3 | 4 | 1 | 8 |
| Fase 5 DevOps/Demo | 5 | 5 | 0 | 10 |
| **Total** | **37** | **24** | **2** | **63** |

**Target DEMO-READY:** 37 item P0 selesai → estimasi 7–9 minggu tim penuh.
