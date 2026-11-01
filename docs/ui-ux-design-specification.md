# PrioMed-Rec: UI/UX Design Specification

## Design Philosophy
UI/UX healthcare yang profesional dibangun dari:
- Human-centered design
- Pengurangan cognitive load
- Visual hierarchy
- Alert hierarchy
- Progressive disclosure
- Accessibility
- Error prevention
- Feedback
- Trust towards AI

Untuk PrioMed-Rec, prinsip ini diterjemahkan menjadi:
- Worklist yang scannable
- Detail pasien yang actionable
- Alert yang berjenjang
- SHAP yang dapat dipahami
- SBAR draft yang jelas
- Audit trail yang lengkap

---

## 1. Worklist Page

**Tujuan:** Apoteker langsung tahu pasien mana yang harus direview.

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ PrioMed-Rec | Admission MedRec Worklist                             │
├──────────────────────────────────────────────────────────────────────┤
│ Filter: [All] [HIGH] [MEDIUM] [LOW] [High Alert] [SLA Breached]     │
│ Search: [Patient ID / Diagnosis]                                     │
├──────────────────────────────────────────────────────────────────────┤
│ P001 | 78M | Pneumonia | 9 meds | Warfarin, Insulin                 │
│ Risk: 0.82 | HIGH | Waiting: 2h 10m | Status: PENDING               │
│ Reasons: OMISSION warfarin, high-alert, renal impairment            │
│                                                        [Review →]   │
├──────────────────────────────────────────────────────────────────────┤
│ P014 | 65F | DM Foot Ulcer | 7 meds | Insulin                       │
│ Risk: 0.71 | HIGH | Waiting: 45m | Status: PENDING                  │
│ Reasons: Insulin + fasting, incomplete history                      │
│                                                        [Review →]   │
└──────────────────────────────────────────────────────────────────────┘
```

### Prinsip Desain

- **Maksimal 5 kolom utama** di worklist
- **Gunakan badge warna** untuk priority (merah/orange/kuning/hijau)
- **Tampilkan alasan singkat**, bukan seluruh SHAP value
- **Tombol utama hanya satu: Review** - menghindari choice paralysis

### Kolom Worklist

| Kolom | Deskripsi |
|-------|-----------|
| Patient ID | Contoh: P001 |
| Usia & Jenis Kelamin | Contoh: 78M |
| Diagnosis | Contoh: Pneumonia |
| Jumlah Obat | Contoh: 9 meds |
| Obat Utama | Contoh: Warfarin, Insulin |
| Risk Score | Contoh: 0.82 |
| Priority | HIGH/MEDIUM/LOW dengan badge |
| Waiting Time | Contoh: 2h 10m |
| Status | PENDING/Approved |
| Reasons | 2-3 alasan singkat |

---

## 2. Patient Detail Page

**Tujuan:** Apoteker memahami kasus dan mengambil keputusan.

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ Patient P001 | 78M | Pneumonia | Encounter E001                     │
│ Risk: 0.82 | HIGH | Waiting: 2h 10m                                 │
├──────────────────────────────────────────────────────────────────────┤
│ [Medication Comparison] [Risk Explanation] [SBAR] [Audit Trail]     │
├──────────────────────────────────────────────────────────────────────┤
│ MEDICATION COMPARISON                                                │
│                                                                      │
│ Warfarin 5 mg       | Not ordered        | OMISSION | CRITICAL       │
│ Metformin 500 mg    | Metformin 500 mg   | MATCHED   |              │
│ Levetiracetam 500   | Not ordered        | OMISSION | HIGH           │
│ Amlodipine 10 mg    | Amlodipine 5 mg    | REVIEW    | Dose change   │
│ Omeprazole 20 mg    | Omeprazole 20 mg   | NEW       |              │
├──────────────────────────────────────────────────────────────────────┤
│ RISK EXPLANATION                                                     │
│ 1. Warfarin high-alert omitted                                       │
│ 2. Renal impairment                                                  │
│ 3. Bleeding history                                                  │
│ 4. Incomplete medication history                                     │
├──────────────────────────────────────────────────────────────────────┤
│ [Generate SBAR Draft] [Escalate to DPJP]                            │
├──────────────────────────────────────────────────────────────────────┤
│ Pharmacist Review                                                    │
│ Action: [APPROVE] [REJECT] [EDIT] [ESCALATE]                        │
│ Note: [____________________________________________]                │
│                                                     [Save Review]   │
└──────────────────────────────────────────────────────────────────────┘
```

### Prinsip Desain

- **Tab utama: Medication Comparison** - tampilan pertama ketika membuka detail pasien
- **SHAP dan detail teknis menggunakan progressive disclosure** - detail hidden hingga di-expand
- **SBAR selalu diberi label AI-generated draft** - menunjukkan otomatisasi
- **Review form selalu terlihat di bagian bawah** - accessibilitas tinggi

