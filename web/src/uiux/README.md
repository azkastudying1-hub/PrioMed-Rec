# PrioMed-Rec — UI/UX Clinical Design System

Folder ini adalah **satu paket UI/UX siap pakai** untuk PrioMed-Rec. Isinya
design token, komponen dasar, komponen klinis, kerangka aplikasi, dan dua layar
utama yang menutup alur kerja apoteker: **Worklist Prioritas** dan **Telaah Kasus**.

Tujuannya bukan menambah fitur baru, tetapi membuat alur yang sudah ada terasa
tenang, cepat, aman, dan dapat dipertanggungjawabkan di lingkungan rumah sakit.

---

## 1. Kebutuhan pengguna yang dijawab

| Pengguna | Kebutuhan utama | Jawaban di UI |
|---|---|---|
| Apoteker klinis | Tahu kasus mana yang harus ditelaah lebih dulu | Worklist terurut, badge prioritas + alasan, SLA countdown |
| Apoteker klinis | Tidak melewatkan obat high-alert | Hard-stop modal, hitungan high-alert, konfirmasi per temuan |
| Apoteker klinis | Cepat memahami temuan | Tab Temuan dengan "mengapa ditandai" dan "yang perlu dilakukan" |
| Apoteker klinis | Menyusun komunikasi ke DPJP | Tab SBAR yang bisa diedit dan disalin |
| Koordinator farmasi | Melihat beban dan SLA | KPI kasus aktif, prioritas tinggi, lewat SLA, high-alert |
| Auditor | Menelusuri keputusan | Tab Riwayat + catatan bahwa setiap aksi masuk jejak audit |
| DPJP | Menerima komunikasi ringkas | SBAR berlabel draf, bukan keputusan otomatis |

Prinsip yang dipegang:

1. **Satu layar, satu pekerjaan.** Worklist untuk memilih; Case untuk memutuskan.
2. **Prioritas harus bisa dijelaskan.** Setiap tier membawa alasan dan sumber
   (ML / Aturan / SLA), bukan angka misterius.
3. **Keselamatan tidak boleh tersembunyi.** High-alert memblokir persetujuan
   sampai diperiksa satu per satu.
4. **AI adalah draf.** Semua teks bantuan AI membawa label "Draf AI — wajib
   diverifikasi apoteker".
5. **Tenang secara visual.** Navy, biru, teal, dan permukaan putih; warna status
   selalu berpasangan dengan ikon dan teks.

---

## 2. Struktur folder

```
web/src/uiux/
├─ README.md          ← dokumen ini
├─ tokens.css         ← font, warna, fokus, reduced-motion, utilitas dasar
├─ primitives.tsx     ← Button, Badge, Card, Input, Field, Tabs, Modal, dll.
├─ clinical.tsx       ← PriorityBadge, SLA, temuan, SBAR notice, audit timeline
├─ layout.tsx         ← AppShell: sidebar, topbar, strip keselamatan
├─ pages.tsx          ← WorklistPage dan CasePage (orkestrasi data)
└─ index.ts           ← barrel export
```

### Penjelasan tiap file

**`tokens.css`**
Fondasi visual. Mendefinisikan `--pmr-*` untuk warna, radius, shadow, fokus,
dan font. Juga mengatur `body`, heading, scrollbar, `:focus-visible`, dan
`prefers-reduced-motion`. Tidak ada layout aplikasi di sini.

**`primitives.tsx`**
Komponen tanpa aturan klinis: tombol, badge, kartu, input, field, tabs,
segmented control, modal, alert, empty/error state, skeleton, `Kbd`, skip link.
Semua komponen sudah memiliki focus ring, target sentuh, dan teks alternatif.
`cleanText()` membersihkan karakter mojibake dari data demo lama.

**`clinical.tsx`**
Komponen yang memahami domain:
- `PriorityBadge` — tier + skor ML, selalu dengan ikon dan teks.
- `SlaIndicator` — target HIGH 4 jam / MEDIUM 12 jam / LOW 24 jam, warning
  2 / 6 / 12 jam.
- `WorkflowStatusBadge` — status API maupun status lama.
- `PatientIdentity` — nama, No. RM/encounter, bangsal, DPJP, waktu admisi.
- `KpiCard`, `ReasonChip`, `SourceTag`, `RiskScoreBar`.
- `FindingCard` — "mengapa ditandai" + "yang perlu dilakukan".
- `AiDraftNotice` — label draf AI permanen.
- `SafetyBanner` — pengingat keputusan klinis.
- `AuditTimeline` — riwayat keputusan.
- `HighAlertDialog` — hard stop dengan centang per temuan.

**`layout.tsx`**
`AppShell` dengan sidebar navy, navigasi per kelompok, topbar, badge mode data,
status demo khusus development, dan strip keselamatan. Props sengaja sama dengan
`AppShell` lama agar `App.tsx` bisa mengganti import tanpa mengubah halaman lain.

**`pages.tsx`**
Dua layar utama:
- `WorklistPage` — query worklist, KPI, filter tier/bangsal/pencarian, klaim
  kasus, keyboard shortcut `/` dan `N`, tabel desktop + kartu mobile.
- `CasePage` — header pasien, SLA, skor ML, tab Temuan / Bandingkan / SBAR /
  Riwayat, action bar, modal keputusan, hard-stop high-alert, dan AI Copilot.

**`index.ts`**
Barrel export. Bisa `import { AppShell, WorklistPage, Button } from "./uiux"`.

---

## 3. Cara memakai

### 3.1 Di folder kanonik `web/` (sudah diterapkan)

Perubahan yang sudah dilakukan:

