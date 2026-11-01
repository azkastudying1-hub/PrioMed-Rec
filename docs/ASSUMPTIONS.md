# ASUMSI & KEPUTUSAN TERBUKA — PrioMed-Rec
## Dokumen Asumsi Fase 0

**Versi:** 1.0
**Tanggal:** Fase 0 (sesi ini)
**Dibuat oleh:** IBM Bob (Fase 0 Audit)
**Status:** AKTIF — perbarui setiap kali asumsi baru dibuat atau diubah

> Dokumen ini mencatat semua asumsi yang dibuat karena tidak ada keputusan eksplisit dari tim atau klinis, serta jawaban atas 10 Keputusan Terbuka (Bagian 18 dokumen strategi). Semua asumsi dapat diubah lewat entri baru di sini dan di `docs/DECISION_LOG.md`.

---

## BAGIAN A: KEPUTUSAN TERBUKA K1–K10 (Bagian 18 dokumen strategi)

### K1 — Tahap yang dikejar
**Keputusan:** DEMO-READY (Fase 0–3). PILOT hanya disiapkan sebagai peta jalan & stub (tidak wajib selesai sebelum hackathon).
**Implikasi:** Item bertanda [PILOT] P1 tidak wajib selesai. Fokus pada 37 item P0 DEMO.

### K2 — Pengguna demo
**Keputusan:** Apoteker Klinis sebagai pengguna utama; TTK untuk pengisian BPMH (peran TECHNICIAN).
**Implikasi:** Alur demo mengikuti perspektif apoteker. RBAC TECHNICIAN ada tapi peran COORDINATOR/ADMIN/AUDITOR bisa distub.

### K3 — Mitra klinis
**Keputusan:** Belum ada mitra klinis. Semua konten klinis = `"status": "DRAFT_PERLU_VALIDASI_APOTEKER"`. Golden set dibuat sebagai kerangka + 40 kasus draf yang menunggu penetapan apoteker.
**Implikasi:** Tidak ada konten klinis yang dapat diklaim sebagai "tervalidasi" sebelum ada apoteker yang menyetujuinya. Semua aturan, alias, dan kasus uji harus ditandai DRAFT.

### K4 — SLA: jam operasional
**Keputusan:** 24/7 sebagai default. Opsi "hanya jam dinas" tersedia di pengaturan Admin (default OFF).
**Implikasi:** Scheduler SLA berjalan 24/7. Jika Admin mengaktifkan opsi jam dinas, pewaktu dipause di luar jam dinas.

### K5 — Discharge Gatekeeper v1
**Keputusan:** Hanya "cek + banner + API" (tanpa memblokir SIMRS). `GET /discharge/{enc}/check` mengembalikan status boleh/tertahan + alasan.
**Implikasi:** Tidak perlu integrasi SIMRS untuk demo. UI menampilkan banner peringatan.

### K6 — LLM: rantai fallback
**Keputusan:** Urutan berbasis konfigurasi (.env): gemini → groq → watsonx (jika kredensial ada) → ollama (jika tersedia) → template deterministik. Nama model TIDAK di-hardcode. Health check berkala.
**Implikasi:** LLM service sudah mendukung Gemini+Groq. Perlu tambahkan: watsonx.ai (opsional), Ollama (opsional), health check proaktif.

### K7 — Bahasa SBAR
**Keputusan:** Indonesia dengan istilah klinis baku (misalnya: "Situasi", "Latar Belakang", "Penilaian", "Rekomendasi"; nama obat dalam generik Indonesia/internasional).
**Implikasi:** Guardrail #8 mendeteksi instruksi dalam bahasa Indonesia DAN Inggris.

### K8 — DDI (Drug-Drug Interaction) knowledge
**Keputusan:** Pakai `knowledge/interactions.json` terkurasi untuk demo; sediakan adapter DDInter CSV (nonaktif) + catatan "periksa lisensi sebelum dipakai".
**Implikasi:** Tidak perlu lisensi DDInter untuk demo. Adapter DDInter dibuat sebagai placeholder.

