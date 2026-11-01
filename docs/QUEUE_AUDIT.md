# QUEUE_AUDIT.md — Kondisi Nyata Manajemen Antrean PrioMed-Rec
## Fase Q0 · Audit Sebelum Implementasi

**Versi:** 1.0  
**Tanggal:** Fase Q0  
**Dibuat oleh:** IBM Bob  
**Referensi:** PRIOMEDREC_QUEUE_MANAGEMENT_PLAN.md (sumber utama); PRIOMEDREC_STRATEGIC_DEVELOPMENT_PLAN.md §5.2, §5.3; docs/PROGRESS.md v3.0  

> Dokumen ini mendeskripsikan **kondisi repo saat ini** (*as-is*), bukan kondisi target. Setiap gap adalah backlog item Q-001..Q-012.

---

## 1. BAGAIMANA WORKLIST DIBANGUN SEKARANG

### 1.1 Query & Pengurutan

**File:** [`api/routes/v1/worklist.py`](../api/routes/v1/worklist.py) — `GET /api/v1/worklist`

```python
# Saat ini — pengurutan dua tahap (bermasalah untuk skala besar):
encounters = query.order_by(Encounter.admitted_at.asc())  # SQL ORDER
             .offset(offset).limit(page_size).all()
# Lalu sort ulang di Python (page_size ≤ 100):
encounters.sort(key=lambda e: (-TIER_ORDER[tier], admitted_at))
```

**Masalah yang teridentifikasi:**
| # | Masalah | Dampak |
|---|---------|--------|
| W-01 | Sort tier dilakukan **di Python** setelah `OFFSET/LIMIT` SQL | Halaman 2+ dapat tidak terurut dengan benar antar-tier |
| W-02 | Menggunakan `OFFSET` bukan *keyset pagination* | Performa O(N) saat halaman besar; baris dapat terlewat/ganda saat data berubah |
| W-03 | Tidak ada kolom `priority_score` di tabel `encounters` | Pengurutan dalam-tier tidak bisa dilakukan — hanya tier + admitted_at |
| W-04 | Tidak ada `queue_entries` terpisah | Setiap `/worklist` query harus menyentuh tabel `encounters` lengkap |
| W-05 | `claimed_by IS NOT NULL` tidak menyertakan TTL/lease | Klaim bisa menggantung selamanya jika apoteker tutup tab |
| W-06 | Tidak ada kolom `tier_source` | UI tidak bisa menampilkan badge "HIGH (aturan)" vs "HIGH (ML)" |
| W-07 | Tidak ada `discharge_pressure` di schema | Pasien mau pulang tidak dapat diprioritaskan |

### 1.2 Pagination

- **Metode saat ini:** `OFFSET/LIMIT` dengan `page` + `page_size` (maks 100)
- **Batas yang ada:** page_size capped 100 — cukup untuk demo S/M, tetapi bukan *keyset*
- **Yang dibutuhkan (target):** Keyset cursor `(tier_rank DESC, priority_score DESC, encounter_id)` — stabil walau ada insert/update concurrent

### 1.3 Polling vs Realtime

- **Frontend** (`WorklistPageV2.tsx`): polling `useQuery` setiap **30 detik**
- **Tidak ada** SSE / WebSocket
- **Dampak:** Juri demo melihat antrean "diam" selama 30 detik; event baru tidak terlihat live

---

## 2. SKEMA DATABASE SAAT INI

### 2.1 Tabel yang relevan dengan antrean

