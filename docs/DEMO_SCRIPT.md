# DEMO SCRIPT — PrioMed-Rec
## Skrip Demo 5 Menit (Hackathon Edition)

**Versi:** 1.0  
**Tanggal:** 2025-07  
**Audiens:** Juri hackathon, apoteker klinis, investor

---

## PERSIAPAN SEBELUM DEMO (T-30 menit)

```bash
# 1. Reset data demo bersih
python scripts/demo_reset.py

# 2. Jalankan API
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Jalankan frontend (jika dev mode)
cd web && npm run dev
# ATAU akses via http://localhost:8000/app (static build)

# 4. Cek health
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health
```

**Rekaman cadangan:** Rekam tiap adegan sebelumnya. Jika koneksi gagal, putar rekaman.  
**Kunci API cadangan:** Simpan Groq/Gemini API key di `.env` — jika satu gagal, pakai yang lain.  
**Mode offline:** Matikan `LANGFLOW_BASE_URL` di `.env` → sistem pakai SBAR template deterministik.

---

## SKRIP DEMO 5 MENIT

### 🎬 Menit 0:00–0:40 — Masalah & Urgensi

> *"Bayangkan seorang apoteker di rumah sakit pagi hari. Ada 40 pasien baru masuk. Setiap rekonsiliasi obat butuh 15–50 menit. Mana yang harus dikerjakan pertama? Bagaimana kalau high-alert terlewat?"*

**[Tunjukkan slide/gambar: antrian worklist manual, tumpukan catatan]**

> *"PrioMed-Rec membantu apoteker menjawab tiga pertanyaan: WHO FIRST — WHAT TO CHECK — WHAT TO DO. Semua dalam satu layar."*

---

### 🎬 Menit 0:40–1:20 — Login & Worklist

**[Login sebagai `apoteker1` / `demo1234`]**

1. Buka `http://localhost:8000/app`
2. Login → masuk ke **Worklist Telaah Farmasi**
3. **Tunjukkan:**
   - Tn. B.S. di paling atas — **badge HIGH** merah
   - SLA countdown: `01:42` tersisa (hitung mundur real-time)
   - Chip alasan: `high-alert`, `tier-1-finding`, `polifarmasi`

> *"Sistem mengurutkan otomatis berdasarkan skor ML + aturan deterministik. Apoteker langsung tahu mana yang paling mendesak tanpa buka rekam medis satu per satu."*

---

### 🎬 Menit 1:20–2:00 — Case Workspace: Temuan

**[Klik Tn. B.S. → Case Workspace → Tab "Temuan"]**

4. Tunjukkan **Tier 1 (Kritis):**
   - `warfarin 5mg` — **OMISI** — Pasien riwayat AF kronik ⚠️ HIGH ALERT
   - `bisoprolol 5mg` — **OMISI** — tidak tertulis pada pesanan admisi
5. Klik tab **"Bandingkan"** → BPMH kiri vs pesanan admisi kanan (side-by-side)

> *"Deteksi 100% deterministik — bukan AI yang menebak. Rule engine berlapis: omisi, duplikasi, DDI, alergi silang, substitusi. High-alert langsung hard stop."*

**[Tunjukkan: tombol APPROVE di-blok karena warfarin high-alert belum dikonfirmasi]**

> *"Sistem tidak bisa di-bypass. Apoteker WAJIB konfirmasi setiap high-alert sebelum menyetujui — ini pagar keselamatan medikolegal."*

---

### 🎬 Menit 2:00–2:30 — SHAP & Transparansi

**[Tab "Temuan" → lihat blok skor ML]**

6. Tunjukkan: **Skor: 0.89 (HIGH)** + penjelasan:
   - Usia 72, polifarmasi 9 obat, riwayat AF, INR tidak terpantau
7. Klik "Mengapa HIGH?" → SHAP breakdown

> *"ML bukan kotak hitam. Sistem menjelaskan MENGAPA pasien ini diprioritaskan. Fitur utama: usia, jumlah obat, riwayat high-alert. Ini penting untuk akuntabilitas apoteker."*

---

### 🎬 Menit 2:30–3:00 — SBAR Draft AI

**[Tab "SBAR"]**

8. Tunjukkan draft SBAR berlabel **"Draf AI — Wajib diperiksa apoteker"**:
   - S: Pasien Tn. B.S., 72 th, JANTUNG, masuk 3.5 jam lalu
   - B: Riwayat AF kronik, konsumsi warfarin 5mg/hari
   - A: Warfarin tidak tercantum pada pesanan admisi (Tier-1 omisi HA)
   - R: Konfirmasi dengan DPJP. Lanjutkan warfarin sesuai dosis terakhir & pantau INR
9. Edit satu kalimat di field Rekomendasi → klik **"Salin CPPT"**

> *"AI men-draft, apoteker yang memutuskan. Label 'Draf AI' wajib ada — ini standar keselamatan kami."*

---

### 🎬 Menit 3:00–3:40 — IBM Bob + Langflow + HITL

**[Klik FAB Copilot (pojok kanan bawah) → CopilotDrawer terbuka]**

10. Ketik: *"Apakah warfarin berinteraksi dengan aspirin?"*
11. Bob menjawab: sitasi DDI mayor, risiko perdarahan, rekomendasi monitoring