### K9 — Target label ML
**Keputusan:** Untuk demo tetap L1 (`has_discrepancy` dari rule engine) dengan dokumentasi keterbatasan yang jujur. Bangun kerangka evaluasi L2 (diskrepansi signifikan) untuk shadow test.
**Implikasi:** MODEL_CARD harus mencantumkan keterbatasan label sintetis secara eksplisit (sudah ada ✅). Tidak ada reklaim akurasi klinis.

### K10 — Pemilik aturan klinis
**Keputusan:** Field `owner` per kelompok aturan diisi "TBD-apoteker". Setiap aturan klinis baru wajib mencantumkan `"status": "DRAFT_PERLU_VALIDASI_APOTEKER"` dan `"owner": "TBD-apoteker"`.
**Implikasi:** Semua konten di `configs/allergy_rules.json`, `configs/discrepancy_rules.json`, dan `knowledge/drug_alias.csv` yang dibuat dalam proyek ini adalah DRAFT.

---

## BAGIAN B: ASUMSI TEKNIS TAMBAHAN

### AT-01 — React versi
**Asumsi:** `package.json` menggunakan React ^19.0.0, bukan React 18 seperti disebutkan dokumen strategi. Kami mempertahankan React 19 karena sudah terpasang dan stabil. Jika ada library yang tidak kompatibel, downgrade ke 18 dengan mencatat di DECISION_LOG.
**Dampak risiko:** Rendah (React 19 backward-compatible untuk sebagian besar use case React 18).

### AT-02 — SQLite untuk demo
**Asumsi:** SQLite dipertahankan untuk fase demo. Migrasi ke PostgreSQL dilakukan di Fase 5 (PILOT). Semua SQL ditulis agar portabel (tidak menggunakan fitur SQLite-only yang tidak ada di PostgreSQL).
**Dampak risiko:** Sedang — konkurensi terbatas di SQLite, cukup untuk demo single-node.

### AT-03 — auth_service untuk endpoint lama
**Asumsi:** Endpoint lama (`/analyze`, `/prioritize`, `/discrepancies`, `/review`) dipertahankan dengan X-API-Key untuk kompatibilitas Langflow/MCP. Endpoint `/api/v1/*` baru menggunakan JWT.
**Dampak risiko:** Sedang — dua mekanisme auth bersamaan; harus didokumentasikan dan diuji.

### AT-04 — Trigger immutable audit
**Asumsi:** Implementasi trigger database untuk menolak UPDATE/DELETE di SQLite dilakukan via app-level guard (Python) karena SQLite trigger terbatas. Trigger database sebenarnya (PostgreSQL trigger) ditambahkan saat migrasi ke PostgreSQL di B-120.
**Dampak risiko:** Sedang — app-level guard bisa dilewati jika koneksi langsung ke DB. Catat di SECURITY.md.

### AT-05 — drug_alias.csv konten DRAFT
**Asumsi:** Tabel alias obat Indonesia yang dibuat (≥200 entri) adalah DRAFT berdasarkan pengetahuan umum tentang merek dagang Indonesia yang umum. WAJIB divalidasi apoteker sebelum digunakan klinis. Setiap baris ditandai `status: "DRAFT"`.
**Dampak risiko:** Tinggi (klinis) — normalisasi yang salah bisa menyembunyikan diskrepansi. Tandai confidence rendah.

### AT-06 — allergy_rules.json konten DRAFT
**Asumsi:** Reaksi silang kelas yang diimplementasikan (penisilin–sefalosporin, sulfa, NSAID, dll.) diambil dari referensi farmakologi standar internasional. Tetap DRAFT karena belum divalidasi apoteker klinis Indonesia.
**Dampak risiko:** Tinggi (klinis). False positive lebih baik dari false negative untuk keselamatan, tetapi alert fatigue tetap risiko.

