# PrioMed-Rec Database Schema

**Database Engine:** SQLite (WAL mode)  
**File:** `data/priomed.db` (override with `DB_PATH`)  
**Managed by:** `api/database.py`

---

## Tables

### 1. `bpmh_records`
Best Possible Medication History (BPMH) — riwayat penggunaan obat terbaik sebelum admisi.

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| `patient_id` | TEXT (PK) | ID pasien |
| `encounter_id` | TEXT (PK) | ID encounter admisi |
| `pharmacist_id` | TEXT | ID/nama apoteker yang mendokumentasikan |
| `saved_at` | TEXT NOT NULL | Timestamp ISO 8601 (UTC) |
| `source_notes` | TEXT | Sumber riwayat (e.g. wawancara pasien, keluarga, blister obat) |
| `medications_json` | TEXT NOT NULL | JSON array dari daftar obat BPMH beserta disposisi |

**medications_json item schema:**
```json
{
  "medication_name": "amlodipine",
  "dose": "10",
  "unit": "mg",
  "frequency": "1x sehari",
  "route": "oral",
  "source": "Wawancara keluarga",
  "last_taken": "2025-10-25 08:00",
  "disposition": "DILANJUTKAN",
  "disposition_reason": "Indikasi hipertensi masih aktif",
  "indication_note": "Target TD < 140/90"
}
```

---

### 2. `audit_entries`
Audit trail kepatuhan farmasi klinis — mencatat semua aksi verifikasi apoteker.

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| `review_id` | TEXT (PK) | UUID unik per review |
| `case_id` | TEXT NOT NULL | ID kasus / encounter |
| `patient_id` | TEXT | ID pasien |
| `pharmacist_id` | TEXT | ID apoteker penelaah |
| `action` | TEXT NOT NULL | `APPROVE` \| `REJECT` \| `EDIT` |
| `timestamp` | TEXT NOT NULL | Timestamp ISO 8601 (UTC) |
| `note` | TEXT | Catatan telaah apoteker |
| `model_version` | TEXT | Versi model ML saat review |
| `rule_version` | TEXT | Versi rule engine saat review |
| `ai_result_json` | TEXT | Snapshot hasil analisis AI |

---

### 3. `ward_configs`
Konfigurasi kapasitas bangsal rawat inap untuk triase apoteker.

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| `ward_id` | TEXT (PK) | Kode bangsal (e.g. `icu`, `interna`) |
| `ward_name` | TEXT NOT NULL | Nama bangsal (e.g. "Penyakit Dalam") |
| `capacity` | INTEGER NOT NULL | Target kapasitas review per shift |
| `allocated` | INTEGER NOT NULL | Jumlah pasien saat ini |
| `pharmacists` | INTEGER NOT NULL | Jumlah apoteker yang bertugas |
| `updated_at` | TEXT | Timestamp perubahan terakhir |

---

### 4. `patient_status`
Sinkronisasi status alur kerja pasien real-time antar sesi/tab apoteker.

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| `patient_id` | TEXT (PK) | ID pasien |
| `encounter_id` | TEXT (PK) | ID encounter |
| `workflow_status` | TEXT NOT NULL | `MENUNGGU_BPMH` \| `BPMH_TERISI` \| `DISETUJUI` \| `DITOLAK` \| `DIEDIT` |
| `updated_at` | TEXT | Waktu update terakhir |
| `updated_by` | TEXT | Identitas pengubah |

---

### 5. `local_high_alert`
Daftar obat high-alert lokal rumah sakit (tambahan formularium lokal).

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| `drug_name` | TEXT (PK) | Nama obat generik/brand lokal (lowercase) |
| `category` | TEXT | Kategori kewaspadaan (e.g. "Konsentrat Pekat", "Sitostatika") |
| `added_by` | TEXT | Identitas apoteker yang mendaftarkan |
| `added_at` | TEXT | Waktu penambahan |

---

## Pemeliharaan & Backup

```bash
# Backup langsung file database SQLite
cp data/priomed.db data/priomed_backup_$(date +%Y%m%d).db

# SQLite dump jika ingin migrasi ke PostgreSQL di masa depan
sqlite3 data/priomed.db .dump > data/priomed_dump.sql
```