### Tab Structure

1. **Medication Comparison** (default tab)
   - Tabel perbandingan obat yang di-order vs di-rec
   - Status per obat: OMISSION, MATCHED, REVIEW, NEW
   - Severity badge: CRITICAL, HIGH, Dose change

2. **Risk Explanation**
   - Daftar alasan risiko dalam format terstruktur
   - Nomor untuk referensi mudah

3. **SBAR**
   - Draft AI-generated dengan label prominent
   - Format SBAR lengkap: Situation, Background, Assessment, Recommendation

4. **Audit Trail**
   - Riwayat review dan perubahan

### Form Review (Bagian Bawah)

```
Pharmacist Review
Action: [APPROVE] [REJECT] [EDIT] [ESCALATE]
Note: [____________________________________________]
                                                    [Save Review]
```

---

## 3. Alert Panel

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ CRITICAL                                                             │
│ Warfarin omitted from admission order.                               │
│ Why: High-alert medication; bleeding history; eGFR 34.              │
│ Action: Verify last dose and escalate to DPJP.                      │
│ [Verify] [Escalate]                                                  │
├──────────────────────────────────────────────────────────────────────┤
│ HIGH                                                                 │
│ Insulin used before admission; patient is fasting.                   │
│ Why: Hypoglycemia risk.                                              │
│ Action: Confirm last insulin dose.                                  │
│ [Verify]                                                             │
├──────────────────────────────────────────────────────────────────────┤
│ MODERATE                                                             │
│ Potential duplicate antihypertensive therapy.                        │
│ Why: Similar active ingredient may exist.                            │
│ Action: Review medication names and doses.                          │
│ [Review later]                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### Prinsip Desain

- **Critical harus diacknowledge** - wajib interaksi sebelum melanjutkan
- **Moderate/Low tidak boleh menginterupsi alur utama** - muncul di sidebar atau collapsible
- **Setiap alert harus punya Why dan Action** - edukasi kepada apoteker
- **Hierarki warna:** Merah = Critical, Oranye = High, Kuning = Medium, Hijau = Low

### Tipe Alert

| Tipe | Interaksi | Pola Tampilan |
|------|-----------|---------------|
| **CRITICAL** | Wajib [Verify] atau [Escalate] | Merah, menumpuk di atas |
| **HIGH** | Disarankan [Verify] | Oranye, muncul setelah critical |
| **MODERATE** | Opsional [Review later] | Kuning, collapsible |
| **LOW** | Informasi | Hijau, bisa diabaikan |

---

## 4. SBAR Panel

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ SBAR DRAFT — AI GENERATED                                            │
├──────────────────────────────────────────────────────────────────────┤
│ S: Pasien laki-laki 78 tahun, pneumonia, masuk dari IGD dan akan     │
│    dirawat inap.                                                     │
│                                                                      │
│ B: Menggunakan warfarin, metformin, dan levetiracetam sebelum        │
│    admisi. Dosis terakhir belum dikonfirmasi.                        │
│                                                                      │
│ A: Potensi omission warfarin dan levetiracetam. Risiko perdarahan    │
│    dan kejang bila obat rutin terlewat.                              │
│                                                                      │
│ R: Mohon konfirmasi dosis terakhir warfarin dan levetiracetam.       │
│    Verifikasi ke keluarga/apotek/rekam medis.                        │
│    Komunikasikan temuan ke DPJP.                                     │
├──────────────────────────────────────────────────────────────────────┤
│ AI-generated draft. Wajib diverifikasi apoteker.                     │
│ Keputusan terapi akhir oleh DPJP.                                    │
└──────────────────────────────────────────────────────────────────────┘
```

### Prinsip Desain

- **Label prominent:** "AI-generated draft" - transparansi penuh
- **Wajib diverifikasi apoteker** - accountability
- **Keputusan terapi akhir oleh DPJP** - garis batas otoritas
- **Format konsisten:** S (Situation), B (Background), A (Assessment), R (Recommendation)

### Konten SBAR

- **S (Situation):** Kondisi pasien sekarang, alasan admisi
- **B (Background):** Riwayat obat, riwayat medis penting
- **A (Assessment):** Analisis risiko, discrepancy yang ditemukan
- **R (Recommendation):** Tindakan yang diharapkan

---

## 5. Design System

### Elemen Visual

| Elemen | Rekomendasi |
|--------|-------------|
| **Font** | Inter, IBM Plex Sans, atau Source Sans Pro |
| **Ukuran font** | 14–16 px untuk body, 18–24 px untuk heading |
| **Warna prioritas** | Merah = Critical, oranye = High, kuning = Medium, hijau = Low |
| **Kontras** | Minimal WCAG AA |
| **Tombol utama** | Satu tombol primer per layar |
| **Ikon** | Gunakan ikon medis yang familiar, bukan dekoratif |
| **Tabel** | Sticky header, zebra striping, badge status |
| **Loading** | Skeleton loading, bukan layar kosong |
| **Error** | Pesan spesifik dan tindakan perbaikan |
| **Empty state** | "Belum ada pasien yang memerlukan review" |

### Warna Prioritas

- **Critical (Merah):** #DC2626 - Segera perhatian, action required
- **High (Oranye):** #F59E0B - Perhatian tinggi, verifikasi needed
- **Medium (Kuning):** #EAB308 - Perhatian sedang, review recommended
- **Low (Hijau):** #10B981 - Informasi, bisa diabaikan

---

## 6. Alur UX yang Disarankan

```
Login apoteker
      │
      ▼