| Tabel | Status | Kolom kunci antrean | Gap |
|-------|--------|---------------------|-----|
| `encounters` | ✅ Ada | `latest_tier`, `workflow_status`, `claimed_by`, `admitted_at`, `row_version` | Tidak ada `priority_score`, `tier_source`, `claim_expires_at`, `discharge_planned_at`, `queue_type`, `depth_level`, `queue_version` |
| `sla_events` | ✅ Ada | `encounter_id`, `event_type`, `from_tier`, `occurred_at` | Ada tapi tidak terhubung ke `queue_entries` (belum ada) |
| `sla_config` | ✅ Ada | `tier`, `target_hours`, `warning_hours` | Isi DRAFT — butuh validasi apoteker (CRQ-080) |
| `notifications` | ✅ Ada | `type`, `is_read` | Tidak ada push (hanya polling) |
| **`queue_entries`** | ❌ **TIDAK ADA** | — | **Tabel utama antrean** dari QUEUE_MANAGEMENT_PLAN Lampiran A |
| **`queue_events`** | ❌ **TIDAK ADA** | — | Jejak diff untuk SSE + audit operasional |
| **`missed_reconciliations`** | ❌ **TIDAK ADA** | — | Indikator keselamatan Q7 wajib |

### 2.2 Tabel `encounters` — kolom yang kurang untuk antrean penuh

```
PERLU DITAMBAH (di queue_entries, bukan encounters — agar encounters tidak membengkak):
  tier_rank           SMALLINT   -- 2=HIGH, 1=MED, 0=LOW (untuk ORDER BY SQL)
  tier_source         TEXT       -- RULE | ML | SLA
  priority_score      NUMERIC    -- skor komposit 0–100
  ml_percentile       NUMERIC    -- persentil ML dalam bangsal
  depth_level         SMALLINT   -- 3=penuh, 2=standar, 1=ringan (default OFF)
  sla_due_at          TEXT       -- timestamp jatuh tempo SLA
  next_due_at         TEXT       -- threshold SLA berikutnya (untuk tick)
  discharge_planned_at TEXT      -- discharge pressure
  claim_expires_at    TEXT       -- TTL klaim (lease 15 menit)
  queue_type          TEXT       -- BPMH | REVIEW
  queue_version       BIGINT     -- monoton; naik setiap perubahan
```

### 2.3 Alembic

- **Versi migrasi yang ada:** `8a108615ebc8` (initial schema B-101/B-102) — 1 file
- **Status:** Alembic terinstall, konfigurasi ada di `alembic.ini`, migrasi awal jalan
- **Dibutuhkan:** Migrasi baru untuk `queue_entries`, `queue_events`, `missed_reconciliations`

---

## 3. AUTH, STATE MACHINE, SLA — KONDISI SAAT INI

### 3.1 Auth & RBAC ✅

- JWT lengkap (`api/auth/jwt.py`, `rbac.py`) — stdlib HS256, tanpa `python-jose`
- Role: `PHARMACIST | TECHNICIAN | COORDINATOR | ADMIN | AUDITOR`
- **Siap dipakai** oleh endpoint antrean baru

### 3.2 State Machine ✅

**File:** `api/services/case_state_service.py`

State yang ada: `MENUNGGU_BPMH → BPMH_LENGKAP → DALAM_ANALISIS → MENUNGGU_TELAAH → DRAFT_REVIEW → SELESAI_APPROVE / SELESAI_EDIT / DITOLAK / ESKALASI / RETRIAGE / MENUNGGU_DPJP`

**Gap untuk antrean:**
- Tidak ada transisi eksplisit `→ queue_entries` saat state berubah
- State `DISCHARGE` (pasien pulang) belum ada — diperlukan untuk `missed_reconciliations`
- State `BATAL` (batal admisi) belum ada — Q-010 perlu ini

### 3.3 SLA Scheduler ✅

**File:** `api/services/sla_service.py` + `api/tasks/scheduler.py`

- APScheduler berjalan setiap **60 detik** — `run_sla_check()`
- Membuat `sla_events` (WARNING / BREACH) — idempoten per hari
- **Tidak** menghitung `priority_score` atau `queue_version` — hanya tier SLA
- **Gap:** Tidak tahu tentang `queue_entries` (belum ada); tidak memperbarui `next_due_at`

### 3.4 priomedrec_core ✅

