# PRIOMED-REC — QUEUE MANAGEMENT AT HOSPITAL SCALE
## Mengelola antrean ratusan–ribuan pasien yang terus bergerak, dan membuat aplikasi terlihat (dan benar-benar) realistis

| | |
| :--- | :--- |
| **Dokumen** | Delta Plan v5.2 — melengkapi `PRIOMEDREC_STRATEGIC_DEVELOPMENT_PLAN.md` (§5.2, §5.3, §8.3) dan `PRIOMEDREC_LANGFLOW_MAXIMIZATION_PLAN.md` |
| **Tanggal** | 29 Oktober 2026 |
| **Pertanyaan pemicu** | "Antrean di RS terus bergerak dan bukan 10 pasien, bisa ratusan–ribuan. Bagaimana mengelolanya dan membuat aplikasi realistis?" |
| **Prinsip yang tidak berubah** | Keselamatan deterministik, human-in-the-loop, audit tak dapat diubah, ML hanya mengurutkan |

> **Catatan jujur tentang angka.** Semua angka volume, durasi telaah, dan bobot skor di dokumen ini adalah **asumsi awal yang dapat dihitung ulang**, bukan data RS nyata. Angka tersebut **wajib dikalibrasi** dengan data RS mitra (cukup 1–2 minggu cap waktu admisi teranonimasi + wawancara kepala instalasi farmasi). Simulator di §9 memang dirancang agar parameter ini mudah diganti.

---

## 1. RINGKASAN JAWABAN (BACA INI DULU)

1. **Masalahnya bukan "mengurutkan 1.000 pasien", tetapi "kapasitas apoteker lebih kecil daripada beban masuk".** Mengurutkan 1.000 baris itu mudah bagi database; yang sulit adalah memutuskan *siapa yang dikerjakan lebih dulu, siapa yang dikerjakan dengan telaah lebih ringan, dan apa yang terjadi bila antrean menumpuk*.
2. **Apoteker tidak boleh diminta menggulir ribuan baris.** Sistem harus **menarik (pull)**: tombol **"Ambil pasien berikutnya"** yang mengunci pasien teratas untuk apoteker tersebut, plus "Antrean Saya" berisi ±10 kasus teratas.
3. **Dua antrean, bukan satu:** (A) *Antrean BPMH* untuk TTK/magang (diurutkan skor ML Fase A) dan (B) *Antrean Telaah* untuk apoteker (diurutkan prioritas komposit).
4. **Prioritas harus dinamis dan adil:** skor komposit + *aging* (menunggu makin lama, makin naik) + dorongan "mau pulang" + kuota agar tidak semuanya HIGH + lantai aturan klinis (tidak boleh diturunkan).
5. **Telaah bertingkat (review depth):** HIGH = telaah penuh; MEDIUM = telaah standar; LOW tanpa temuan = telaah ringan/batch dengan *spot-check*. *(Usulan; butuh persetujuan klinis, default OFF.)*
6. **Mode lonjakan (surge)** dan **dasbor kapasitas** untuk koordinator: permintaan vs kapasitas, prakiraan backlog, rekomendasi.
7. **Teknis skala:** tabel `queue_entries` terdenormalisasi + indeks tepat, *keyset pagination*, pembaruan SSE berbentuk *diff*, klaim dengan *lease*, pengambilan atomik (`SKIP LOCKED` di PostgreSQL). 5.000 entri terbuka masih ringan untuk PostgreSQL.
8. **Realisme demo:** bangun **Hospital Simulator ("Live Hospital Mode")** yang memanggil API asli: pasien datang mengikuti pola jam, apoteker simulasi bekerja, ada pindah bangsal/lab kritis/pulang, jam dipercepat. Antrean *benar-benar bergerak* di depan juri.
9. **Jalur antrean tidak boleh bergantung pada LLM/Langflow per pasien** (latensi & biaya). Langflow dipakai untuk analisis per kasus saat dibuka, penjelasan, dan copilot (§12).

---

## 2. REALITAS OPERASIONAL: BERAPA BESAR ANTREANNYA?

### 2.1 Hitungan kasar (Hukum Little) — asumsi, untuk dikalibrasi

`pasien masuk per hari ≈ (tempat tidur × BOR) ÷ ALOS`

| RS (tempat tidur) | BOR | ALOS (hari) | Admisi/hari | Admisi/bulan | Pasien rawat inap serentak |
| :-: | :-: | :-: | :-: | :-: | :-: |
| 100 | 70% | 4 | ±18 | ±530 | 70 |
| 250 | 75% | 4 | ±47 | ±1.400 | 190 |
| 500 | 75% | 5 | ±75 | ±2.250 | 375 |
| 1.000 | 75% | 5 | ±150 | ±4.500 | 750 |

**Pembacaan:** "ribuan pasien" umumnya muncul sebagai **jumlah kumulatif per bulan** atau saat **terjadi backlog parah**, bukan jumlah yang *sedang menunggu* pada satu waktu. Antrean aktif RS tipe B/A biasanya **puluhan hingga beberapa ratus**. Namun sistem **tetap harus dirancang dan diuji untuk 5.000 entri terbuka** (stres/backlog/multi-RS) agar tidak runtuh.

### 2.2 Antrean ini dibatasi kapasitas (capacity-constrained)

Contoh ilustratif (RS 500 tempat tidur, ±80 admisi/hari; menit telaah *asumsi*):

| Tier | Porsi | Menit telaah/pasien | Menit/hari |
| :-: | :-: | :-: | :-: |
| HIGH | 20% | 30 | 480 |
| MEDIUM | 40% | 20 | 640 |
| LOW | 40% | 8 (telaah ringan) | 256 |
| **Total permintaan** | | | **≈ 1.376 menit ≈ 23 jam/hari** |

