# QUEUE_IMPLEMENTATION_PLAN.md — Rencana Implementasi Manajemen Antrean
## Fase Q0 · Plan

**Versi:** 1.0  
**Tanggal:** Fase Q0  
**Dibuat oleh:** IBM Bob  
**Referensi:** PRIOMEDREC_QUEUE_MANAGEMENT_PLAN.md (sumber utama); docs/QUEUE_AUDIT.md (kondisi saat ini)  

> Dokumen ini adalah rencana operasional. Setiap ID Q-xxx = satu commit. Ikuti protokol: BACA → TULIS TES → IMPLEMENTASI → JALANKAN pytest → PERBARUI DOCS → COMMIT.

---

## PETA DEPENDENSI

```
Q-001 ──► Q-002 ──► Q-003
            │          │
            ▼          ▼
          Q-004 ◄─── Q-005
            │
            ▼
          Q-006 (SSE)    Q-007 (Simulator)
            │                   │
            └────────┬──────────┘
                     ▼
                Q-008 + Q-009 (Frontend)
                     │
                     ▼
              Q-010 + Q-011 (Events + Metrics)
                     │
                     ▼
                  Q-012 (Uji Beban)
```

---

## FASE Q1 — MESIN ANTREAN & DATA

### Q-001: Migrasi Alembic — Tabel Antrean

**Ukuran:** M · **Prio:** P0 · **Dependensi:** Alembic terinstall (✅ ada)

**Tujuan:** Buat tiga tabel baru tanpa kehilangan data lama.

**File yang dibuat/diubah:**
- `alembic/versions/YYYYMMDD_queue_tables.py` (BARU)
- `api/db/models.py` — tambah `QueueEntry`, `QueueEvent`, `MissedReconciliation`

**Skema (mengacu Lampiran A QUEUE_MANAGEMENT_PLAN):**

```python
# queue_entries
class QueueEntry(Base):
    __tablename__ = "queue_entries"
    encounter_id        = Column(String, ForeignKey("encounters.id"), primary_key=True)
    queue_type          = Column(String, nullable=False)   # BPMH | REVIEW
    ward                = Column(String, nullable=False)
    state               = Column(String, nullable=False)   # OPEN | CLAIMED | PARKED_DPJP | CLOSED
    tier_rank           = Column(SmallInteger, nullable=False)  # 2=HIGH 1=MED 0=LOW
    tier_source         = Column(String, nullable=False)   # RULE | ML | SLA
    priority_score      = Column(Numeric(6,2), nullable=False)
    ml_percentile       = Column(Numeric(4,3), nullable=True)
    depth_level         = Column(SmallInteger, nullable=False, default=2)  # 3/2/1
    admitted_at         = Column(String, nullable=False)
    sla_due_at          = Column(String, nullable=True)
    next_due_at         = Column(String, nullable=True)    # ambang SLA berikutnya
    discharge_planned_at = Column(String, nullable=True)
    claimed_by          = Column(String, ForeignKey("users.id"), nullable=True)
    claim_expires_at    = Column(String, nullable=True)    # TTL lease 15 menit
    queue_version       = Column(BigInteger, nullable=False, default=0)
    updated_at          = Column(String, nullable=False)
    # Indeks: (queue_type,ward,state,tier_rank DESC,priority_score DESC,encounter_id)
    #         (next_due_at) WHERE state IN ('OPEN','CLAIMED')
    #         (claimed_by, claim_expires_at) WHERE claimed_by IS NOT NULL

# queue_events
class QueueEvent(Base):
    __tablename__ = "queue_events"
    seq             = Column(BigInteger, primary_key=True, autoincrement=True)
    encounter_id    = Column(String, nullable=False, index=True)
    kind            = Column(String, nullable=False)  # upsert|remove|claim|release|promote
    payload_json    = Column(Text, nullable=False)
    at              = Column(String, nullable=False)

# missed_reconciliations
class MissedReconciliation(Base):
    __tablename__ = "missed_reconciliations"
    encounter_id    = Column(String, primary_key=True)
    discharged_at   = Column(String, nullable=False)
    last_state      = Column(String, nullable=True)
    last_tier       = Column(String, nullable=True)
    reason          = Column(String, nullable=True)  # DISCHARGE_BEFORE_REVIEW | CANCEL | etc
```

