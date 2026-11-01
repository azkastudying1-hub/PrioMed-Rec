# ANTREAN TINJAUAN KLINIS — PrioMed-Rec
## Daftar Konten Klinis yang Menunggu Validasi Apoteker

**Versi:** 1.0
**Status dokumen:** AKTIF — tambahkan item baru saat konten klinis baru dibuat
**Proses validasi:** Apoteker klinis menelaah, menandatangani, dan memperbarui status setiap item

> **PERATURAN UTAMA (S10):** Setiap konten klinis yang dibuat oleh tim pengembang atau IBM Bob WAJIB dicatat di sini dengan status `DRAFT_PERLU_VALIDASI_APOTEKER` dan field `owner: "TBD-apoteker"`. Konten tidak boleh digunakan dalam demo klinis nyata sampai apoteker menyetujuinya.

---

## FORMAT ENTRI

```
### [CRQ-XXX] Nama Konten
- **Tipe:** aturan / alias / severity / golden_case / prompt / konfigurasi
- **File:** path/ke/file
- **Dibuat oleh:** IBM Bob / Pengembang / [nama]
- **Tanggal dibuat:** YYYY-MM-DD
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER | DALAM_REVIEW | DISETUJUI | DITOLAK
- **Owner:** TBD-apoteker / [nama apoteker klinis]
- **Deskripsi:** Apa isi kontennya
- **Risiko jika salah:** [dampak klinis]
- **Catatan reviewer:** (diisi apoteker saat review)
```

---

## BAGIAN 1: ATURAN KLINIS

### [CRQ-001] allergy_rules.json — Reaksi Silang Kelas Obat
- **Tipe:** aturan
- **File:** `configs/allergy_rules.json`
- **Dibuat oleh:** IBM Bob (Fase 1 - B-109)
- **Tanggal dibuat:** TBD (saat B-109 diimplementasikan)
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Owner:** TBD-apoteker
- **Deskripsi:** Aturan reaksi silang kelas obat berdasarkan alergi yang dilaporkan pasien. Mencakup: penisilin–sefalosporin (~1-2% cross-reactivity), sulfonamid, NSAID, kontras iodium, dll.
- **Risiko jika salah:** Alert palsu → alert fatigue; atau miss → reaksi alergi tidak terdeteksi
- **Catatan reviewer:** _(kosong — menunggu apoteker)_

### [CRQ-002] discrepancy_rules.json — Severity Tier 1/2/3
- **Tipe:** severity
- **File:** `configs/discrepancy_rules.json`
- **Dibuat oleh:** IBM Bob (Fase 1 - B-110)
- **Tanggal dibuat:** TBD (saat B-110 diimplementasikan)
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Owner:** TBD-apoteker
- **Deskripsi:**
  - Tier 1 (Kritis): omisi antikoagulan/insulin/antiepilepsi/kardiak; duplikasi antikoagulan; konflik alergi; interaksi mayor
  - Tier 2 (Signifikan): omisi antibiotik/antihipertensi non-kritis; interaksi moderat; Beers PIM
  - Tier 3 (Minor): omisi vitamin/suplemen; substitusi formularium
- **Risiko jika salah:** Over-escalation atau under-escalation prioritas; alert fatigue atau miss kritis
- **Catatan reviewer:** _(kosong — menunggu apoteker)_

### [CRQ-003] High-Alert Drug List Indonesia
- **Tipe:** konfigurasi
- **File:** `configs/discrepancy_rules.json` + tabel `local_high_alert`
- **Dibuat oleh:** IBM Bob (berdasarkan ISMP High-Alert + adaptasi Indonesia)
- **Tanggal dibuat:** TBD
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Owner:** TBD-apoteker
- **Deskripsi:** Daftar obat high-alert yang memicu hard stop konfirmasi. Basis: ISMP High-Alert Medications list + adaptasi untuk formularium RS Indonesia (insulin, heparin, warfarin, elektrolit pekat, kemoterapi, opioid, NMB agent, dll.)
- **Risiko jika salah:** Hard stop terlalu sering (alert fatigue) atau terlewat (keselamatan pasien)
- **Catatan reviewer:** _(kosong — menunggu apoteker)_

---

## BAGIAN 2: TABEL ALIAS OBAT