Satu apoteker klinis dengan **±60% waktu produktif** untuk rekonsiliasi ≈ 4,8 jam/shift ⇒ butuh **±4–5 apoteker-shift per hari** hanya untuk rekonsiliasi admisi. Banyak RS tidak memiliki itu ⇒ **backlog struktural**. Inilah alasan fitur prioritisasi bernilai: bukan sekadar urutan, tetapi **alokasi kapasitas yang langka**, dan inilah yang harus tampak di aplikasi (permintaan vs kapasitas).

### 2.3 Dinamika yang membuat antrean "bergerak terus"

| Dinamika | Dampak pada antrean |
| :--- | :--- |
| Kedatangan tidak merata (lonjakan IGD sore–malam, Senin pagi) | Gelombang beban; backlog malam hari |
| Shift & serah terima (pagi/siang/malam) | Klaim menggantung, kapasitas turun di malam/akhir pekan |
| BPMH selesai terlambat/bertahap | Kasus berpindah dari antrean A ke B kapan saja |
| Pindah bangsal (IGD→ICU→bangsal) | Re-triage, perubahan penanggung jawab |
| Hasil lab kritis / order baru | Prioritas dapat naik mendadak |
| Pasien pulang sebelum telaah | Entri harus keluar + dicatat sebagai *missed reconciliation* |
| Pendaftaran ganda / batal admisi | Entri duplikat/yatim perlu dibersihkan |
| Menunggu DPJP | Kasus "parkir" yang tidak boleh menghukum SLA apoteker |

---

## 3. MODEL ANTREAN YANG DIREKOMENDASIKAN

### 3.1 Dua antrean dengan kebijakan urutan berbeda

```text
 ADMISI ──► [ANTREAN A: BPMH]  ──TTK/magang──► BPMH selesai ──► [ANTREAN B: TELAAH] ──apoteker──► SELESAI
             urut: skor ML Fase A               (event)           urut: prioritas komposit
             + lama menunggu + bangsal                            (tier, SLA, aging, discharge, ML)
                                                                  ↳ parkir: MENUNGGU_DPJP (pewaktu terpisah)
```

| | Antrean A (BPMH) | Antrean B (Telaah) |
| :--- | :--- | :--- |
| Pelaku | TTK / mahasiswa magang / apoteker | Apoteker klinis |
| Tujuan | Mengumpulkan BPMH untuk yang paling mungkin bermasalah lebih dulu | Menelaah temuan & memutuskan |
| Data tersedia | Fase A (fitur saat registrasi) | Fase B (BPMH + order + alergi) |
| Urutan | Skor ML Fase A + aging + bangsal | Prioritas komposit (§4) |
| SLA | Waktu ke BPMH selesai | Waktu ke telaah pertama & ke penyelesaian |

### 3.2 Pull-based: "Ambil pasien berikutnya"
- Apoteker memilih **cakupan** (bangsal yang ia pegang + opsi "bantu bangsal lain").
- `POST /queue/next` memilih entri teratas yang **belum diklaim**, sesuai cakupan, lalu **mengunci atomik** (tidak mungkin dua apoteker mendapat pasien yang sama).
- **Lease klaim** 15 menit, diperpanjang oleh *heartbeat* selama kasus terbuka; kedaluwarsa → kasus kembali ke antrean **dengan usia menunggu tetap** (tidak "mulai dari nol").
- Akhir shift: semua klaim dilepas otomatis dan masuk laporan serah terima.

### 3.3 Segmentasi per bangsal (satelit farmasi) + overflow
- Tiap apoteker/TTK memiliki **penugasan bangsal** (dapat berubah per shift).
- **Overflow:** bila antrean suatu bangsal melewati ambang (mis. HIGH yang mendekati SLA), kasus muncul pada antrean apoteker *floating*/bangsal tetangga dengan penanda "bantuan".
- **Keadilan antar-bangsal:** kuota ringan agar satu bangsal ramai tidak "menghabiskan" semua kapasitas (§4.5).

### 3.4 Telaah bertingkat (review depth) — *usulan, butuh persetujuan klinis*

| Level | Untuk | Isi pekerjaan apoteker | Catatan keselamatan |
| :-: | :--- | :--- | :--- |
| **3 — Penuh** | HIGH | Workspace lengkap, SBAR, kontak DPJP, keputusan | Hard stop high-alert berlaku |
| **2 — Standar** | MEDIUM | Telaah temuan, SBAR bila perlu | — |
| **1 — Ringan/batch** | LOW **dan** tidak ada temuan Tier 1/2, BPMH lengkap, tanpa high-alert, tanpa konflik alergi | Konfirmasi massal hasil rule engine "tidak ada temuan yang perlu ditindaklanjuti" | **Spot-check acak (mis. 10%)** oleh apoteker senior; **default OFF** sampai disetujui komite farmasi (S10); setiap aksi massal tetap tercatat di audit per pasien |

### 3.5 Mode lonjakan (surge)
- **Pemicu (dapat diatur):** rasio permintaan/kapasitas > 1,3 **atau** p90 usia menunggu HIGH > 75% SLA **atau** backlog > N.
- **Tindakan otomatis/anjuran:** banner ke koordinator; aktifkan overflow lintas-bangsal; (bila disetujui) aktifkan Level 1 untuk LOW; tampilkan estimasi tambahan jam apoteker yang dibutuhkan; catat periode lonjakan untuk laporan mutu.
- **Tidak pernah:** menurunkan tier HIGH karena kepadatan, atau menyembunyikan pasien dari antrean.

---

## 4. ALGORITMA PRIORITAS DINAMIS

### 4.1 Dua tingkat (tier dulu, lalu skor)

```text
TINGKAT 1 — TIER (penentu utama)
  tier_final = max( tier_ML_terkuota , lantai_aturan , lantai_SLA )
     lantai_aturan : ada temuan Tier-1 / obat High-Alert / konflik alergi  → minimal HIGH (TIDAK DIKUOTA)
     lantai_SLA    : melewati ambang menunggu → naik bertahap (LOW→MED→HIGH)
     tier_ML_terkuota : lihat 4.2 (agar tidak semua HIGH)

TINGKAT 2 — SKOR DALAM TIER (0–100), dihitung batch
  priority_score = 100 × ( 0.40·sla_pressure
                         + 0.25·ml_percentile
                         + 0.15·severity_load
                         + 0.10·discharge_pressure
                         + 0.10·wait_norm )
  Pengurutan: tier_rank ↓, priority_score ↓, admitted_at ↑, encounter_id (penentu akhir, deterministik)
```