**Kriteria selesai:**
- [ ] `alembic upgrade head` berjalan tanpa error di SQLite baru dan DB yang sudah ada dengan data S1–S10
- [ ] `alembic downgrade -1` berjalan tanpa kehilangan data `encounters`
- [ ] `pytest tests/test_q001_migration.py` hijau (test: tabel ada, indeks ada, data lama tetap)

**Risiko:** SQLite tidak mendukung `ADD COLUMN` dalam beberapa dialek. Pakai `batch_alter_table` Alembic.

---

### Q-002: `queue_engine` di `priomedrec_core`

**Ukuran:** L · **Prio:** P0 · **Dependensi:** Q-001 (skema diketahui), `priority.py` yang ada

**Tujuan:** Modul `priomedrec_core/queue_engine.py` — deterministik, batch, tanpa LLM.

**File yang dibuat/diubah:**
- `priomedrec_core/queue_engine.py` (BARU)
- `priomedrec_core/queue_config.py` (BARU) — konfigurasi berversi
- `tests/test_q002_queue_engine.py` (BARU)
- `tests/test_q002_queue_properties.py` (BARU) — uji Hypothesis

**Fungsi utama yang harus ada:**

```python
# Konfigurasi berversi
@dataclass
class QueueConfig:
    version: str = "queue-0.1.0"
    # Bobot skor (§4.1 QUEUE_PLAN)
    w_sla_pressure: float = 0.40
    w_ml_percentile: float = 0.25
    w_severity_load: float = 0.15
    w_discharge_pressure: float = 0.10
    w_wait_norm: float = 0.10
    # Kuota HIGH-ML per bangsal
    ml_high_quota_pct: float = 0.25
    # Histeresis
    tier_hysteresis_margin: float = 0.05
    # SLA default
    sla_hours: dict = {
        "HIGH": {"target": 4.0, "warning": 2.0},
        "MEDIUM": {"target": 12.0, "warning": 6.0},
        "LOW": {"target": 24.0, "warning": 12.0},
    }

def compute_queue_score(entry: dict, now: datetime, cfg: QueueConfig) -> float:
    """
    priority_score = 100 × (
        cfg.w_sla_pressure   × sla_pressure(elapsed, tier_sla_target)
      + cfg.w_ml_percentile  × ml_percentile_in_ward  [0–1]
      + cfg.w_severity_load  × severity_load(discrepancies)  [0–1]
      + cfg.w_discharge_pressure × discharge_pressure(discharge_planned_at, now)  [0–1]
      + cfg.w_wait_norm      × wait_norm(admitted_at, now)  [0–1]
    )
    """

def apply_ml_quota(entries: list[dict], cfg: QueueConfig) -> list[dict]:
    """
    Entri yang HIGH hanya karena ML dibatasi ≤ cfg.ml_high_quota_pct per bangsal.
    HIGH karena RULE atau SLA tidak dikuota (Q1).
    """

def batch_rescore(entries: list[dict], now: datetime, cfg: QueueConfig) -> list[dict]:
    """Vektorisasi numpy — hitung ulang priority_score + tier_rank semua entri OPEN."""

def determine_next_due_at(entry: dict, cfg: QueueConfig) -> str:
    """Kapan entri ini perlu SLA naik? Threshold berikutnya dari now."""

def sort_queue(entries: list[dict]) -> list[dict]:
    """Deterministik: tier_rank↓, priority_score↓, admitted_at↑, encounter_id asc."""
```