1. `web/src/index.css` mengimpor `./uiux/tokens.css` dan tetap menyimpan token
   lama agar halaman yang belum dimigrasi tidak rusak.
2. `web/index.html` memuat font Inter, Plus Jakarta Sans, dan JetBrains Mono
   serta `theme-color`.
3. `web/src/App.tsx` memakai `AppShell`, `WorklistPage`, dan `CasePage` dari
   `./uiux`.
4. `web/src/components/AiDraftLabel.tsx` diperbaiki: ikon lucide dan tanda
   pisah yang benar, tanpa karakter rusak.

Jalankan:

```bash
cd web
npm run dev
```

Verifikasi produksi:

```bash
cd web
npm run build
```

### 3.2 Bila ingin menerapkan ke `frontend/web`

`frontend/web` adalah salinan/eksperimen. Folder kanonik menurut
`docs/WEBSITE_RUNBOOK.md` adalah `web/`. Bila tetap ingin memakai
`frontend/web`:

1. Salin `web/src/uiux/` ke `frontend/web/src/uiux/`.
2. Samakan `frontend/web/src/index.css` dengan pola `web/src/index.css`
   (impor `./uiux/tokens.css`, pertahankan token lama yang masih dipakai).
3. Tambahkan font `<link>` dan `theme-color` di `frontend/web/index.html`.
4. Ganti `AppShell` di `frontend/web/src/App.tsx` dengan
   `import { AppShell } from "./uiux/layout"`.
5. Ganti halaman worklist/case dengan `WorklistPage` dan `CasePage` dari
   `./uiux/pages`, lalu sesuaikan tipe `WorklistItemV1` bila berbeda.

Catatan: `frontend/web` memiliki `types/clinical.ts` dan `api/client.ts` yang
berbeda. Komponen `uiux` bergantung pada `WorklistItemV1` dan `ReviewAction`
dari `web/src/lib/apiClient.ts`; pastikan tipe dan endpoint di target sama
sebelum menyalin.

---

## 4. Integrasi data

Halaman memakai API yang sudah ada, bukan endpoint baru:

| Aksi | Fungsi |
|---|---|
| Memuat worklist | `getWorklistV1({ page_size: 100 })` |
| Klaim kasus | `claimEncounterV1(encounterId, rowVersion)` |
| Menyimpan keputusan | `submitReviewV1(encounterId, body, { idempotencyKey, ifMatch })` |
| Riwayat telaah | `getReviewHistoryV1(encounterId)` |

Mode data mengikuti `VITE_DATA_MODE`:

- `synthetic` (default) — memakai `clinicalData.ts`, keputusan tidak dikirim ke
  server. Cocok untuk demo dan pengembangan UI.
- `live` — memakai API, polling 30 detik, klaim, hard-stop server, dan audit
  trail tetap berlaku.

Pada mode `live`, tombol **Setujui** tidak mengirim apa pun sebelum semua temuan
high-alert dicentang. Ini lapisan UI; server tetap wajib menolak `APPROVE` bila
high-alert belum dikonfirmasi.

---

## 5. Standar visual & aksesibilitas

- **Tipografi**: Inter untuk teks, Plus Jakarta Sans untuk judul, JetBrains Mono
  untuk angka/SLA/hash.
- **Warna**: navy `#061426`, biru `#1d4ed8`, teal `#0d9488`; status merah,
  amber, emerald, biru.
- **Kontras**: teks utama `#0f172a` di atas putih; teks sekunder `#475569`.
- **Target sentuh**: minimal 40px untuk kontrol, 44px untuk aksi utama.
- **Fokus**: `:focus-visible` 2px biru + ring pada komponen.
- **Status**: selalu ikon + teks, bukan warna saja.
- **Modal**: Escape menutup, scroll dikunci, fokus dipindahkan ke dialog.
- **Tabs**: ArrowLeft / ArrowRight.
- **Reduced motion**: animasi diperkecil bila pengguna mengaktifkannya.
- **Skip link**: langsung ke `#pmr-main`.

Checklist sebelum rilis:

- [ ] Semua aksi utama bisa dijangkau keyboard.
- [ ] Semua badge status punya teks, bukan hanya warna.
- [ ] High-alert tidak bisa disetujui tanpa centang.
- [ ] Teks AI selalu memakai label draf.
- [ ] Tidak ada emoji/karakter mojibake di layar baru.
- [ ] Worklist punya loading, empty, dan error state.
- [ ] Tabel bisa di-scroll horizontal di layar kecil.

---

## 6. Keyboard shortcut

| Tombol | Aksi |
|---|---|
| `/` | Fokus ke pencarian worklist |
| `N` | Ambil kasus berikutnya |
| `Enter` / `Space` pada baris | Buka telaah |
| `ArrowLeft` / `ArrowRight` pada tab | Pindah tab |
| `Escape` | Tutup modal / drawer |

---

## 7. Batasan & langkah berikutnya

- Halaman lama (Queue, Command Center, BPMH, Audit, Settings, Tutorial) belum
  dimigrasi ke `uiux`; token lama tetap dipertahankan agar tidak rusak.
- Rincian order obat pada mode live bergantung pada data yang tersedia di
  worklist. Bila tidak ada, tab Bandingkan menampilkan alasan prioritas dan
  mengarahkan ke modul BPMH.
- SBAR tidak dikirim otomatis; apoteker menyalin dan mengirim lewat kanal resmi.
- Langkah berikutnya: migrasikan Queue dan Command Center ke `Card`, `Badge`,
  dan `KpiCard` yang sama agar bahasa visual seluruh aplikasi konsisten.