### [CRQ-010] drug_alias.csv — Merek Dagang Indonesia ke Generik (≥200 entri)
- **Tipe:** alias
- **File:** `knowledge/drug_alias.csv`
- **Dibuat oleh:** IBM Bob (Fase 1 - B-111)
- **Tanggal dibuat:** TBD (saat B-111 diimplementasikan)
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Owner:** TBD-apoteker
- **Deskripsi:** Tabel pemetaan nama merek dagang umum Indonesia ke nama generik internasional. Contoh: Plavix→clopidogrel, Amaryl→glimepiride, Lovenox/Clexane→enoxaparin, Concor→bisoprolol, dll.
- **Risiko jika salah:** Pemetaan salah menyembunyikan diskrepansi atau menciptakan false positive omisi
- **Catatan reviewer:** _(kosong — menunggu apoteker)_
- **Panduan review:**
  - Verifikasi bahwa setiap pemetaan generik sudah benar
  - Tandai alias yang ambigu (satu merek untuk beberapa generik)
  - Tambahkan alias yang hilang dari praktik RS lokal

### [CRQ-011] Pemetaan Kode ATC untuk Kelas Obat
- **Tipe:** alias
- **File:** `configs/drug_class_map.json`
- **Dibuat oleh:** Tim pengembang (sudah ada di repo)
- **Tanggal dibuat:** 2025
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Owner:** TBD-apoteker
- **Deskripsi:** Pemetaan kode ATC ke nama kelas obat untuk deteksi duplikasi terapeutik
- **Risiko jika salah:** Duplikasi tidak terdeteksi atau false positive duplikasi

---

## BAGIAN 3: GOLDEN CLINICAL TEST SET (Kerangka)

> Setiap kasus di bawah memerlukan apoteker klinis untuk menetapkan expected output (findings, tier, keputusan yang benar).

### [CRQ-020] Golden Case S1 — Polifarmasi + Omisi Antikoagulan + High-Alert
- **Tipe:** golden_case
- **File:** `tests/golden/s1_elderly_warfarin_omission.yaml`
- **Dibuat oleh:** IBM Bob (kerangka)
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Deskripsi:** Tn. Ahmad 72 th, polifarmasi 9 obat, warfarin di BPMH tidak ada di order admisi, order ada Clexane + aspirin
- **Expected output (DRAFT):** Tier HIGH; omisi warfarin Tier-1; duplikasi antikoagulan; hard stop high-alert warfarin+Clexane
- **Apoteker perlu konfirmasi:** Apakah omisi warfarin dalam kasus ini benar Tier-1? Apakah kombinasi Clexane+aspirin merupakan duplikasi atau terapi intentional?

### [CRQ-021] Golden Case S2 — Disposisi Sah (Tidak Ada False Positive)
- **Tipe:** golden_case
- **File:** `tests/golden/s2_metformin_hold.yaml`
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Deskripsi:** Ny. Siti 58 th, metformin DITUNDA karena prosedur kontras, insulin geser baru
- **Expected output (DRAFT):** Tidak ada false omisi (disposisi TUNDA sah); peringatan insulin (high-alert)
- **Apoteker perlu konfirmasi:** Apakah sistem benar tidak melaporkan omisi metformin jika disposisi = DITUNDA?

### [CRQ-022] Golden Case S3 — SLA Eskalasi LOW→MEDIUM
- **Tipe:** golden_case
- **File:** `tests/golden/s3_sla_escalation.yaml`
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Deskripsi:** Tn. Budi 34 th, LOW priority, tidak ditelaah 13 jam
- **Expected output (DRAFT):** Status naik ke MEDIUM; priority_reason mencatat "SLA: >12 jam"

### [CRQ-023] Golden Case S9 — Merek Dagang → Normalisasi
- **Tipe:** golden_case
- **File:** `tests/golden/s9_brand_normalization.yaml`
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Deskripsi:** BPMH memuat "Plavix 75mg" dan "Amaryl 2mg"
- **Expected output (DRAFT):** Dinormalisasi ke clopidogrel 75mg dan glimepiride 2mg; ditandai "dipetakan otomatis — verifikasi"

### [CRQ-024..059] Golden Cases 4–40 (Kerangka Belum Diisi)
- **Status:** BUTUH INPUT APOTEKER
- **Kasus yang dibutuhkan:** (lihat Bagian 13.2 dokumen strategi)
  - Omisi sah vs tidak sah berbagai kelas obat
  - Duplikasi intensional (terapeutik) vs tidak
  - Alergi silang kelas
  - Merek dagang kompleks
  - High-alert berbagai kategori
  - Pasien "tidak minum obat rutin"
  - Kasus adversarial untuk LLM (obat fiktif, instruksi tersembunyi)