**Contoh hitung wajib sebagai test (§4.4 QUEUE_PLAN):**
```python
# Pasien A: HIGH(aturan), sla_pressure=0.40, ml_pct=0.85, severity=1.0, discharge=0, wait=0.13
# Skor A = 100×(0.40×0.40 + 0.25×0.85 + 0.15×1.0 + 0.10×0 + 0.10×0.13)
#        = 100×(0.160 + 0.2125 + 0.150 + 0 + 0.013) = 53.6 ✓

# Pasien B: HIGH(ML), sla_pressure=0.04, ml_pct=0.95, severity=0, discharge=0, wait=0.01
# Skor B = 100×(0.016 + 0.2375 + 0 + 0 + 0.001) = 25.5 ✓

# Pasien C: MED(SLA), sla_pressure=0.25, ml_pct=0.30, severity=0, discharge=0.9, wait=0.50
# Skor C = 100×(0.10 + 0.075 + 0 + 0.09 + 0.05) = 31.5 ✓
# Urutan: A(HIGH,53.6) → B(HIGH,25.5) → C(MED,31.5)
```

**Uji properti (Hypothesis) — wajib ≥1.000 kasus acak:**
1. **P1:** Tidak ada dua entri dengan `state=CLAIMED` dan `claimed_by` sama pada waktu yang sama
2. **P2:** `tier_rank` tidak pernah turun jika `tier_source=RULE` tanpa event re-triage
3. **P3:** Tier tidak turun tanpa event re-triage (`RULE` floor tidak bisa dikurangi)
4. **P4:** Setiap entri OPEN mencapai `tier_rank=HIGH` atau diklaim paling lambat saat `next_due_at ≤ now + max_SLA`
5. **P5:** `sort_queue` menghasilkan urutan deterministik untuk input yang sama
6. **P6:** `queue_version` selalu naik (monoton) — tidak pernah turun

**Kriteria selesai:**
- [ ] Semua unit test hijau
- [ ] Properti P1–P6 lulus ≥1.000 kasus acak
- [ ] Contoh hitung §4.4 tepat (toleransi ±0.1)
- [ ] Tidak ada import dari `api/` atau Langflow di `queue_engine.py`

**Risiko:** Uji properti "anti-starvation" (P4) memerlukan simulasi waktu berjalan — gunakan `hypothesis` dengan `@settings(max_examples=1000)` dan mockable `now`.

---

### Q-003: Dua Antrean A/B + Transisi Event

**Ukuran:** M · **Prio:** P0 · **Dependensi:** Q-001 (tabel ada), Q-002 (engine ada)

**Tujuan:** Logika transisi: ADMIT → Antrean A (BPMH); BPMH submit → A→B (Telaah); DPJP → parkir.

**File yang dibuat/diubah:**
- `priomedrec_core/queue_transitions.py` (BARU)
- `api/services/queue_service.py` (BARU)
- `tests/test_q003_transitions.py` (BARU)

**Transisi yang harus diimplementasikan:**

| Event | Dari | Ke | Logika |
|-------|------|----|--------|
| ADMIT | — | `queue_entries` state=OPEN, queue_type=BPMH | Skor Fase A; `ward` dari encounter |
| BPMH_SUBMIT | BPMH OPEN | REVIEW OPEN | Skor Fase B; hitung ulang tier + skor |
| ORDER_CHANGE | REVIEW | REVIEW | Re-analisis + skor ulang (debounce 30 dtk/encounter) |
| TRANSFER | REVIEW/BPMH | REVIEW/BPMH ward baru | Re-triage; lepas klaim jika beda bangsal |
| DPJP_WAIT | REVIEW | state=PARKED_DPJP | Pewaktu sendiri; tidak hukum SLA apoteker |
| DPJP_RESPOND | PARKED_DPJP | REVIEW OPEN | Skor ulang |
| DISCHARGE | OPEN/CLAIMED | CLOSED | Jika bukan SELESAI → catat `missed_reconciliations` |
| CANCEL | OPEN/CLAIMED | CLOSED | Catat alasan pembatalan |
| APPROVE/SELESAI | CLAIMED | CLOSED | Arsip; tidak catat missed |
| SLA_ESCALATE | OPEN | OPEN tier naik | Dari tick; lepas klaim |
| CLAIM_EXPIRE | CLAIMED | OPEN | Dari tick; usia menunggu dipertahankan |