| Komponen | Definisi (0–1) | Maksud |
| :--- | :--- | :--- |
| `sla_pressure` | `min(elapsed / target_SLA, 2) / 2` | Makin dekat/lewat batas waktu, makin naik |
| `ml_percentile` | Persentil skor ML di antara entri terbuka **pada bangsal yang sama** | Kemungkinan diskrepansi relatif |
| `severity_load` | Bobot temuan: Σ(Tier-1×1,0 + Tier-2×0,4 + Tier-3×0,1) dinormalisasi | Beratnya temuan (Fase B) |
| `discharge_pressure` | 1 bila rencana pulang ≤ 12 jam; skala turun hingga 0 pada ≥ 48 jam | Menghindari pulang tanpa rekonsiliasi |
| `wait_norm` | `min(lama_menunggu / 24 jam, 1)` | Anti *starvation* |
Bobot di atas = **titik awal**; dikalibrasi lewat simulasi (§9) dan masukan apoteker; disimpan di konfigurasi berversi.

### 4.2 Kuota tier ML (agar HIGH tetap bermakna)
- Ambang absolut (probabilitas terkalibrasi) menentukan **kelayakan** HIGH/MED.
- **Kuota:** entri yang naik HIGH *hanya karena ML* dibatasi ≤ **Q% dari antrean aktif** (default 25%) per bangsal; sisanya MEDIUM. **HIGH karena aturan klinis tidak dikuota.**
- UI menampilkan sumber: "HIGH (aturan)" vs "HIGH (ML)" dan **persentil** selain probabilitas, karena peringkat relatif lebih jujur daripada probabilitas absolut pada data sintetis.

### 4.3 Stabilitas urutan (agar baris tidak "melompat")
- **Histeresis:** perubahan tier akibat ML hanya jika selisih skor melewati margin; kenaikan karena aturan/SLA langsung berlaku.
- **Urutan dibekukan selama dibaca:** UI menampilkan banner "12 pembaruan baru — Muat ulang urutan" alih-alih memindahkan baris di bawah kursor.
- Entri yang sedang diklaim **tidak ikut diurutkan ulang**; ia berada di "Sedang Saya Tangani".

### 4.4 Contoh hitung (ilustratif)

| Pasien | Tier | sla_pressure | ml_pct | severity | discharge | wait | **Skor** |
| :--- | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| A (warfarin tak ada di order, 3,2 jam dari target 4 jam) | HIGH(aturan) | 0,40 | 0,85 | 1,00 | 0,0 | 0,13 | 0,160+0,2125+0,15+0+0,013 = **53,6** |
| B (HIGH-ML, baru 20 menit) | HIGH(ML) | 0,04 | 0,95 | 0,0 | 0,0 | 0,01 | 0,016+0,2375+0+0+0,001 = **25,5** |
| C (LOW menunggu 12 jam dari target 24 jam → naik MED; rencana pulang 8 jam) | MED(SLA) | 0,25 | 0,30 | 0,0 | 0,9 | 0,50 | 0,10+0,075+0+0,09+0,05 = **31,5** |
**Urutan:** A (HIGH, 53,6) → B (HIGH, 25,5) → C (MED, 31,5). Tier menentukan blok; skor hanya mengurutkan di dalam blok (C tidak melampaui B walau skornya lebih tinggi, karena tier-nya lebih rendah).

### 4.5 Keadilan, anti-starvation, dan jaminan
1. **Tidak ada kelaparan:** setiap entri terbuka mencapai HIGH atau diklaim paling lambat pada batas SLA maksimum (properti yang diuji, §11).
2. **Keadilan bangsal:** bila satu bangsal menyerap > X% klaim dalam 2 jam sementara bangsal lain memiliki HIGH hampir jatuh tempo, "Ambil berikutnya" menggeser ke bangsal yang tertinggal (kecuali apoteker mengunci cakupan).
3. **Lantai aturan tidak pernah turun** (selaras ADR-03).
4. **Parkir DPJP:** kasus `MENUNGGU_DPJP` keluar dari antrean B (tetap tampil di "Menunggu"), dengan pewaktu sendiri dan eskalasi ke koordinator, bukan penalti SLA apoteker.

---

## 5. SIKLUS HIDUP ENCOUNTER & EVENT YANG MENGGERAKKAN ANTREAN

| Event (sumber ADT/HL7/FHIR) | Efek pada antrean | Catatan |
| :--- | :--- | :--- |
| **Admit** (ADT^A01 / `Encounter` baru) | Buat `queue_entry` di Antrean A; skor Fase A; mulai pewaktu | Idempoten (kunci: `encounter_id`) |
| **BPMH submit** | Pindah A → B; hitung Fase B; urut ulang | — |
| **Order admisi masuk/berubah** | Re-analisis (Fase B), skor ulang | Pembatas laju per encounter (debounce 30 dtk) |
| **Transfer** (ADT^A02) | Ganti bangsal; **re-triage**; lepas klaim bila apoteker beda bangsal | Riwayat tidak hilang |
| **Lab kritis** (mis. K⁺, INR, kreatinin) | Naikkan lantai (tandai "perlu telaah ulang") | Hanya jenis lab yang dipakai aturan |
| **Rencana pulang ditetapkan** | `discharge_pressure` naik; Discharge check aktif | — |
| **Discharge** (ADT^A03) | Jika belum SELESAI → keluar antrean + catat **missed reconciliation**; jika SELESAI → arsip | Metrik keselamatan utama |
| **Batal admisi / duplikasi** (ADT^A11 / A08, penggabungan) | Tutup entri (alasan) / gabungkan, pertahankan audit | Cegah entri yatim |
| **Pergantian shift** | Lepas klaim, cetak serah terima, hitung ulang kapasitas | — |
| **SLA warning/breach** | Naik tier, notifikasi, `sla_events` | Terjadwal |
| **Koreksi data (A08)** | Skor ulang bila berpengaruh | — |