### AT-07 — Skenario S1–S10 menggunakan data sintetis
**Asumsi:** Semua skenario demo (S1–S10) menggunakan data sintetis yang sepenuhnya fiktif. Nama pasien adalah nama generik Indonesia (Tn. Ahmad, Ny. Siti, dll.). Tidak ada PII.
**Dampak risiko:** Rendah (sudah terdokumentasi sebagai data sintetis).

### AT-08 — Kalibrasi model: pakai eval_report_v4 bukan v3
**Asumsi:** `models/eval_report_v4.json` mencerminkan hasil STAB-001 yang lebih baru dan lebih akurat (MACE < 0.010 setelah isotonic calibration). `eval_report_v3.json` adalah artefak antara. MODEL_CARD menggunakan angka dari STAB-001.
**Dampak risiko:** Rendah — perlu diverifikasi saat M-402.

### AT-09 — Wartsonx.ai opsional saja
**Asumsi:** Watsonx.ai diintegrasikan sebagai opsional (aktif hanya jika `LLM_WATSONX_*` env ada). Tidak wajib untuk demo. Jika tim memiliki akses IBM Cloud, tambahkan sebagai penyedia ke-3.
**Dampak risiko:** Rendah untuk demo; nilai tambah untuk narasi IBM SkillsBuild.

### AT-10 — CI/CD: GitHub Actions
**Asumsi:** CI/CD menggunakan GitHub Actions (karena repo kemungkinan di GitHub). Jika bukan GitHub, sesuaikan workflow file.
**Dampak risiko:** Rendah.

### AT-11 — `make` target menggunakan Python sebagai fallback
**Asumsi:** Jika `make` tidak tersedia (Windows), sediakan perintah Python alternatif: `python scripts/seed_demo.py` sebagai pengganti `make demo-reset`.
**Dampak risiko:** Rendah — target pengguna demo bisa di Linux/Mac/Windows.

### AT-12 — Discharge check tanpa integrasi SIMRS
**Asumsi:** Discharge check (B-117) hanya mengecek status internal PrioMed-Rec (kasus HIGH belum selesai, tier-1 terbuka). Tidak ada webhook ke SIMRS. Hanya banner UI + API.
**Dampak risiko:** Rendah untuk demo; fungsionalitas lengkap membutuhkan SIMRS (Fase 5).

---

## BAGIAN C: ASUMSI KLINIS (MEMBUTUHKAN KONFIRMASI APOTEKER)

> **PERINGATAN:** Semua asumsi klinis di bawah ini adalah pendapat teknis/engineering, BUKAN keputusan klinis. Wajib divalidasi oleh apoteker klinis bersertifikat sebelum digunakan.

| ID | Asumsi klinis | Risiko jika salah | Prioritas validasi |
|:---|:---|:---|:---|
| AK-01 | Omisi antikoagulan (warfarin, heparin, apixaban) selalu Tier 1 | Pasien tidak mendapat perhatian segera | TINGGI |
| AK-02 | Duplikasi antikoagulan selalu Tier 1 | Perdarahan tidak terdeteksi dini | TINGGI |
| AK-03 | Penisilin dan sefalosporin memiliki risiko reaksi silang ~1-2% | Alert palsu atau miss | TINGGI |
| AK-04 | Sulfonamid dan beberapa diuretik sulfa memiliki risiko silang | Alert palsu | SEDANG |
| AK-05 | Obat ISMP High-Alert: insulin, antikoagulan, kemoterapi, opioid, elektrolit konsentrat | Konfigurasi salah | TINGGI |
| AK-06 | SLA HIGH ≤ 4 jam, MEDIUM ≤ 12 jam, LOW ≤ 24 jam (sesuai standar akreditasi) | Eskalasi tidak tepat | SEDANG |

---

## BAGIAN D: ASUMSI ANTREAN (FASE Q0)

> Semua asumsi di bagian ini berdasarkan PRIOMEDREC_QUEUE_MANAGEMENT_PLAN.md §2–§4.
> Angka-angka adalah **asumsi awal, belum dikalibrasi dengan RS nyata**.