**Kriteria selesai:**
- [ ] Setiap transisi menghasilkan `queue_events` (idempoten dengan kunci `event_id`)
- [ ] `missed_reconciliations` terisi saat DISCHARGE sebelum SELESAI
- [ ] Tes: urutan event terbalik/duplikat/hilang → idempoten & konsisten
- [ ] Tidak ada panggilan LLM/Langflow di `queue_transitions.py`

---

## FASE Q2 — API, TICK, SSE, EVENT

### Q-004: API Endpoint Antrean

**Ukuran:** L · **Prio:** P0 · **Dependensi:** Q-001, Q-002, Q-003

**File yang dibuat/diubah:**
- `api/routes/v1/queue.py` (BARU)
- `api/routes/v1/__init__.py` (perbarui mount)
- `tests/test_q004_queue_api.py` (BARU)

**Endpoint yang dibutuhkan:**

| Endpoint | Method | Deskripsi | Auth |
|----------|--------|-----------|------|
| `/queue` | GET | Daftar antrean — keyset pagination, filter ward/tier/queue_type | PHARMACIST, TECHNICIAN, COORDINATOR |
| `/queue/next` | POST | Ambil & klaim entri teratas atomik | PHARMACIST, COORDINATOR |
| `/queue/{encounter_id}/heartbeat` | POST | Perpanjang lease 15 menit | PHARMACIST, COORDINATOR |
| `/queue/{encounter_id}/release` | POST | Lepas klaim manual | PHARMACIST, COORDINATOR, ADMIN |
| `/queue/{encounter_id}/admit` | POST | Ingest encounter baru ke antrean | TECHNICIAN, ADMIN, SYSTEM |
| `/queue/{encounter_id}/discharge` | POST | Trigger DISCHARGE → missed_reconciliation check | ADMIN, SYSTEM |

**GET /queue — keyset pagination:**
```
GET /queue?queue=REVIEW&ward=ICU&tier=HIGH
           &after=eyJ0...&limit=50
# after = base64({"tier_rank": 2, "priority_score": 53.6, "encounter_id": "xxx"})
```

**POST /queue/next — atomik:**
```python
# SQLite (demo):
# BEGIN IMMEDIATE
# UPDATE queue_entries SET state='CLAIMED', claimed_by=:uid,
#        claim_expires_at=now+900s, queue_version=queue_version+1
# WHERE encounter_id = (SELECT encounter_id FROM queue_entries
#   WHERE queue_type=:qt AND state='OPEN' AND ward IN (:scope)
#   ORDER BY tier_rank DESC, priority_score DESC, admitted_at, encounter_id
#   LIMIT 1)
# RETURNING *
```

**Uji konkurensi (wajib):**
- 20 klien menekan `/queue/next` serentak pada 200 entri → 0 duplikat klaim, 0 entri terlewat
- Gunakan `threading.Thread` atau `asyncio.gather` dalam test

**Kriteria selesai:**
- [ ] Tes konkurensi: 0 duplikat
- [ ] Tes keyset: halaman 2 konsisten setelah insert baru
- [ ] Lease 15 menit: klaim kedaluwarsa otomatis saat tick

---

### Q-005: Tick Batch + SLA Escalation + Lease Cleanup

**Ukuran:** M · **Prio:** P0 · **Dependensi:** Q-002 (engine), Q-001 (tabel)

**File yang dibuat/diubah:**
- `api/tasks/queue_tick.py` (BARU)
- `api/tasks/scheduler.py` (perbarui — tambah job `queue_tick`)

**Pseudokode tick:**
```python
def queue_tick(now: datetime):
    with tx(BEGIN_IMMEDIATE):
        rows = fetch_open_entries()          # ≤ ~5.000 dari queue_entries
        scores = batch_rescore(rows, now, cfg)
        for r in rows_where(next_due_at <= now):
            promote_tier(r, reason="SLA")
            log_sla_event(r)
        apply_ml_quota(rows, cfg)
        bulk_update(rows, scores)            # satu UPDATE batch
        expire_claims(now)                   # WHERE claim_expires_at <= now → state=OPEN
        session.commit()
    publish_diffs(changed_rows)              # ke SSE broadcast
```