---

## 6. ARSITEKTUR TEKNIS UNTUK SKALA

### 6.1 Prinsip
1. **Pisahkan "antrean" dari "encounter":** tabel `queue_entries` terdenormalisasi khusus untuk membaca daftar kerja (cepat), sementara data klinis tetap di tabel masing-masing.
2. **Jalur antrean bebas LLM/Langflow:** penentuan urutan memakai `priomedrec_core` (batch, deterministik).
3. **Event-driven + tick ringan:** perubahan memicu perhitungan ulang entri terkait; *tick* periodik hanya untuk aging/SLA.
4. **Pembaruan ke klien berbentuk diff** (bukan memuat ulang seluruh daftar).
5. **Mulai sederhana:** pada ≤ 5.000 entri terbuka, hitung ulang batch tiap menit masih ringan. Optimalkan (Redis ZSET, partisi) hanya bila terukur perlu.

### 6.2 Skema data antrean (ringkas; SQL di Lampiran A)
`queue_entries(encounter_id PK, queue_type, ward, state, tier_rank, tier_source, priority_score, ml_percentile, sla_due_at, next_due_at, depth_level, claimed_by, claim_expires_at, queue_version, updated_at)`
Indeks utama: `(queue_type, ward, state, tier_rank DESC, priority_score DESC, encounter_id)` untuk daftar; `(next_due_at) WHERE state='OPEN'` untuk eskalasi; `(claimed_by, claim_expires_at)` untuk lease.

### 6.3 Operasi inti

| Operasi | Implementasi | Catatan |
| :--- | :--- | :--- |
| **Daftar antrean** | `GET /queue?queue=B&ward=&tier=&q=&after=<kursor>&limit=50` — *keyset pagination* pada (tier_rank, priority_score, encounter_id) | Tanpa `OFFSET`; stabil walau data berubah |
| **Ambil berikutnya** | `POST /queue/next` — satu transaksi: pilih entri teratas yang `claimed_by IS NULL` sesuai cakupan → set klaim + `claim_expires_at` | PostgreSQL: `FOR UPDATE SKIP LOCKED`; SQLite (demo): `BEGIN IMMEDIATE` + `UPDATE … WHERE claimed_by IS NULL … RETURNING` |
| **Heartbeat/lepas klaim** | `POST /queue/{id}/heartbeat` · `/release` | Lease 15 menit; kedaluwarsa dilepas oleh tick |
| **Hitung ulang entri** | `queue_engine.rescore(encounter_ids[])` (batch, vectorized) | Dipanggil oleh event; debounce per encounter |
| **Tick (60 dtk)** | Hitung ulang skor aging semua entri OPEN dalam **satu transaksi batch**; naikkan tier untuk `next_due_at ≤ now`; tulis `sla_events`; bersihkan klaim kedaluwarsa | Idempoten; aman bila dua instance berjalan (kunci penasihat/`SKIP LOCKED`) |
| **Pembaruan ke UI** | SSE `/events/queue` mengirim `{type: upsert|remove|claim, entry, queue_version}`; klien menambal cache; sambung ulang dengan `Last-Event-ID`/`since_version` → bila tertinggal jauh, muat ulang halaman | Hindari *thundering herd* |
| **Metrik antrean** | `GET /queue/metrics` (agregasi SQL; cache 10 dtk) | Untuk Command Center |

### 6.3.1 Pseudo-kode inti
```python
def tick(now):
    with tx():
        rows = fetch_open_entries()                     # <= ~5.000
        feats = vectorize(rows, now)                    # numpy: sla_pressure, wait_norm, ...
        scores = score(feats, cfg)                      # priority_score
        for r in rows_where(next_due_at <= now):        # lompatan tier karena SLA
            promote_tier(r, reason="SLA"); log_sla_event(r)
        apply_tier_quota(rows, cfg.ml_high_quota)       # kuota HIGH-ML per bangsal (lantai aturan dikecualikan)
        bulk_update(rows, scores)                       # satu UPDATE batch
        release_expired_claims(now)
    publish_diffs(changed_rows)                         # SSE

def next_for(user, scope):
    with tx(immediate=True):
        e = select_top_unclaimed(scope, order=(tier_rank, priority_score, admitted_at, encounter_id))
        if e: claim(e, user, ttl=15*60)
        return e
```

### 6.4 Target performa (usulan) pada 5.000 entri terbuka

| Operasi | Target P95 |
| :--- | :-: |
| `GET /queue` (50 baris) | < 300 ms |
| `POST /queue/next` | < 200 ms (tanpa kolisi ganda) |
| Tick batch | < 800 ms |
| Latensi event → UI (SSE) | < 2 dtk |
| Admit (ingest + skor Fase A) | < 500 ms |
| Pengguna serentak | 50 (apoteker + TTK + koordinator) |
| Laju event | 60/menit (puncak) |

### 6.5 Basis data
- **Demo:** SQLite WAL dengan transaksi pendek (cukup untuk simulator skala S/M).
- **Pilot/produksi:** **PostgreSQL** (wajib untuk banyak penulis serentak; `SKIP LOCKED`, indeks parsial). Alembic menjaga dua dialek.
- **Redis (opsional, P2):** `ZSET` untuk antrean sangat besar / multi-RS; bukan syarat awal.

### 6.6 Ketahanan
- Idempotensi ingest (kunci `encounter_id` + `event_id`), urutan event tidak terjamin → gunakan versi/cap waktu dan abaikan event usang.
- *Dead-letter* untuk event gagal diproses; tampil di dasbor admin.
- Antrean tetap berfungsi bila ML gagal (urut berdasarkan aturan + SLA + usia) — banner "ML tidak tersedia".
- Kebijakan saat sistem mati: formulir kertas + entri susulan; indikator "data tertinggal sejak …".