> *"IBM Bob terhubung via MCP. Dia bisa menjawab pertanyaan klinis DAN men-draft review — tapi tidak bisa mengeksekusi apapun. Keputusan tetap di apoteker."*

12. Klik **"Draft Review via Bob"** → draft muncul di tab SBAR
13. Klik **"Konfirmasi & Simpan"** → action dicatat di audit trail

> *"Ini HITL — Human-in-the-Loop. Langflow mengorkestrasi pipeline AI, Bob berkomunikasi via MCP, tapi apoteker yang menekan tombol terakhir."*

---

### 🎬 Menit 3:40–4:10 — Degradasi Anggun + Safety Net

**[Demo offline: matikan internet / set LANGFLOW_BASE_URL=http://invalid]**

14. Refresh → buka kasus → Tab SBAR
15. Tunjukkan: SBAR masih muncul dengan **template deterministik**
16. Badge merah kecil: *"AI tidak tersedia — menggunakan template standar"*

> *"Sistem tidak pernah berhenti. LLM mati → template. Rule engine tidak bergantung pada AI. Keselamatan terjamin 100% offline."*

**[Kembali ke Worklist]**

17. Tunjukkan Tn. H.F. (S7) — SLA BREACH → badge **ESKALASI** otomatis
18. Tunjukkan Tn. J.R. (S8) — LOW, tidak ada obat rutin → bersih, tidak ada aksi

---

### 🎬 Menit 4:10–4:40 — Audit Trail & Metrik

**[Navigasi ke "Audit Log"]**

19. Tunjukkan entri: APPROVE, DRAFT_REVIEW, LOGIN — setiap aksi tercatat
20. Klik **"Verifikasi Integritas Rantai Hash"** → hijau ✓

> *"Setiap aksi klinis dapat dibuktikan di pengadilan. Hash chain berarti tidak ada yang bisa diubah diam-diam."*

**[Tunjukkan slide metrik — jujur]**

> *"Lift@10% = 1.32x dibanding baseline acak. Recall tier-1 = 94%. Data sintetis — ini PoC. Kami punya protokol shadow test yang siap dijalankan di RS mitra."*

---

### 🎬 Menit 4:40–5:00 — Penutup & Roadmap

> *"Hari ini: prototype yang siap didemonstrasikan. Target pilot: 3 RS dalam 6 bulan. Butuh: data real untuk shadow test, izin etik, integrasi SIMRS."*

> *"PrioMed-Rec bukan pengganti apoteker. Ini alat yang membuat apoteker 3x lebih efisien sambil memastikan tidak ada high-alert yang terlewat."*

---

## ANTISIPASI PERTANYAAN JURI

| Pertanyaan | Jawaban |
|:---|:---|
| "AI bisa salah kasih obat?" | Tidak — LLM tidak punya tool tulis. Deteksi 100% aturan deterministik. 9 guardrail. Keputusan di apoteker. Audit lengkap. |
| "Data sintetis, apa buktinya bekerja?" | Jujur: tahap PoC. Ada protokol shadow test & golden set 40 kasus. Kami laporkan lift & keterbatasan, bukan hanya AUC. |
| "Mengapa perlu ML jika aturan cukup?" | ML mengurutkan SEBELUM BPMH dan menjelaskan. Aturan memastikan keselamatan sesudahnya. Kami bandingkan dengan baseline sederhana. |
| "Mengapa Langflow & Bob?" | Langflow = orkestrasi AI transparan, bisa diubah tanpa coding. Bob = akselerasi dev + antarmuka percakapan dengan pagar HITL. |
| "Bagaimana privasi data?" | Anonimisasi, minimal data ke LLM, opsi LLM lokal, RBAC, audit, rencana patuh UU PDP & PERMENKES. |
| "Integrasi SIMRS?" | Rencana FHIR bridge. Saat ini input manual/CSV. Shadow test tidak ubah data production. |
| "Angka 79% dari mana?" | [Siapkan sitasi: WHO 2017 medication reconciliation report] |

---

## CHECKLIST HARI-H DEMO

- [ ] `python scripts/demo_reset.py` sudah dijalankan
- [ ] API berjalan di port 8000, `/health` returns `200 ok`
- [ ] Web build terbaru (`cd web && npm run build`)
- [ ] Browser di-zoom 100%, resolusi ≥ 1280×720
- [ ] Rekaman cadangan tiap adegan sudah ada
- [ ] Kunci API cadangan tersedia (Groq / Gemini)
- [ ] `.env` production values dikonfirmasi
- [ ] Mode offline sudah ditest
- [ ] Slide metrik disiapkan (lift, recall, keterbatasan)
- [ ] Akun login tertulis di kertas/tab tersembunyi

---

## PERINTAH BERGUNA

```bash
# Reset demo data
python scripts/demo_reset.py

# Jalankan API (development)
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Build frontend
cd web && npm run build

# Jalankan semua tes
python -m pytest tests/test_fase1_b103_auth.py tests/test_fase1_b104_state_machine.py \
  tests/test_fase1_b105_priority.py tests/test_fase1_b107_audit.py \
  tests/test_fase1_b111_normalizer.py tests/test_fase3_ai_orchestration.py \
  tests/test_rules_disposition.py tests/test_safety_flags_engine.py \
  tests/test_analysis_orchestrator.py

# Cek health
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health/deps
```