**Sifat tick:**
- **Idempoten:** menjalankan dua kali pada input yang sama → hasil sama
- **Aman dua instance:** `BEGIN IMMEDIATE` (SQLite) / advisory lock (PG)
- **Tidak memanggil LLM/Langflow** (Q5)

**Kriteria selesai:**
- [ ] Tick selesai < 800 ms untuk 5.000 entri (diukur, bukan diklaim)
- [ ] Idempoten: jalankan 2× → `queue_version` naik 1× saja (bukan 2×)
- [ ] Lease yang expired kembali ke OPEN dengan `admitted_at` asli (tidak "mulai dari nol")

---

### Q-006: SSE `/events/queue`

**Ukuran:** M · **Prio:** P0 · **Dependensi:** Q-005 (tick publish diffs)

**File yang dibuat/diubah:**
- `api/routes/v1/queue_events.py` (BARU)

**Protokol SSE:**
```
GET /events/queue?since_version=12345&ward=ICU
---
event: upsert
data: {"encounter_id":"...", "tier_rank":2, "priority_score":53.6, "queue_version":12346}

event: remove
data: {"encounter_id":"...", "queue_version":12347}

event: heartbeat
data: {"queue_version": 12347, "ts": "..."}
```

- `Last-Event-ID` header → resync sejak versi tersebut
- Jika `queue_version` tertinggal > 100 → kirim event `resync` → klien muat ulang halaman
- Tidak ada data klinis sensitif di SSE (hanya tier, skor, encounter_id)

**Kriteria selesai:**
- [ ] Klien SSE menerima event dalam < 2 detik setelah tick
- [ ] Reconnect dengan `Last-Event-ID` → tidak ada event terlewat

---

### Q-010: Penanganan Event Idempoten

**Ukuran:** M · **Prio:** P0 · **Dependensi:** Q-003, Q-004

**Event yang harus ditangani (lihat §5 QUEUE_PLAN):**

| Event | Endpoint/trigger | Idempoten kunci |
|-------|-----------------|----------------|
| ADMIT | `POST /queue/{id}/admit` | `encounter_id` + kunci unik |
| TRANSFER | `POST /encounters/{id}/transfer` | `event_id` atau `(encounter_id, ward_baru, ts)` |
| DISCHARGE | `POST /queue/{id}/discharge` | `encounter_id` — hanya sekali |
| LAB_CRITICAL | `POST /queue/{id}/lab_critical` | `(encounter_id, lab_type, ts)` dedup 1 jam |
| ORDER_CHANGE | `POST /queue/{id}/order_change` | debounce 30 dtk per encounter |
| CANCEL | `POST /queue/{id}/cancel` | `encounter_id` |
| DUPLICATE_MERGE | `POST /queue/merge` | idempoten pada encounter_id target |

**Kriteria selesai:**
- [ ] Mengirim event yang sama 2× → hasil sama (idempoten)
- [ ] Urutan event terbalik (DISCHARGE sebelum ADMIT) → ditangani dengan graceful
- [ ] Semua event menghasilkan `queue_events` row

---

### Q-011: Metrik Antrean `/queue/metrics`

**Ukuran:** M · **Prio:** P0 · **Dependensi:** Q-001, Q-005

**Response schema:**
```json
{
  "backlog": {"BPMH": {"HIGH": 12, "MEDIUM": 45, "LOW": 23}, "REVIEW": {...}},
  "wip": {"total": 8, "by_pharmacist": {...}},
  "age_distribution": {"HIGH": {"p50_hours": 1.2, "p90_hours": 3.1, "p99_hours": 4.8}},
  "sla_compliance": {"HIGH_pct": 94.2, "MEDIUM_pct": 88.1},
  "missed_reconciliations": {"today": 3, "this_week": 12},
  "expired_claims": {"last_hour": 2},
  "tier_source_ratio": {"RULE": 0.35, "ML": 0.45, "SLA": 0.20},
  "queue_version": 12347,
  "cached_at": "2026-11-02T14:30:00Z"
}
```