---

## 7. UI/UX UNTUK ANTREAN BESAR

| Elemen | Spesifikasi | Prio |
| :--- | :--- | :-: |
| **Tombol "Ambil pasien berikutnya"** (utama) | Satu klik → langsung ke Case Workspace pasien teratas yang sesuai cakupan; tampil "mengapa dia?" (alasan prioritas) | P0 |
| **Antrean Saya** | ±10 kasus: yang sedang saya tangani, klaim saya, dan 5 berikutnya; indikator lease | P0 |
| **Antrean Bangsal** | Tabel server-side, **virtualisasi baris** (TanStack Virtual), filter tier/status/bangsal, pencarian, kursor | P0 |
| **Aging strip** | Bilah warna distribusi usia menunggu per tier (0–25–50–75–100% SLA) | P0 |
| **Banner pembaruan** | "12 pembaruan baru — Muat ulang urutan" (baris tidak melompat) | P0 |
| **Badge sumber tier** | "HIGH (aturan)" / "HIGH (ML)" / "MED (SLA)" + persentil | P0 |
| **Tampilan Koordinator — Command Center** | Permintaan vs kapasitas (gauge), peta panas bangsal × tier, histogram usia, daftar berisiko SLA, status mode lonjakan, tombol alihkan/bantu | P0 (dasar) / P1 |
| **Aksi massal aman** | Pilih beberapa kasus Level 1 → konfirmasi massal (setelah disetujui klinis), dengan ringkasan & spot-check | P1 |
| **Serah terima shift** | Halaman/laporan: HIGH terbuka, klaim belum selesai, menunggu DPJP, berisiko SLA; ekspor PDF/CPPT | P1 |
| **Tampilan tersimpan** | Filter favorit ("Penyakit Dalam – HIGH – belum diklaim") | P1 |
| **Mode TV/Papan** | Layar besar di ruang farmasi: ringkasan antrean per bangsal & jam SLA | P2 |
| **Penanda realistis** | Jam server, "diperbarui X dtk lalu", status koneksi SSE | P0 |

**Aturan UX skala:** tidak ada tabel tanpa paginasi/virtualisasi; semua penyaringan di server; keyboard-first (`N` = ambil berikutnya, `J/K`, `/` cari); warna + ikon + teks; setiap angka (mis. "Backlog 143") dapat diklik menuju daftar yang menyusunnya.

---

## 8. MANAJEMEN KAPASITAS & OPERASIONAL

### 8.1 Model kapasitas (konfigurasi di Admin)
```text
kapasitas_menit(shift) = Σ apoteker_bertugas × menit_shift × persen_produktif   (default 60%)
permintaan_menit       = Σ entri_terbuka × menit_telaah(tier/level)             (default 30/20/8)
rasio_beban            = permintaan_menit / kapasitas_menit
```
- **Prakiraan 4 jam:** kedatangan diprakirakan dari rata-rata jam-per-hari (7–14 hari terakhir) + backlog saat ini ⇒ "Beban 1,4× kapasitas; butuh +2,5 jam apoteker."
- **Rekomendasi (bukan perintah):** tambah apoteker floating, aktifkan overflow, pertimbangkan Level 1.
- **Eskalasi bertingkat:** apoteker → koordinator (SLA HIGH hampir lewat) → kepala instalasi (backlog melewati ambang X jam) — semua tercatat.

### 8.2 Jam dinas & shift
- Pewaktu SLA 24/7 (default) dengan opsi "hanya jam dinas" per bangsal; kapasitas malam/akhir pekan dapat berbeda.
- Pergantian shift memicu: pelepasan klaim, laporan serah terima, perhitungan ulang kapasitas.

### 8.3 Indikator keselamatan antrean (lebih penting dari "kecepatan")
| Indikator | Arti | Target usulan |
| :--- | :--- | :-: |
| **Missed reconciliation rate** | % pasien pulang tanpa rekonsiliasi selesai | → 0; pantau tren |
| **HIGH ditelaah ≤ SLA** | Kepatuhan HIGH | ≥ 95% |
| **Usia menunggu p50/p90/p99** per tier | Distribusi, bukan rata-rata | p90 < SLA |
| **Backlog & WIP** | Jumlah terbuka per antrean/bangsal | Tren terkendali |
| **Throughput per apoteker-jam** | Produktivitas | Dilaporkan, bukan alat evaluasi individu |
| **Klaim kedaluwarsa** | Kasus "menggantung" | < 5% |
| **Re-triage per hari** | Kestabilan | Dipantau |
| **Variasi tunggu antar-bangsal** | Keadilan | Dipantau |
| **Proporsi HIGH (aturan vs ML)** | Kesehatan kuota | HIGH-ML ≤ Q% |
| **Cumulative Flow Diagram** | Aliran Admit → BPMH → Telaah → Selesai | Tampil di Command Center |

---

## 9. HOSPITAL SIMULATOR — "LIVE HOSPITAL MODE"

Tujuan: **antrean terlihat hidup dan realistis saat demo**, serta bahan uji beban/properti. Simulator **memanggil API asli** (bukan data palsu di UI), sehingga seluruh sistem (auth, antrean, SLA, SSE, audit, Langflow) benar-benar terpakai.