### AQ-01 — SLA Default Antrean
**Asumsi:** HIGH ≤ 4 jam (warning 2 jam), MEDIUM ≤ 12 jam (warning 6 jam), LOW ≤ 24 jam (warning 12 jam).
Berbeda dengan nilai di `sla_service.py` lama (HIGH=2j, MED=8j, LOW=24j) — dokumen QUEUE_PLAN §D4 menang karena lebih baru.
**Dampak risiko:** Sedang — apoteker perlu konfirmasi apakah 4 jam sudah tepat untuk RS mitra (CRQ-080).

### AQ-02 — Bobot Skor Prioritas Komposit
**Asumsi:** `w_sla=0.40, w_ml=0.25, w_severity=0.15, w_discharge=0.10, w_wait=0.10` (§4.1 QUEUE_PLAN).
Ini adalah **titik awal** yang akan dikalibrasi via simulator (Q-007) dan disimpan dalam konfigurasi berversi.
**Dampak risiko:** Sedang — bobot yang salah dapat menyebabkan urutan tidak optimal, tapi tidak melanggar lantai aturan klinis.

### AQ-03 — Kuota HIGH-ML 25% per bangsal
**Asumsi:** Entri yang naik HIGH hanya karena ML dibatasi ≤ 25% per bangsal (§4.2 QUEUE_PLAN).
HIGH karena aturan klinis (temuan Tier-1, high-alert, alergi) tidak dikuota.
**Dampak risiko:** Sedang — kuota terlalu ketat bisa menyebabkan kasus berisiko tinggi dikelompokkan MEDIUM.

### AQ-04 — Lease Klaim 15 Menit
**Asumsi:** Klaim kedaluwarsa setelah 15 menit tanpa heartbeat; entri kembali ke antrean dengan usia menunggu tetap.
**Dampak risiko:** Rendah — jika terlalu pendek, apoteker sering kehilangan klaim; jika terlalu panjang, kasus menggantung.

### AQ-05 — Menit Telaah per Tier
**Asumsi:** HIGH=30 mnt, MEDIUM=20 mnt, LOW=8 mnt (§2.2 QUEUE_PLAN, DRAFT).
Dipakai untuk kalkulasi kapasitas di Command Center.
**Dampak risiko:** Tinggi (klinis/operasional) — angka ini perlu divalidasi apoteker.

### AQ-06 — Simulator: Data Sintetis Semata
**Asumsi:** Semua data yang dihasilkan simulator adalah sintetis; label "Data simulasi — parameter berbasis asumsi,
belum dikalibrasi dengan RS" wajib tampil di semua output.
**Dampak risiko:** Rendah jika label konsisten; tinggi jika disalahartikan sebagai data RS nyata.

### AQ-07 — Level 1 (Telaah Ringan/Batch) Default OFF
**Asumsi:** Fitur Level 1 tidak aktif sampai disetujui komite farmasi (P1, bukan P0).
**Dampak risiko:** Tinggi jika diaktifkan tanpa persetujuan — bisa menyebabkan pasien berisiko tidak ditelaah penuh.

### AQ-08 — SQLite Cukup untuk Demo Ukuran S/M
**Asumsi:** Untuk simulator ukuran S (80 entri terbuka) dan M (300 entri terbuka), SQLite WAL cukup.
Ukuran L/XL memerlukan PostgreSQL (Q-024, P1).
**Dampak risiko:** Sedang — konkurensi SQLite terbatas; cukup untuk demo single-node, tidak untuk produksi.

---

## RIWAYAT PERUBAHAN

| Versi | Tanggal | Perubahan |
|:---|:---|:---|
| 1.0 | Fase 0 | Dibuat berdasarkan audit repo + keputusan K1–K10 |
| 2.0 | Fase Q0 | Tambah Bagian D: asumsi antrean AQ-01..AQ-08 |