- Cache 10 detik (bukan per-request query berat)
- **Kriteria selesai:**
  - [ ] `missed_reconciliations` tampil dan akurat
  - [ ] `tier_source_ratio` menunjukkan HIGH(RULE) vs HIGH(ML) — transparansi kuota

---

## FASE Q3 — HOSPITAL SIMULATOR

### Q-007: Hospital Simulator

**Ukuran:** L · **Prio:** P0 · **Dependensi:** Q-004 (endpoint `/queue/next` dan `/queue/{id}/admit` ada)

**Struktur direktori yang dibuat:**
```
simulator/
  __init__.py
  run.py              # entry point: python -m simulator.run
  config.py           # dataclass config + load dari YAML
  clock.py            # jam virtual (speed 1×–240×, pause/resume)
  arrival.py          # generator Poisson tak homogen (profil jam + hari)
  agents.py           # agen TTK, apoteker, DPJP (lognormal service time)
  events.py           # event acak (transfer, lab kritis, discharge, batal, duplikasi)
  api_client.py       # wrapper HTTP ke API asli (JWT per peran)
  scenarios.py        # evening_surge, staff_shortage, llm_outage, ml_outage
  report.py           # laporan akhir simulasi
configs/
  simulator_M.yaml    # konfigurasi ukuran M (Lampiran B QUEUE_PLAN)
  simulator_S.yaml
  simulator_L.yaml
docs/
  SIMULATION_REPORT.md  (dibuat saat akhir simulasi)
```

**Perintah:**
```bash
python -m simulator.run --size M --speed 60 --scenario evening_surge --seed 42
make demo-live       # alias perintah di atas
make demo-reset      # python scripts/demo_reset.py + seed_demo.py
```

**Konfigurasi minimal dari Lampiran B QUEUE_PLAN:**
```yaml
seed: 42
size: M
clock: {speed: 60, start: "2026-11-02T06:00:00+07:00"}
wards:
  - {name: "Penyakit Dalam", beds: 200, bor: 0.78, ...}
arrivals:
  hourly_profile: [0.3, 0.2, ..., 1.6, ...]  # 24 nilai
  weekday_factor: {Mon: 1.15, ...}
bpmh: {median_minutes: 45, sigma: 0.6, incomplete_rate: 0.15}
pharmacists:
  shifts: {pagi: ["07:00","14:00",3], siang: ["14:00","21:00",2], malam: ["21:00","07:00",1]}
  service_minutes: {HIGH: {median: 30}, MED: {median: 20}, LOW: {median: 8}}
events: {transfer: 0.03, discharge_before_review: 0.05, ...}
scenarios:
  evening_surge: {at: "17:00", arrivals_multiplier: 2.0, duration_hours: 4}
label: "Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS"
```

**Label wajib (Q6):** Setiap output simulator (log, UI, laporan) harus menyertakan:
> `"Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS"`

**Laporan akhir simulasi** (`docs/SIMULATION_REPORT.md`) harus berisi:
- SLA HIGH compliance (%)
- p50/p90 waktu tunggu per tier
- Missed reconciliation count
- Rasio beban (demand/capacity)
- Parameter yang perlu dikalibrasi dengan RS mitra

**Kriteria selesai:**
- [ ] `python -m simulator.run --size M --speed 60 --seed 42` berjalan 24 jam-virtual (~12 menit real)
- [ ] Hasil reprodusibel dengan seed yang sama (dua kali run → laporan identik)
- [ ] Tidak ada entri yatim (encounter ada di `queue_events` tapi tidak di `queue_entries`)
- [ ] Label "Data simulasi" tampil di semua output
- [ ] `docs/SIMULATION_REPORT.md` dihasilkan otomatis

---