**File:** `priomedrec_core/priority.py`, `pipeline.py`, `contracts.py`

- `compute_priority()` sudah menerapkan `max(ML, rules, SLA, current)` — **jaminan tier tidak turun**
- `run_phase_a()` dan `run_phase_b()` tersedia
- **Gap:**
  - Tidak ada `compute_queue_score()` (rumus §4.1 QUEUE_PLAN: 0.40·sla + 0.25·ml_pct + 0.15·severity + 0.10·discharge + 0.10·wait)
  - Tidak ada `apply_quota()` (kuota HIGH-ML ≤ 25% per bangsal)
  - Tidak ada `apply_hysteresis()` (stabilitas urutan)
  - Tidak ada `batch_rescore()` (vektorisasi numpy untuk tick)

---

## 4. ANALISIS POLLING & REALTIME

| Komponen | Implementasi saat ini | Target (QUEUE_PLAN) |
|----------|-----------------------|---------------------|
| Frontend refresh | Polling 30 detik (`refetchInterval`) | SSE `/events/queue` — diff per entry |
| Backend push | Tidak ada | `GET /events/queue` — EventSource, `queue_version` untuk resync |
| Tick antrean | APScheduler 60 detik (SLA saja) | Tick 60 dtk: scoring batch + tier escalation + lease cleanup + SSE publish |
| Klaim atomik | `UPDATE claimed_by WHERE claimed_by IS NULL` (kira-kira) | `BEGIN IMMEDIATE` (SQLite) / `FOR UPDATE SKIP LOCKED` (PG) |
| Heartbeat | Tidak ada | `POST /queue/{id}/heartbeat` — perpanjang lease |

---

## 5. ANALISIS FRONTEND

**File utama:** `web/src/pages/WorklistPageV2.tsx`, `DashboardPage.tsx`

| Fitur | Status | Catatan |
|-------|--------|---------|
| Daftar worklist + filter tier/status/ward | ✅ Ada | Polling 30s; belum SSE |
| Tier badge (HIGH/MED/LOW) | ✅ Ada (`TierBadge.tsx`) | Belum ada badge "sumber" (RULE/ML/SLA) |
| SLA countdown | ✅ Ada (`SlaCountdown.tsx`) | Berbasis `admitted_at` bukan `sla_due_at` |
| Klaim encounter | ✅ Ada | Tanpa lease/heartbeat/expired |
| Pagination | ✅ Ada | OFFSET-based; belum keyset |
| Tombol "Ambil berikutnya" | ❌ **Tidak ada** | **Fitur utama Q-008** |
| "Antrean Saya" (10 kasus) | ❌ **Tidak ada** | — |
| Virtualisasi baris (TanStack Virtual) | ❌ **Tidak ada** | Diperlukan untuk >100 baris |
| Aging strip | ❌ **Tidak ada** | — |
| Banner pembaruan ("N update baru") | ❌ **Tidak ada** | — |
| Badge sumber tier ("HIGH (aturan)") | ❌ **Tidak ada** | — |
| Command Center koordinator | ❌ **Tidak ada** | — |
| Label "Data Simulasi" | ❌ **Tidak ada** | Wajib (Q6) saat simulator aktif |

---

## 6. HOSPITAL SIMULATOR — STATUS

- **Tidak ada** direktori `simulator/`
- **Tidak ada** skrip Python simulator
- `scripts/seed_demo.py` — hanya seed statis S1–S10 (tidak bergerak)
- `scripts/demo_reset.py` — reset + reseed statis

---

## 7. PRASYARAT YANG BELUM ADA

Diurutkan berdasarkan dependensi:

| # | Prasyarat | Dibutuhkan oleh | Status |
|---|-----------|-----------------|--------|
| P1 | Tabel `queue_entries` + migrasi Alembic | Semua Q | ❌ Tidak ada |
| P2 | Tabel `queue_events` + migrasi | SSE, audit operasional | ❌ Tidak ada |
| P3 | Tabel `missed_reconciliations` + migrasi | Q-010, Q-011, keselamatan Q7 | ❌ Tidak ada |
| P4 | `queue_engine` di `priomedrec_core` | Q-002, Q-005, Q-007 | ❌ Tidak ada |
| P5 | Endpoint `POST /queue/next` (atomik) | Q-004, Q-008 | ❌ Tidak ada |
| P6 | SSE `/events/queue` | Q-006, Q-008 | ❌ Tidak ada |
| P7 | Lease heartbeat + TTL cleanup | Q-004, Q-005 | ❌ Tidak ada |
| P8 | Paket `simulator/` | Q-007 | ❌ Tidak ada |
| P9 | Kolom `tier_source`, `priority_score`, `claim_expires_at`, `depth_level`, `queue_version` | Semua Q | ❌ Tidak ada (di `queue_entries`) |
| P10 | State DISCHARGE + BATAL di state machine | Q-010 | ❌ Tidak ada |

### Apa yang SUDAH ada dan bisa langsung dipakai:

| Komponen | Dipakai oleh |
|----------|-------------|
| Auth JWT + RBAC lengkap | Semua endpoint baru |
| Alembic (terinstall + konfigurasi berjalan) | P1, P2, P3 |
| `priomedrec_core/priority.py` `compute_priority()` | Q-002 (perluasan) |
| `api/services/sla_service.py` `run_sla_check()` | Q-005 (perluasan) |
| APScheduler di `api/tasks/scheduler.py` | Q-005 (tick baru) |
| SLA config + sla_events + notifications | Q-005 |
| Claim/release + optimistic locking (`row_version`) | Q-004 (pola yang sama, diangkat ke queue_entries) |
| `priomedrec_core/pipeline.py` `run_phase_a()` | Q-002 (skor Fase A) |
| WorklistPageV2.tsx (polling, filter, badge) | Q-008 (ekstensi) |
| Seed S1–S10 deterministik | Q-007 (backfill mode) |

---

## 8. URUTAN IMPLEMENTASI YANG DISARANKAN

```
Q-001 (DB) → Q-002 (engine) → Q-003 (transisi A/B) 
  → Q-004+Q-005 (API+tick) → Q-006 (SSE) 
  → Q-007 (simulator) 
  → Q-008+Q-009 (frontend)
  → Q-010+Q-011 (events+metrics) 
  → Q-012 (uji beban+properti)
```

**Dependensi kritis:**
- Q-002 (`queue_engine`) bergantung pada Q-001 (tabel ada di DB)
- Q-004 (`POST /queue/next`) bergantung pada Q-002 (rumus skor) + Q-001 (tabel)
- Q-007 (simulator) bergantung pada Q-004 (endpoint atomik ada)
- Q-008 (frontend) bergantung pada Q-004 + Q-006 (SSE)

---

## 9. PERTANYAAN PEMBLOKIR

Berdasarkan audit ini, **tidak ada pertanyaan yang benar-benar memblokir** untuk Fase Q1–Q3 karena QUEUE_MANAGEMENT_PLAN sudah membuat semua keputusan default (D1–D7). Keputusan yang masih perlu konfirmasi klinis (tapi tidak memblokir implementasi teknis):

| Pertanyaan | Pemblokir untuk | Status |
|------------|----------------|--------|
| Apakah Level 1 (telaah ringan/batch) disetujui klinis? | Q-020 (P1, bukan P0) | Tidak memblokir Q0–Q3 |
| Bobot skor §4.1 sudah benar secara klinis? | Dikalibrasi via simulator (Q-007) | Tidak memblokir — pakai default |
| SLA HIGH=4jam, MED=12jam, LOW=24jam sudah sesuai RS? | CRQ-080 | Tidak memblokir — pakai default, catat di ASSUMPTIONS |

---

*Dokumen ini wajib diperbarui setiap kali prasyarat selesai atau gap baru ditemukan.*