---

## BAGIAN 4: PROMPT SBAR

### [CRQ-070] prompts/sbar_v1.md — Template Prompt SBAR
- **Tipe:** prompt
- **File:** `prompts/sbar_v1.md`
- **Dibuat oleh:** IBM Bob (Fase 3 - A-309)
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Owner:** TBD-apoteker
- **Deskripsi:** System prompt untuk menghasilkan narasi SBAR dari data terstruktur. Berdasarkan Lampiran C dokumen strategi.
- **Risiko jika salah:** LLM menghasilkan SBAR yang menyesatkan atau mengandung instruksi terapi
- **Panduan review:** Pastikan bahwa SBAR yang dihasilkan: (1) menggunakan istilah klinis baku Indonesia, (2) tidak mengandung saran dosis otonom, (3) selalu merujuk ID temuan dari rule engine

### [CRQ-071] prompts/copilot_v1.md — Template Prompt Copilot
- **Tipe:** prompt
- **File:** `prompts/copilot_v1.md`
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER

---

## BAGIAN 5: KONFIGURASI SLA

### [CRQ-080] SLA Default (HIGH ≤ 4 jam, MEDIUM ≤ 12 jam, LOW ≤ 24 jam)
- **Tipe:** konfigurasi
- **File:** tabel `sla_config` + default di `api/services/sla_service.py`
- **Dibuat oleh:** IBM Bob (berdasarkan Bagian 5.3 dokumen strategi + QUEUE_PLAN §D4)
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Owner:** TBD-apoteker (Kepala Instalasi Farmasi)
- **Deskripsi:** Konfigurasi SLA awal: HIGH ≤ 4 jam (warning 2 jam), MEDIUM ≤ 12 jam (warning 6 jam), LOW ≤ 24 jam (warning 12 jam)
- **Risiko jika salah:** Eskalasi terlalu cepat (gangguan kerja) atau terlalu lambat (pasien terlewat)
- **Panduan review:** Sesuaikan dengan kebijakan RS mitra dan standar akreditasi SNARS/KARS

---

## BAGIAN 6: KEBIJAKAN ANTREAN (FASE Q0) — MEMERLUKAN VALIDASI

> Semua item di bagian ini perlu keputusan dari apoteker klinis/komite farmasi sebelum go-live.
> Tidak memblokir implementasi teknis fase Q1–Q3, tetapi wajib diselesaikan sebelum pilot.

### [CRQ-090] Bobot Skor Prioritas Komposit
- **Tipe:** konfigurasi
- **File:** `priomedrec_core/queue_config.py` (belum ada, Q-002)
- **Dibuat oleh:** IBM Bob (§4.1 QUEUE_MANAGEMENT_PLAN)
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Owner:** TBD-apoteker
- **Deskripsi:** Bobot skor: sla_pressure=0.40, ml_percentile=0.25, severity_load=0.15, discharge_pressure=0.10, wait_norm=0.10.
  Pertanyaan klinis: "Apakah 40% bobot ke SLA sudah tepat dibanding 25% ke ML? Atau urgensi klinis (severity) seharusnya lebih besar?"
- **Risiko jika salah:** Urutan tidak mencerminkan prioritas klinis sesungguhnya
- **Panduan review:** Uji bobot dengan kasus nyata; bandingkan urutan yang dihasilkan dengan intuisi klinis apoteker senior

### [CRQ-091] Kuota HIGH-ML 25% per Bangsal
- **Tipe:** konfigurasi
- **File:** `priomedrec_core/queue_config.py` (belum ada, Q-002)
- **Dibuat oleh:** IBM Bob (§4.2 QUEUE_MANAGEMENT_PLAN)
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Owner:** TBD-apoteker
- **Deskripsi:** Entri yang naik HIGH hanya karena ML dibatasi ≤ 25% antrean aktif per bangsal. HIGH karena aturan klinis tidak dikuota.
  Pertanyaan: "Apakah 25% sudah tepat? Apakah kuota per bangsal atau per shift?"
- **Risiko jika salah:** Terlalu ketat → kasus berisiko ML tertunda; terlalu longgar → HIGH kehilangan makna