Worklist prioritas
      │
      ▼
Pilih pasien
      │
      ▼
Medication comparison
      │
      ├── Lihat alasan risiko
      ├── Lihat discrepancy
      ├── Generate SBAR
      ├── Escalate ke DPJP
      └── Simpan review
      │
      ▼
Kembali ke worklist
```

### Metrik UX yang Perlu Diukur

| Metrik | Target |
|--------|--------|
| Waktu memahami prioritas pasien | < 3 detik |
| Waktu review satu kasus | 1–3 menit |
| Jumlah klik untuk menyelesaikan review | Maksimal 5 klik |
| Tingkat alert yang ditindaklanjuti | Meningkat |
| Tingkat alert yang diabaikan | Menurun |
| Kepuasan apoteker (SUS score) | Minimal 70 |
| Error input | Menurun |
| Waktu menemukan pasien high-alert | < 10 detik |

---

## 7. Rekomendasi Implementasi MVP

**Untuk hackathon, buat hanya 4 halaman:**

1. **Login sederhana** - Autentikasi apoteker only
2. **Worklist** - Tampilan prioritas pasien dengan filter
3. **Patient Detail** - Perbandingan obat, risk explanation, SBAR, review form
4. **Review Confirmation** - Konfirmasi keputusan setelah review

**Jangan membuat:**
- Modul admin
- Reporting
- Integrasi penuh EHR di MVP

**Fokus pada alur yang paling bernilai:**
apoteker melihat worklist → memahami risiko → mereview → mencatat keputusan

---

## 8. Accessibility Considerations

- Kontras warna minimal WCAG AA untuk semua badge dan teks
- Ukuran teks yang bisa di-resize tanpa break layout
- Label yang deskriptif untuk screen reader
- Tombol yang bisa diakses melalui keyboard saja
- Focus indicators yang jelas
- Warna tidak sole sebagai satu-satunya indikator makna (tambahkan ikon atau teks)

---

## 9. Error Prevention Features

- **Disable tombol** yang tidak relevant pada konteks tertentu
- **Confirm dialogue** untuk action yang drastis (escalate, reject)
- **Validation real-time** pada form input
- **Draft autosave** sebelum logout atau peralihan halaman
- **Inline validation** pesan error spesifik

---

## 10. Feedback Mechanisms

- **Skeleton loading** saat data fetching
- **Toast notifications** untuk action success/failure
- **Inline confirmation** setelah review disave
- **Progressive disclosure** untuk mencegah info overload
- **Visual feedback** pada hover/active state tombol

---

## 11. Trust Towards AI

- **Label transparent:** "AI-generated draft" di SBAR dan discrepancy
- **Human override** selalu tersedia
- **Audit trail** lengkap untuk accountability
- **Confidence indicators** jika tersedia
- **Option to edit** AI-generated content sebelum submit

---

## 12. Empty States

- **Worklist empty:** "Belum ada pasien yang memerlukan review"
- **Patient detail empty:** "Tidak ada discrepancy ditemukan"
- **Alert panel empty:** "Semua alert sudah dihandle"
- **Design:** Gunakan illustration atau placeholder yang relevan dengan informasi edukatif

---

## 13. Tabel Layout Specifications

```
Sticky header       | Kolom header tetap saat scroll
Zebra striping      | Baris berwarna berbeda untuk readability
Badge status        | Warna merah/orange/kuning/hijau untuk priority
Column width        | Responsif, minimum 120px untuk text, wider untuk nomor ID
```

## 14. Key Performance Indicators

- **Time to priority understanding:** < 3 detik dari worklist load
- **Review completion time:** 1–3 menit per kasus
- **Click efficiency:** Maksimal 5 klik dari login hingga save review
- **Alert responsiveness:** < 10 detik untuk menemukan high-alert pasien

---