### 9.1 Komponen
| Komponen | Perilaku |
| :--- | :--- |
| **Generator kedatangan** | Proses Poisson tak homogen: laju λ(jam) per hari-dalam-pekan; puncak IGD sore–malam; Senin pagi lebih ramai |
| **Profil pasien** | Dari Synthea/seed: usia (condong lansia di Penyakit Dalam), komorbid, jumlah obat rutin, alergi (sebagian tidak tercatat), high-alert |
| **Agen TTK** | Mengisi BPMH dengan waktu lognormal (median ±45 mnt), sebagian BPMH tidak lengkap/terlambat, nama dagang & ejaan bervariasi |
| **Agen apoteker** | Mengambil "berikutnya", waktu telaah lognormal per tier, kadang meninggalkan klaim (menguji lease), jadwal shift & istirahat |
| **Agen DPJP** | Latensi konfirmasi acak (menguji `MENUNGGU_DPJP`) |
| **Peristiwa acak** | Transfer (±3%), lab kritis (±2%), pulang sebelum telaah (±5%), batal admisi (±1%), duplikasi (±0,5%), koreksi data |
| **Kejadian khusus (skenario)** | *Lonjakan IGD malam*, *kekurangan staf*, *flu musiman* (kedatangan ×2), *gangguan LLM/Langflow*, *ML mati* |
| **Jam virtual** | Percepatan 1×–240× (mis. 60× → 1 jam RS = 1 menit demo); dapat dijeda |

### 9.2 Ukuran data awal (seed) dan mode
| Ukuran | RS setara (asumsi) | Entri terbuka awal | Riwayat selesai | Apoteker/hari | Untuk |
| :-: | :-: | :-: | :-: | :-: | :--- |
| **S** | ±250 tt, backlog ringan | 80 | 400 | 3 | Demo cepat |
| **M** | ±500 tt, backlog sedang | 300 | 4.000 | 6 (3/2/1 per shift) | Demo utama / uji integrasi |
| **L** | backlog parah | 2.000 | 20.000 | 12 | Uji beban |
| **XL** | stres ekstrem / multi-RS | 5.000 | 50.000 | 20 | Uji stres |

*Catatan:* untuk RS ±500 tempat tidur, kedatangan stabil hanya ±75/hari (§2.1). Entri terbuka awal 300 pada ukuran M sengaja mewakili **backlog sedang** (±4 hari kedatangan) agar antrean terlihat padat dan fitur lonjakan/aging dapat didemokan; ukuran L dan XL adalah **skenario stres**, bukan kondisi normal.
Perintah (usulan): `python -m simulator.run --size M --speed 60 --scenario evening_surge --seed 42`. Seed menjamin **reprodusibel**.

### 9.3 Kejujuran presentasi
Tampilkan label permanen **"Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS"** di UI mode simulasi. Jangan menyebut angka simulasi sebagai hasil RS nyata. Pada pilot, kalibrasi parameter λ(jam), ALOS, waktu BPMH, dan waktu telaah dengan data RS mitra.

### 9.4 Skenario demo antrean (±60–90 detik, jam 60×)
1. Antrean M berjalan; Command Center menunjukkan beban 0,9× kapasitas.
2. Skenario **lonjakan IGD** dipicu: kedatangan naik, beban → 1,4×, **mode lonjakan** menyala, rekomendasi +2,5 jam apoteker.
3. Apoteker menekan **"Ambil berikutnya"**: kasus HIGH (aturan) teratas, "mengapa" tampil.
4. Kasus LOW yang lama menunggu **naik ke MEDIUM** otomatis (aging) + notifikasi.
5. Pasien dengan rencana pulang mendekat melonjak naik; satu pasien pulang sebelum telaah → tercatat *missed reconciliation* + muncul di laporan.
6. Matikan Langflow: antrean **tetap bergerak** (jalur antrean bebas Langflow); analisis kasus memakai mode cadangan.

---

## 10. REALISME: CEKLIS "TERLIHAT DAN BENAR-BENAR REALISTIS"

| Aspek | Kurang realistis | Realistis (target) |
| :--- | :--- | :--- |
| Jumlah | 10 pasien statis | 80–5.000 entri terbuka, bergerak |
| Pengambilan kerja | Gulir daftar | **Pull "Ambil berikutnya"** + klaim + lease |
| Pergerakan | Data tetap | Kedatangan, pulang, transfer, lab, shift, SLA tick |
| Kapasitas | Tidak ada | Permintaan vs kapasitas, mode lonjakan |
| Keadilan | Tidak ada | Aging, kuota, overflow antar-bangsal |
| Konkurensi | Satu pengguna | Banyak apoteker; tidak ada pasien ganda |
| Keselamatan | Tidak diukur | *Missed reconciliation*, kepatuhan SLA HIGH |
| Kegagalan | Diabaikan | ML/LLM/Langflow mati ≠ antrean mati |
| Data | Bersih | Nama dagang, alergi hilang, BPMH tidak lengkap, duplikasi |
| Peran | Satu | Apoteker, TTK, Koordinator, Admin |
| Serah terima | Tidak ada | Laporan shift |
| Integrasi | Tidak ada | Kontrak ADT/FHIR (stub + simulator) |

**Pertanyaan yang pasti diajukan juri/kepala farmasi (siapkan jawaban):** *Bagaimana bila 300 pasien menumpuk? Apa yang terjadi pada pasien LOW? Bagaimana dua apoteker tidak mengambil pasien yang sama? Bagaimana jika pasien pulang sebelum direkonsiliasi? Siapa yang menanggung bila sistem salah mengurutkan?* → jawaban ada di §3–§8 dan prinsip aturan-tidak-turun.

---

## 11. PENGUJIAN ANTREAN

| Jenis | Isi | Gerbang |
| :--- | :--- | :--- |
| **Unit** | Rumus skor, kuota, histeresis, lantai aturan, discharge boost | Hijau |
| **Properti** (Hypothesis) | (1) tak ada entri dengan dua klaim; (2) lantai aturan HIGH tak pernah turun; (3) tier tidak turun tanpa event re-triage; (4) **tak ada starvation** (setiap entri OPEN mencapai HIGH/diklaim ≤ SLA maksimum); (5) urutan deterministik untuk input sama; (6) `queue_version` monoton | 1.000+ kasus acak lulus |
| **Konkurensi** | 20 "apoteker" menekan *next* serentak pada 200 entri → tak ada duplikat, tak ada yang terlewat | 0 pelanggaran |
| **Integrasi event** | Urutan terbalik/duplikat/hilang (admit, transfer, discharge) → idempoten & konsisten | Lulus |
| **Beban** (k6/Locust) | Ukuran L & XL, 50 pengguna, 60 event/mnt, target §6.4 | Target tercapai |
| **Ketahanan (soak)** | Simulator 24 jam-virtual @120× (±12 mnt) tanpa kebocoran memori/entri yatim | Stabil |
| **Degradasi** | ML/LLM/Langflow mati → antrean tetap berfungsi | Lulus |
| **E2E** | Playwright: ambil berikutnya, lease kedaluwarsa, banner pembaruan, mode lonjakan | Hijau |
| **Kalibrasi kebijakan** | Jalankan simulasi untuk menyetel bobot & kuota (metrik: SLA HIGH, p90 tunggu, missed reconciliation) lalu bekukan versi | Dicatat di `DECISION_LOG` |

