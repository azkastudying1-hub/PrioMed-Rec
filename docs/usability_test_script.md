# Skenario Pengujian Usability — PrioMed-Rec

**Target Pengguna:** Apoteker Klinis Rumah Sakit  
**Tujuan:** Memvalidasi bahwa alur kerja dua tahap, pengisian BPMH, dan telaah hasil analisis dapat diselesaikan secara intuitif, aman, dan efisien tanpa bergantung pada bantuan teknis.

---

## 1. Persiapan Sesi
- **Waktu:** ~30 menit per peserta
- **Metode:** *Think-Aloud Protocol* (peserta diminta mengungkapkan apa yang dipikirkan saat berinteraksi dengan aplikasi)
- **Lingkungan Uji:** Komputer bangsal / tablet klinis
- **Peran Fasilitator:** Netral, mengamati tanpa mengarahkan jawaban

---

## 2. Skenario Tugas (Task Scenarios)

### Tugas 1: Triase Worklist Pasien Baru Masuk
> *"Anda baru memulai shift pagi di Ruang Rawat Inap. Terdapat 10 pasien baru masuk admisi. Tentukan pasien mana yang memerlukan rekonsiliasi obat paling awal."*
- **Tindakan yang diharapkan:**
  1. Membuka Worklist.
  2. Memfilter berdasarkan bangsal dan melihat ranking prioritas (HIGH / MEDIUM / LOW).
  3. Memilih pasien peringkat #1 dengan skor tertinggi.
- **Metrik:** Waktu hingga menemukan pasien (< 60 detik), pemahaman label prioritas.

### Tugas 2: Dokumentasi Riwayat Obat (BPMH) & Disposisi
> *"Pasien mengonfirmasi rutin mengonsumsi Amlodipine 10mg 1x sehari di rumah untuk hipertensi. Masukkan ke dalam BPMH dan tentukan disposisi klinisnya (misal: DILANJUTKAN)."*
- **Tindakan yang diharapkan:**
  1. Membuka tab/form BPMH pasien.
  2. Mengisi nama obat: `amlodipine`, dosis: `10mg`, frekuensi: `1x sehari`.
  3. Memilih disposisi `DILANJUTKAN` dan mengisi alasan singkat.
  4. Menekan tombol Simpan BPMH.
- **Metrik:** Kemudahan form, kejelasan pilihan 4 disposisi (*DILANJUTKAN, DITUNDA, DIGANTI, DIHENTIKAN*).

### Tugas 3: Telaah Analisis & Verifikasi Draf SBAR
> *"Buka hasil analisis sistem untuk memeriksa apakah ada obat yang tertinggal (omission) atau berisiko tinggi. Review draf SBAR dan putuskan tindakan (APPROVE, EDIT, atau REJECT)."*
- **Tindakan yang diharapkan:**
  1. Menavigasi ke halaman Analisis Pasien.
  2. Membaca flag discrepancy (memahami bahwa flag berstatus verifikasi wajib).
  3. Memeriksa faktor SHAP dan safety flags.
  4. Membaca draf SBAR dan menekan APPROVE dengan catatan singkat.
- **Metrik:** Apoteker menyadari watermark "DRAF AI — WAJIB DIVERIFIKASI", kepuasan format SBAR.

---

## 3. Evaluasi Usability (Post-Test)

### Kuesioner System Usability Scale (SUS) Singkat:
1. Sistem ini mudah dipelajari oleh apoteker baru. (Skala 1-5)
2. Saya merasa percaya diri menggunakan sistem ini saat dinas bangsal. (Skala 1-5)
3. Alur kerja dua tahap (Triase → Rekonsiliasi) sesuai dengan standar praktik di RS kami. (Skala 1-5)
4. Bahasa dan terminologi yang digunakan mudah dipahami. (Skala 1-5)

### Pertanyaan Kualitatif:
- Bagian mana yang paling membantu menghemat waktu Anda?
- Informasi apa yang dirasa kurang atau berlebihan?
- Apakah ada tombol atau terminologi yang membingungkan?
