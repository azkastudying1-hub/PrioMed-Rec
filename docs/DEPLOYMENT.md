# Panduan Deployment PrioMed-Rec

> **Dokumen ini ditujukan untuk Tim IT Rumah Sakit.**  
> PrioMed-Rec adalah sistem bantu pengambilan keputusan klinis berbasis AI untuk rekonsiliasi obat pada admisi pasien.

---

## 1. Prerequisites

### Perangkat Lunak
| Kebutuhan | Versi Minimum | Catatan |
|-----------|---------------|---------|
| Docker Engine | 24.x | [Unduh Docker](https://docs.docker.com/engine/install/) |
| Docker Compose | v2.x | Sudah termasuk dalam Docker Desktop |
| Git | 2.x | Untuk menarik kode sumber |

### Spesifikasi Server Minimum
| Komponen | Minimum | Rekomendasi |
|----------|---------|-------------|
| CPU | 2 core | 4 core |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB | 50 GB |
| OS | Ubuntu 20.04 / Windows Server 2019 | Ubuntu 22.04 LTS |

> [!IMPORTANT]
> Pastikan port **80** (web) dan **8000** (API) tidak diblokir oleh firewall rumah sakit.

---

## 2. Langkah Instalasi Step-by-Step

### Langkah 1 — Clone Repository

```bash
git clone https://github.com/rumahsakit/priomed-rec.git
cd priomed-rec
```

### Langkah 2 — Buat File Konfigurasi `.env`

```bash
cp .env.example .env
```

Edit file `.env` sesuai lingkungan rumah sakit (lihat Bagian 3).

### Langkah 3 — Build dan Jalankan Container

```bash
docker compose up --build -d
```

Proses build pertama kali membutuhkan waktu ±5–10 menit (mengunduh dependensi Python dan Node.js).

### Langkah 4 — Verifikasi Status

```bash
docker compose ps
```

Semua service harus berstatus **`running`** atau **`healthy`**.

### Langkah 5 — Akses Aplikasi

- **Antarmuka Web:** `http://<IP-SERVER>/`
- **API Documentation:** `http://<IP-SERVER>:8000/docs`
- **Health Check:** `http://<IP-SERVER>:8000/health`

---

## 3. Konfigurasi Environment (`.env`)

Buat file `.env` di root proyek. Berikut adalah parameter yang **wajib** dikonfigurasi:

```dotenv
# ── LLM Provider ──────────────────────────────────────────────────
# Pilih provider: "gemini" atau "groq"
LLM_PROVIDER=gemini

# API Key untuk Google Gemini (wajib jika LLM_PROVIDER=gemini)
LLM_API_KEY=AIza...

# Mode data yang dikirim ke LLM eksternal:
#   synthetic   → data sintetis saja (aman, untuk demo)
#   anonymized  → data dianonimkan sebelum dikirim (produksi)
#   blocked     → LLM dinonaktifkan sepenuhnya
LLM_DATA_MODE=anonymized

# ── Autentikasi API ───────────────────────────────────────────────
# Kunci API untuk apoteker (akses penuh)
API_KEY_PHARMACIST=ganti-dengan-kunci-rahasia-kuat

# Kunci API untuk akses baca saja (opsional)
API_KEY_READONLY=ganti-dengan-kunci-readonly

# ── Database ──────────────────────────────────────────────────────
# Path database SQLite di dalam container (jangan diubah jika menggunakan Docker)
DB_PATH=/app/data/priomed.db

# ── Server ────────────────────────────────────────────────────────
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000

# ── Threshold Prioritas ───────────────────────────────────────────
HIGH_PRIORITY_THRESHOLD=0.7
MEDIUM_PRIORITY_THRESHOLD=0.4
```

> [!CAUTION]
> **Jangan pernah commit file `.env` ke repository Git.** File ini sudah terdaftar di `.gitignore`.

> [!TIP]
> Gunakan `openssl rand -hex 32` untuk menghasilkan `API_KEY_PHARMACIST` yang kuat secara acak.

---

## 4. Verifikasi Deployment

### Cek Health Endpoint

```bash
curl http://localhost:8000/health
```

Respons yang diharapkan:

```json
{
  "status": "ok",
  "model_version": "xgb_v3_leakage_safe",
  "rule_version": "rules-disposition-v2",
  "api_version": "1.0.0",
  "db_status": "ok",
  "uptime_seconds": 12.5
}
```

### Cek Log Container

```bash
# Log API backend
docker compose logs api --tail=50

# Log web server
docker compose logs web --tail=20
```

### Cek Status Container

```bash
docker compose ps
```

| Service | Status yang Diharapkan |
|---------|------------------------|
| `api` | `running (healthy)` |
| `web` | `running` |

---

## 5. Backup Database

Database SQLite disimpan dalam Docker volume `priomed_data`. Lakukan backup secara rutin.

### Backup Manual

```bash
# Salin database dari volume ke host
docker run --rm \
  -v priomed-rec_priomed_data:/data \
  -v $(pwd)/backup:/backup \
  alpine cp /data/priomed.db /backup/priomed-$(date +%Y%m%d).db
```

### Backup Terjadwal (Crontab Linux)

Tambahkan ke crontab server (`crontab -e`):

```cron
# Backup database setiap hari pukul 02:00
0 2 * * * docker run --rm -v priomed-rec_priomed_data:/data -v /srv/backup/priomed:/backup alpine cp /data/priomed.db /backup/priomed-$(date +\%Y\%m\%d).db
```

> [!NOTE]
> Simpan backup di lokasi yang berbeda dari server utama (NAS, cloud storage RS, atau server backup).

---

## 6. Update Aplikasi

### Update ke Versi Terbaru

```bash
# 1. Tarik perubahan kode terbaru
git pull origin main

# 2. Rebuild dan restart container
docker compose up --build -d

# 3. Verifikasi
curl http://localhost:8000/health
```

> [!WARNING]
> Selalu lakukan **backup database** (lihat Bagian 5) sebelum melakukan update, terutama jika ada perubahan skema database.

### Rollback ke Versi Sebelumnya

```bash
# Kembali ke commit sebelumnya
git checkout <commit-hash>
docker compose up --build -d
```

---

## 7. Troubleshooting Umum

### 🔴 Model ML Gagal Load

**Gejala:** Log menampilkan `WARNING: Could not pre-load model` atau endpoint `/prioritize` mengembalikan error 503.

**Penyebab & Solusi:**

1. File model tidak ada di direktori `models/`
   ```bash
   docker compose exec api ls models/
   # Pastikan ada: model.pkl, metadata.json, thresholds.json
   ```

2. File model rusak — unduh ulang atau restore dari backup:
   ```bash
   docker compose cp backup/models/. api:/app/models/
   ```

3. Volume tidak ter-mount:
   ```bash
   docker compose down && docker compose up -d
   ```

---

### 🔴 Database Tidak Ditemukan / Error SQLite

**Gejala:** Health check menampilkan `"db_status": "error: ..."` atau data BPMH tidak tersimpan.

**Penyebab & Solusi:**

1. Volume belum diinisialisasi — periksa volume:
   ```bash
   docker volume ls | grep priomed
   ```

2. Izin direktori:
   ```bash
   docker compose exec api ls -la data/
   # Direktori data/ harus writable oleh proses uvicorn
   ```

3. Database corrupt — restore dari backup:
   ```bash
   docker compose stop api
   docker run --rm \
     -v priomed-rec_priomed_data:/data \
     -v $(pwd)/backup:/backup \
     alpine cp /backup/priomed-YYYYMMDD.db /data/priomed.db
   docker compose start api
   ```

---

### 🔴 LLM Tidak Merespons / Timeout

**Gejala:** Analisis pasien memakan waktu >30 detik atau mengembalikan error `LLM_TIMEOUT`.

**Penyebab & Solusi:**

1. **API Key tidak valid atau kedaluwarsa:**
   ```bash
   # Periksa nilai API key di .env
   grep LLM_API_KEY .env
   # Perbarui API key, lalu restart
   docker compose restart api
   ```

2. **Server tidak dapat mengakses internet** (untuk Gemini/Groq):
   - Hubungi Tim Jaringan RS untuk memastikan server dapat mengakses `generativelanguage.googleapis.com` dan `api.groq.com`.
   - Atau, ubah ke mode offline: `LLM_DATA_MODE=blocked` di `.env`, lalu restart.

3. **Gunakan model fallback Groq:**
   ```dotenv
   LLM_PROVIDER=groq
   LLM_GROQ_API_KEY=gsk_...
   LLM_GROQ_MODEL=llama-3.3-70b-versatile
   ```

4. **Nonaktifkan LLM sepenuhnya** (sistem tetap berfungsi dengan ML + rule engine):
   ```dotenv
   LLM_DATA_MODE=blocked
   ```

---

### 🔴 Web Tidak Dapat Diakses

**Gejala:** Browser menampilkan "Connection refused" pada port 80.

**Solusi:**
```bash
# Cek status container web
docker compose ps web

# Lihat log error nginx
docker compose logs web

# Restart container web
docker compose restart web
```

---

## Kontak & Dukungan

Untuk pertanyaan teknis, hubungi tim pengembang melalui saluran yang telah ditentukan oleh RS.

> [!NOTE]
> PrioMed-Rec adalah **sistem bantu keputusan klinis** — semua output AI wajib diverifikasi oleh apoteker klinis yang berwenang sebelum diterapkan ke pasien.