---

## 12. HUBUNGAN DENGAN LANGFLOW (JANGAN DICAMPUR-ADUK)

| Fungsi | Dijalankan di | Alasan |
| :--- | :--- | :--- |
| Skor Fase A massal, aging, kuota, SLA tick, klaim | **FastAPI + `priomedrec_core` (batch)** | Latensi, biaya, ribuan entri; deterministik |
| Analisis per kasus (Fase B, SBAR, guardrail) | **Langflow master flow** (jalur utama) → cadangan lokal | Dipanggil saat BPMH submit / kasus dibuka; bukan per kedatangan |
| Copilot: "Mengapa pasien ini nomor 3?", "Apa yang paling mendesak sekarang?" | **Flow 04** dengan tool baru `explain_queue_position(encounter_id)` & `summarize_my_queue(user)` (baca-saja) | Penjelasan, bukan penentuan urutan |
| Notifikasi event (opsional) | Webhook → Flow ringan (mis. ringkasan SLA breach) | Hanya narasi |
| Paritas | Fungsi skor Fase A di `01_admission_triage` memanggil fungsi **yang sama** dengan jalur batch | Uji paritas batch↔flow |
Prinsip: **tidak ada panggilan LLM per kedatangan pasien.** Antrean harus tetap bergerak walau Langflow/LLM mati.

---

## 13. BACKLOG ANTREAN

Ukuran: S ≤ 1 hari · M 2–4 hari · L 1–2 minggu.

| ID | Item | Ukuran | Prio |
| :-: | :--- | :-: | :-: |
| Q-001 | Tabel `queue_entries` (+ indeks, migrasi Alembic) & `queue_version` | M | P0 |
| Q-002 | `queue_engine` di `priomedrec_core`: skor, kuota HIGH-ML, aging, discharge boost, histeresis + uji unit/properti | L | P0 |
| Q-003 | Dua antrean (A: BPMH, B: Telaah) + transisi event | M | P0 |
| Q-004 | `GET /queue` (keyset), `POST /queue/next` (atomik), heartbeat/release, lease | L | P0 |
| Q-005 | Tick batch + `next_due_at` + `sla_events` + pembersihan klaim | M | P0 |
| Q-006 | SSE `/events/queue` (diff + `queue_version` + resync) | M | P0 |
| Q-007 | **Hospital Simulator** (kedatangan, TTK/apoteker/DPJP, event acak, jam virtual, seed S/M/L/XL, skenario) | L | P0 |
| Q-008 | Frontend: tombol Ambil berikutnya, Antrean Saya, Antrean Bangsal (virtualisasi), aging strip, banner pembaruan, badge sumber tier | L | P0 |
| Q-009 | Command Center dasar: backlog bangsal×tier, histogram usia, permintaan vs kapasitas, risiko SLA | L | P0 |
| Q-010 | Penanganan event: transfer, discharge, batal, duplikasi, lab kritis, koreksi (idempoten, urutan acak) | M | P0 |
| Q-011 | Metrik antrean (`/queue/metrics`) termasuk *missed reconciliation* | M | P0 |
| Q-012 | Uji beban L/XL + uji properti + uji konkurensi | M | P0 |
| Q-020 | Mode lonjakan + telaah bertingkat Level 1 (default OFF, butuh persetujuan klinis) + spot-check | L | P1 |
| Q-021 | Laporan serah terima shift (UI + PDF/CPPT) | M | P1 |
| Q-022 | Prakiraan kapasitas 4 jam + rekomendasi | M | P1 |
| Q-023 | Keadilan antar-bangsal & overflow | M | P1 |
| Q-024 | Jalur PostgreSQL (`SKIP LOCKED`) + uji lintas-DB | M | P1 |
| Q-025 | Adapter stub HL7 ADT / FHIR Subscription → event | L | P1 |
| Q-026 | Tampilan tersimpan & aksi massal aman | M | P1 |
| Q-027 | Tool Langflow `explain_queue_position`, `summarize_my_queue` + uji | S | P1 |
| Q-030 | Redis ZSET untuk skala sangat besar / multi-RS | L | P2 |
| Q-031 | Prakiraan kedatangan berbasis ML sederhana | M | P2 |
| Q-032 | Rekomendasi penugasan otomatis (saran, bukan perintah) | M | P2 |
| Q-033 | Mode TV/papan ruang farmasi | S | P2 |

**Urutan kritis:** Q-001 → Q-002 → Q-003 → Q-004/005 → Q-006 → Q-007 → Q-008 → Q-009 → Q-010/011 → Q-012.

---

## 14. KEPUTUSAN DEFAULT (TANPA PERLU DITANYA LAGI) & HAL YANG PERLU DIVALIDASI KLINIS

**Default:** dua antrean (A/B) · pull "Ambil berikutnya" dengan lease 15 mnt · skor & bobot §4.1 sebagai titik awal · kuota HIGH-ML 25% per bangsal · aging kontinu dihitung batch tiap 60 dtk · Level 1 (telaah ringan) **OFF** · mode lonjakan hanya memberi rekomendasi · SLA 24/7 · SQLite untuk demo, PostgreSQL untuk pilot · simulator ukuran M sebagai default demo.