## FASE Q4 — FRONTEND ANTREAN & COMMAND CENTER

### Q-008: Frontend Antrean

**Ukuran:** L · **Prio:** P0 · **Dependensi:** Q-004 (API), Q-006 (SSE)

**File yang dibuat/diubah:**
- `web/src/pages/QueuePage.tsx` (BARU) — halaman utama antrean
- `web/src/components/NextPatientButton.tsx` (BARU) — tombol "Ambil berikutnya"
- `web/src/components/MyQueue.tsx` (BARU) — Antrean Saya ±10 kasus
- `web/src/components/WardQueue.tsx` (BARU) — Antrean Bangsal (TanStack Virtual)
- `web/src/components/AgingStrip.tsx` (BARU) — distribusi usia per tier
- `web/src/components/UpdateBanner.tsx` (BARU) — "N pembaruan — muat ulang urutan"
- `web/src/components/TierSourceBadge.tsx` (BARU) — "HIGH (aturan)" / "HIGH (ML)"
- `web/src/hooks/useQueueSSE.ts` (BARU) — EventSource hook
- `web/src/lib/apiClient.ts` (perbarui) — tambah `getQueue`, `postQueueNext`, dll.

**Fitur wajib:**
| Fitur | Perilaku |
|-------|----------|
| Tombol "Ambil pasien berikutnya" | Klik → `POST /queue/next` → buka Case Workspace; tampil "Mengapa pasien ini?" |
| Pintasan keyboard `N` | Sama dengan tombol |
| Antrean Saya | ±10 kasus: sedang dikerjakan + 5 berikutnya; indikator lease countdown |
| Antrean Bangsal | Server-side, TanStack Virtual, keyset cursor, filter tier/status/ward |
| Aging strip | Distribusi visual usia menunggu (0–25–50–75–100% SLA) per tier |
| Banner pembaruan | Baris tidak melompat; "12 pembaruan baru — Muat ulang urutan" |
| Badge sumber tier | "HIGH (aturan)" 🔴 / "HIGH (ML)" 🟠 / "MED (SLA)" 🟡 + persentil |
| Status koneksi SSE | Indikator "live" / "reconnecting" / "offline" |
| Indikator "Data Simulasi" | Banner oranye jika mode simulator aktif |
| Fallback ML/LLM mati | Banner kuning "ML tidak tersedia — urutan berdasarkan aturan+SLA" |

**Playwright e2e wajib:**
1. Klik "Ambil berikutnya" → Case Workspace terbuka dengan pasien HIGH
2. Lease kedaluwarsa → kasus kembali ke antrean
3. Banner pembaruan muncul setelah tick
4. IGD surge (simulator) → backlog naik, mode lonjakan aktif
5. Pasien pulang sebelum telaah → missed reconciliation tampil

**Kriteria selesai:**
- [ ] Demo 60–90 detik skenario §9.4 QUEUE_PLAN berjalan mulus
- [ ] Tidak ada tabel tanpa paginasi/virtualisasi
- [ ] `npm run build` 0 TypeScript error

---

### Q-009: Command Center Dasar

**Ukuran:** L · **Prio:** P0 · **Dependensi:** Q-011 (metrics), Q-008 (SSE)

**File yang dibuat/diubah:**
- `web/src/pages/CommandCenterPage.tsx` (BARU)
- `web/src/components/CapacityGauge.tsx` (BARU)
- `web/src/components/WardHeatmap.tsx` (BARU)
- `web/src/components/AgeHistogram.tsx` (BARU)
- `web/src/components/SlaRiskList.tsx` (BARU)

**Fitur Command Center (dasar):**
| Komponen | Deskripsi |
|----------|-----------|
| Gauge permintaan vs kapasitas | Menit demand / menit kapasitas; konfigurasi apoteker bertugas |
| Peta panas bangsal×tier | Grid warna: bangsal (baris) × tier (kolom) → jumlah entri |
| Histogram usia menunggu | Distribusi per tier (kolom) |
| Daftar berisiko SLA | Entri HIGH yang mendekati jatuh tempo (< 1 jam) |
| Banner mode lonjakan | Rekomendasi saja — tidak mengubah tier HIGH |
| Indikator "Data Simulasi" | Wajib (Q6) |