### [CRQ-092] Menit Telaah per Tier (Kapasitas)
- **Tipe:** konfigurasi
- **File:** Command Center config (Q-009)
- **Dibuat oleh:** IBM Bob (§2.2 QUEUE_MANAGEMENT_PLAN, asumsi)
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Owner:** TBD-apoteker
- **Deskripsi:** HIGH=30 mnt, MEDIUM=20 mnt, LOW=8 mnt per pasien. Dipakai untuk hitung permintaan vs kapasitas.
- **Risiko jika salah:** Prakiraan kapasitas tidak akurat → rekomendasi penambahan staf keliru

### [CRQ-093] Level 1 — Telaah Ringan/Batch untuk LOW Tanpa Temuan
- **Tipe:** kebijakan klinis
- **File:** tidak ada (default OFF, Q-020)
- **Dibuat oleh:** IBM Bob (§3.4 QUEUE_MANAGEMENT_PLAN)
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Owner:** TBD-apoteker (Komite Farmasi)
- **Deskripsi:** Level 1 memungkinkan konfirmasi massal "tidak ada temuan yang perlu ditindaklanjuti" untuk pasien LOW tanpa
  temuan Tier-1/2, BPMH lengkap, tanpa high-alert, tanpa konflik alergi. Dengan spot-check acak ≥10%.
  **DEFAULT OFF** sampai disetujui komite farmasi.
- **Risiko jika salah:** Pasien berisiko tidak mendapat telaah penuh; dapat melanggar standar akreditasi
- **Panduan review:** Apakah komite farmasi RS menyetujui Level 1? Berapa persen spot-check? Apakah perlu tanda tangan apoteker per batch?

### [CRQ-094] Definisi "Missed Reconciliation"
- **Tipe:** kebijakan klinis
- **File:** `api/db/models.py` `MissedReconciliation` (belum ada, Q-001)
- **Dibuat oleh:** IBM Bob (§8.3 QUEUE_MANAGEMENT_PLAN, Q7)
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Owner:** TBD-apoteker
- **Deskripsi:** Apakah "missed reconciliation" hanya mencakup DISCHARGE sebelum workflow_status = SELESAI_*?
  Atau juga mencakup: BPMH tidak terisi sebelum discharge? Transfer tanpa serah terima telaah?
- **Risiko jika salah:** Indikator keselamatan tidak akurat; missed case tidak terlaporkan

### [CRQ-095] Aturan Overflow Antar-Bangsal
- **Tipe:** kebijakan operasional
- **File:** `priomedrec_core/queue_engine.py` (belum ada, Q-002)
- **Dibuat oleh:** IBM Bob (§3.3 QUEUE_MANAGEMENT_PLAN)
- **Status:** DRAFT_PERLU_VALIDASI_APOTEKER
- **Owner:** TBD-Koordinator Farmasi
- **Deskripsi:** Kapan kasus bangsal X boleh dikerjakan apoteker bangsal Y (overflow)?
  Ambang default: HIGH yang mendekati SLA + bangsal tetangga tersedia.
- **Risiko jika salah:** Apoteker lintas-bangsal tidak familiar dengan konteks klinis bangsal lain

---

## STATUS RINGKASAN

| Kategori | Total item | DRAFT | Dalam Review | Disetujui |
|:---|:--:|:--:|:--:|:--:|
| Aturan klinis | 3 | 3 | 0 | 0 |
| Alias obat | 2 | 2 | 0 | 0 |
| Golden test cases | 40 | 40 | 0 | 0 |
| Prompt | 2 | 2 | 0 | 0 |
| Konfigurasi SLA | 1 | 1 | 0 | 0 |
| **Kebijakan antrean (Q0)** | **6** | **6** | **0** | **0** |
| **Total** | **54** | **54** | **0** | **0** |

> **Catatan:** Tidak ada satu pun konten klinis yang disetujui pada saat ini. Semua masih DRAFT. Ini normal untuk tahap Fase 0 / Q0.

---

## PANDUAN UNTUK APOTEKER REVIEWER

Saat Anda menelaah item di atas:
1. Baca deskripsi dan risiko
2. Periksa file yang disebutkan
3. Tulis catatan di field "Catatan reviewer"
4. Ubah status ke DALAM_REVIEW atau DISETUJUI atau DITOLAK
5. Isi field owner dengan nama Anda
6. Buat PR dengan perubahan atau hubungi tim pengembang

Untuk pertanyaan: hubungi tim pengembang PrioMed-Rec.