**Wajib divalidasi apoteker/komite farmasi (S10):** (1) apakah Level 1/batch dapat diterima dan syarat spot-check-nya; (2) bobot skor & kuota; (3) menit telaah per tier; (4) ambang SLA; (5) definisi "missed reconciliation"; (6) aturan overflow antar-bangsal.

---

## LAMPIRAN A — SKEMA SQL ANTREAN (PostgreSQL; padanan SQLite via Alembic)

```sql
CREATE TABLE queue_entries (
  encounter_id    TEXT PRIMARY KEY REFERENCES encounters(id),
  queue_type      TEXT NOT NULL CHECK (queue_type IN ('BPMH','REVIEW')),
  ward            TEXT NOT NULL,
  state           TEXT NOT NULL CHECK (state IN ('OPEN','CLAIMED','PARKED_DPJP','CLOSED')),
  tier_rank       SMALLINT NOT NULL,            -- 2=HIGH 1=MED 0=LOW
  tier_source     TEXT NOT NULL,                -- RULE | ML | SLA
  priority_score  NUMERIC(6,2) NOT NULL,
  ml_percentile   NUMERIC(4,3),
  depth_level     SMALLINT NOT NULL DEFAULT 2,  -- 3 penuh, 2 standar, 1 ringan
  admitted_at     TIMESTAMPTZ NOT NULL,
  sla_due_at      TIMESTAMPTZ,
  next_due_at     TIMESTAMPTZ,                  -- ambang SLA berikutnya
  discharge_planned_at TIMESTAMPTZ,
  claimed_by      INT REFERENCES users(id),
  claim_expires_at TIMESTAMPTZ,
  queue_version   BIGINT NOT NULL,              -- naik pada setiap perubahan
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_q_list   ON queue_entries (queue_type, ward, state, tier_rank DESC, priority_score DESC, encounter_id);
CREATE INDEX ix_q_due    ON queue_entries (next_due_at) WHERE state IN ('OPEN','CLAIMED');
CREATE INDEX ix_q_claim  ON queue_entries (claimed_by, claim_expires_at) WHERE claimed_by IS NOT NULL;

CREATE TABLE queue_events (        -- jejak untuk diff SSE & audit operasional
  seq BIGSERIAL PRIMARY KEY, encounter_id TEXT NOT NULL, kind TEXT NOT NULL,   -- upsert|remove|claim|release|promote
  payload JSONB NOT NULL, at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE missed_reconciliations (
  encounter_id TEXT PRIMARY KEY, discharged_at TIMESTAMPTZ NOT NULL,
  last_state TEXT, last_tier TEXT, reason TEXT
);

-- Ambil berikutnya (PostgreSQL)
-- WITH c AS (
--   SELECT encounter_id FROM queue_entries
--   WHERE queue_type='REVIEW' AND state='OPEN' AND ward = ANY(:scope)
--   ORDER BY tier_rank DESC, priority_score DESC, admitted_at, encounter_id
--   FOR UPDATE SKIP LOCKED LIMIT 1)
-- UPDATE queue_entries q SET state='CLAIMED', claimed_by=:uid,
--        claim_expires_at=now()+interval '15 minutes', queue_version=nextval('queue_ver_seq')
-- FROM c WHERE q.encounter_id=c.encounter_id RETURNING q.*;
```

## LAMPIRAN B — KONFIGURASI SIMULATOR (CONTOH)

```yaml
seed: 42
size: M
clock: {speed: 60, start: "2026-11-02T06:00:00+07:00"}
wards:
  - {name: "Penyakit Dalam", beds: 200, bor: 0.78, alos_days: {dist: lognormal, median: 5.0, sigma: 0.5}, age_mean: 63}
  - {name: "Bedah",          beds: 140, bor: 0.72, alos_days: {dist: lognormal, median: 4.0, sigma: 0.5}, age_mean: 52}
  - {name: "Jantung",        beds: 80, bor: 0.80, alos_days: {dist: lognormal, median: 4.5, sigma: 0.4}, age_mean: 62}
  - {name: "Saraf",          beds: 80, bor: 0.75, alos_days: {dist: lognormal, median: 6.0, sigma: 0.5}, age_mean: 60}
arrivals:
  hourly_profile: [0.3,0.2,0.2,0.2,0.3,0.4,0.6,0.8,1.0,1.0,1.0,0.9,0.9,0.9,1.0,1.1,1.3,1.5,1.6,1.5,1.2,0.9,0.6,0.4]  # relatif; puncak sore-malam (asumsi)
  weekday_factor: {Mon: 1.15, Tue: 1.0, Wed: 1.0, Thu: 1.0, Fri: 1.0, Sat: 0.85, Sun: 0.8}
bpmh: {median_minutes: 45, sigma: 0.6, incomplete_rate: 0.15, brand_name_rate: 0.30, missing_allergy_rate: 0.10}
pharmacists:
  shifts: {pagi: ["07:00","14:00",3], siang: ["14:00","21:00",2], malam: ["21:00","07:00",1]}
  service_minutes: {HIGH: {median: 30, sigma: 0.4}, MED: {median: 20, sigma: 0.4}, LOW: {median: 8, sigma: 0.4}}
  abandon_claim_rate: 0.03
dpjp_response_minutes: {median: 25, sigma: 0.8}
events: {transfer: 0.03, critical_lab: 0.02, discharge_before_review: 0.05, cancel: 0.01, duplicate: 0.005}
scenarios:
  evening_surge: {at: "17:00", arrivals_multiplier: 2.0, duration_hours: 4}
  staff_shortage: {shift: malam, pharmacists: 1}
  llm_outage: {at: "19:00", duration_minutes: 20}
label: "Data simulasi — parameter berbasis asumsi"
```

---
*Dokumen ini adalah delta atas rencana induk. Bila bertentangan, dokumen ini menang untuk topik **manajemen antrean**; aturan keselamatan klinis S1–S14 tetap berlaku penuh.*