**Kriteria selesai:**
- [ ] Command Center dapat diakses oleh COORDINATOR dan ADMIN
- [ ] Semua angka di-klik-kan ke daftar yang menyusunnya (drilldown)
- [ ] "Data simulasi" tampil saat mode simulator

---

## FASE Q5 — UJI BEBAN & P1

### Q-012: Uji Beban + Properti + Konkurensi

**Ukuran:** M · **Prio:** P0 · **Dependensi:** Q-001..Q-011 selesai

**Target performa (§6.4 QUEUE_PLAN) pada 5.000 entri:**

| Operasi | Target P95 | Alat |
|---------|-----------|------|
| `GET /queue` (50 baris) | < 300 ms | k6 / Locust |
| `POST /queue/next` | < 200 ms (0 duplikat) | k6 concurrent |
| Tick batch | < 800 ms | Python timer |
| Latensi SSE (event → UI) | < 2 dtk | Playwright |
| `POST /queue/{id}/admit` | < 500 ms | k6 |
| 50 pengguna serentak | Tanpa timeout | k6 load test |
| 60 event/menit | Backlog stabil | Simulator |

**Hasil dilaporkan apa adanya — termasuk yang gagal beserta rencana perbaikan.**

**Kriteria selesai:**
- [ ] G1: pytest hijau (lama + baru)
- [ ] G2: properti P1–P6 lulus ≥1.000 kasus
- [ ] G3: konkurensi 0 duplikat klaim
- [ ] G4: simulator reprodusibel, stabil 24j-virtual
- [ ] G5: performa diukur dan dilaporkan jujur
- [ ] G7: ML/LLM/Langflow dimatikan → antrean tetap bergerak
- [ ] G8: missed reconciliation tercatat dan tampil

---

## BACKLOG P1 (setelah Q-012)

| ID | Item | Dependensi |
|----|------|-----------|
| Q-020 | Mode lonjakan + Level 1 (default OFF, spot-check) | Q-009, Q-012 |
| Q-021 | Laporan serah terima shift (UI + PDF) | Q-008 |
| Q-022 | Prakiraan kapasitas 4 jam | Q-011 |
| Q-023 | Keadilan antar-bangsal + overflow | Q-002 (perluasan) |
| Q-024 | PostgreSQL (`SKIP LOCKED`) + uji lintas-DB | Q-001 (migrasi kompatibel) |
| Q-025 | Adapter stub HL7 ADT / FHIR Subscription | Q-003 |
| Q-026 | Tampilan tersimpan + aksi massal aman | Q-008 |
| Q-027 | Langflow tools `explain_queue_position`, `summarize_my_queue` | Q-004 |

---

## RINGKASAN GERBANG MUTU

| Gerbang | Deskripsi | Fase |
|---------|-----------|------|
| G1 | pytest lama+baru hijau | Q1+ |
| G2 | Properti Q1–Q7 lulus ≥1.000 kasus | Q1 |
| G3 | Konkurensi: 0 duplikat klaim | Q2 |
| G4 | Simulator: reprodusibel, stabil 24j-virtual | Q3 |
| G5 | Performa §6.4 tercapai atau dilaporkan jujur | Q5 |
| G6 | Playwright e2e hijau | Q4 |
| G7 | ML/LLM/Langflow mati → antrean tetap bergerak | Q2 |
| G8 | Missed reconciliation tercatat & tampil | Q2 |
| G9 | Label "Data simulasi" di semua tampilan mode simulasi | Q3 |
| G10 | `docker compose up` + `make demo-live` dari nol berhasil | Q3 |
| G11 | Dokumen sinkron (DECISION_LOG, API, schema, README) | Semua |

---

*Rencana ini akan diperbarui di setiap akhir fase. Setiap perubahan dicatat di `docs/DECISION_LOG.md`.*
