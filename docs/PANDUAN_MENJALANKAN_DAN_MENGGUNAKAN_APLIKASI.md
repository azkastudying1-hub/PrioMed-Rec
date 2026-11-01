# Panduan Lengkap Menjalankan dan Menggunakan PrioMed-Rec

> **Versi panduan:** disusun dari implementasi repositori saat ini.  
> **Target pengguna:** pengembang lokal, demonstrator, dan apoteker klinis yang berwenang.

## 1. Ringkasan proyek dan batas penggunaan

PrioMed-Rec adalah prototipe *clinical decision support* untuk membantu apoteker memprioritaskan **telaah rekonsiliasi obat saat admisi**. Sistem mengurutkan kasus berdasarkan kemungkinan adanya diskrepansi obat, menampilkan alasan prioritas, membantu pencatatan BPMH (*Best Possible Medication History*), dan merekam keputusan telaah.

Sistem **bukan** alat triase kegawatdaruratan dan tidak menggantikan pertimbangan apoteker, DPJP, atau tenaga kesehatan lain. Seluruh keluaran model, aturan, SBAR, dan Copilot adalah bahan telaah yang wajib diverifikasi manusia sebelum dipakai dalam keputusan klinis atau CPPT.

Arsitektur jalur aplikasi yang didukung:

```text
Browser (React/Vite, port 5173)
        │ /api
        ▼
FastAPI (port 8000) ──► model ML + rule engine + SQLite + audit trail
        │
        └──────────────► Langflow/LLM (opsional; bila tidak tersedia gunakan fallback)
```

`streamlit_app/` masih ada di repositori, tetapi bukan antarmuka runtime yang didukung. Gunakan aplikasi pada folder `web/`.

## 2. Fitur, manfaat, dan statusnya

| Fitur | Kegunaan/manfaat | Cara akses | Status implementasi saat ini |
|---|---|---|---|
| Login berbasis peran | Membatasi akses dan mencatat identitas pengguna pada audit trail. | Halaman awal mode `live`. | Aktif. |
| Worklist prioritas | Memusatkan antrean kerja, menampilkan HIGH/MEDIUM/LOW, status, alasan, dan hitung mundur SLA agar kasus yang perlu ditelaah lebih dahulu terlihat cepat. | **Worklist**. | Aktif di mode `live`. Polling setiap 30 detik. |
| Klaim kasus | Mengurangi risiko dua pengguna mengerjakan encounter yang sama. | Tombol **Klaim** pada baris worklist. | Aktif. |
| Workspace kasus | Menyatukan perbandingan, temuan, SBAR, riwayat, dan keputusan dalam satu layar sehingga penelusuran kasus lebih rapi. | Klik baris kasus dari Worklist. | Aktif. |
| Temuan/diskrepansi | Mengelompokkan alasan prioritas menjadi Tier 1 (kritis), Tier 2, dan Tier 3 agar fokus telaah jelas. | Tab **Temuan** di workspace. | Aktif bila data alasan tersedia. |
| Konfirmasi high-alert | Mencegah persetujuan tanpa pengakuan atas temuan obat high-alert. | Aksi **Setujui** pada kasus dengan high-alert. | Aktif. |
| SBAR | Menyediakan area draf Situation–Background–Assessment–Recommendation yang dapat disalin untuk CPPT setelah diverifikasi. | Tab **SBAR** di workspace. | Aktif; isian SBAR saat ini manual. |
| Keputusan telaah | Menyimpan draf, persetujuan, pengeditan, penolakan, atau eskalasi beserta alasan/catatan. | Bilah aksi bawah workspace. | Aktif; alasan wajib untuk Edit, Tolak, Eskalasi. |
| BPMH | Mencatat riwayat obat terbaik pasien untuk dibandingkan dengan order admisi. | **Form BPMH**. | Aktif pada alur UI klasik/sintetis; API BPMH tersedia. |
| AI Copilot | Membantu mengajukan pertanyaan tentang kasus melalui AI Gateway, tanpa browser mengakses LLM langsung. | Tombol **Copilot** pada workspace. | Aktif bila gateway/Langflow/LLM tersedia; jawaban tetap draf AI. |
| Audit log + hash chain | Menelusuri tindakan pengguna; Admin/Auditor dapat memeriksa integritas rantai hash. | **Audit Log**. | Aktif; verifikasi hanya untuk peran ADMIN/AUDITOR. |
| Pengaturan | Mengubah daftar high-alert dan kapasitas bangsal untuk demonstrasi UI. | **Pengaturan**. | Prototype lokal: perubahan hanya memori browser dan hilang saat refresh. |
| Tutorial | Menjelaskan urutan kerja yang direkomendasikan. | **Tutorial**. | Aktif. |
| Command Center dan Antrean | Diharapkan menjadi halaman ringkasan/antrean lanjutan. | Menu terkait. | **Placeholder**, belum menyediakan alur operasional lengkap. |

## 3. Prasyarat

- Windows PowerShell (contoh perintah di bawah untuk Windows).
- Python 3.10 atau lebih baru (direkomendasikan Python 3.12).
- Node.js 20 atau lebih baru dan npm.
- Git (bila repositori belum di-clone).
- Koneksi internet hanya diperlukan bila memasang dependensi atau memakai provider LLM eksternal.

LLM tidak wajib untuk menjalankan alur telaah utama. Bila kunci LLM/Langflow kosong atau layanan tidak tersedia, backend dirancang untuk tetap menyediakan alur aman berbasis aturan/fallback.

## 4. Menjalankan aplikasi secara lokal (direkomendasikan)

Jalankan perintah berikut dari root repositori. Jika belum ada virtual environment, buat terlebih dahulu.

### Terminal 1 — backend FastAPI

```powershell
Set-Location D:\Hacktiv8\priomed-rec

# Hanya sekali, jika .venv belum ada
python -m venv .venv

# Hanya sekali atau ketika requirements berubah
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Buat konfigurasi lokal bila belum ada
Copy-Item .env.example .env

# Pemeriksaan susunan data dan artefak model
.\.venv\Scripts\python.exe scripts\validate_data_layout.py

# Jalankan API
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Catatan:

- Jangan menyalin `.env.example` jika `.env` telah berisi konfigurasi lokal yang ingin dipertahankan.
- Saat basis data kosong, aplikasi otomatis menambahkan 10 skenario demo (`AUTO_SEED_DEMO=true` secara default).
- Basis data lokal default tersimpan di `data/priomed.db`. Jangan gunakan atau masukkan data pasien nyata tanpa tata kelola dan persetujuan institusi.

Setelah log startup menyatakan API berjalan, buka dan periksa:

- Healthcheck: `http://localhost:8000/health`
- Dokumentasi endpoint interaktif: `http://localhost:8000/docs`

### Terminal 2 — frontend React/Vite

```powershell
Set-Location D:\Hacktiv8\priomed-rec\web

# Hanya sekali atau jika package-lock.json berubah
npm ci

# Wajib untuk memakai API lokal dan login
$env:VITE_DATA_MODE = "live"
npm run dev
```

Buka alamat yang ditampilkan Vite, normalnya `http://localhost:5173`.

### Konfigurasi minimum `.env`

Untuk demo lokal, pertahankan parameter basis data/CORS dari `.env.example`; ganti nilai rahasia sebelum lingkungan selain demo. Contoh aman tanpa provider LLM:

```env
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost
DATABASE_URL=sqlite:///data/priomed.db
DB_PATH=data/priomed.db
JWT_SECRET_KEY=ganti_dengan_rahasia_minimal_32_karakter
JWT_REFRESH_SECRET_KEY=ganti_dengan_rahasia_refresh_yang_kuat
LLM_API_KEY=
```

Jangan memasukkan API key ke kode sumber atau meng-commit `.env`. Jika memakai Gemini/Groq, isi kunci hanya di `.env` sesuai nama variabel yang tersedia dalam `.env.example`.

## 5. Menjalankan dengan Docker

Gunakan opsi ini bila Docker Desktop telah aktif dan Anda ingin menjalankan stack container.

```powershell
Set-Location D:\Hacktiv8\priomed-rec
docker compose up --build
```

Buka `http://localhost`. Stack menjalankan API, web Nginx, dan Langflow; volume `priomed_runtime` menyimpan SQLite/audit state. Hentikan stack dengan:

```powershell
docker compose down
```

Jangan menambahkan `-v` kecuali memang bermaksud menghapus volume state operasional. Sebelum menjalankan Docker, ganti semua nilai contoh/`CHANGE_ME` untuk rahasia Langflow dan JWT pada `.env`.

## 6. Akun demo dan masuk aplikasi

Pada mode `live`, halaman login muncul otomatis. Masukkan salah satu akun demo berikut:

| Peran | Username | Password | Manfaat utama |
|---|---|---|---|
| Apoteker | `apoteker1` | `demo1234` | Menjalankan telaah dan mengambil keputusan kasus. |
| TTK | `ttk1` | `demo1234` | Mengakses alur sesuai hak peran teknis kefarmasian. |
| Admin | `admin` | `admin1234` | Mengakses fungsi administratif, termasuk verifikasi audit hash chain. |

Setelah berhasil masuk, token akses disimpan di browser. Access token berlaku 15 menit dan refresh token 7 hari berdasarkan konfigurasi default. Untuk demonstrasi produksi, ganti atau hapus seluruh akun demo.

## 7. Alur penggunaan utama: dari antrean sampai keputusan

### Langkah 1 — telaah Worklist

1. Pilih menu **Worklist**.
2. Gunakan pencarian untuk mencari pasien/ID dan filter **HIGH**, **MEDIUM**, atau **LOW** untuk mempersempit daftar.
3. Periksa kolom prioritas, status proses, bangsal, SLA, dan chip alasan prioritas.
4. Mulailah dari kasus **HIGH** atau yang mendekati/melewati SLA; label ini adalah prioritas telaah farmasi, bukan diagnosis atau prioritas kegawatdaruratan pasien.
5. Klik **Klaim** bila tersedia, kemudian klik baris kasus untuk membuka workspace.

Manfaat: apoteker dapat membagi perhatian pada kasus dengan indikasi diskrepansi lebih tinggi dan mengurangi keterlambatan telaah.

### Langkah 2 — cek data dan temuan dalam Case Workspace

Di halaman kasus, identitas pasien, bangsal, prioritas, status, dan countdown SLA selalu terlihat pada header.

1. Buka tab **Bandingkan** untuk melihat representasi data BPMH/order dan alasan yang tersedia.
2. Buka tab **Temuan**. Tier 1 selalu ditampilkan; Tier 3 disembunyikan secara default agar tidak mengganggu fokus pada temuan serius.
3. Validasi setiap temuan terhadap rekam medis, BPMH, order dokter, dan sumber primer. Jangan menganggap temuan sebagai keputusan otomatis.
4. Bila ada fakta klinis yang belum cukup, gunakan **Eskalasi** atau lengkapi telaah sesuai SOP institusi.

Manfaat: layar tunggal mengurangi perpindahan konteks saat membandingkan riwayat obat, order admisi, dan alasan prioritas.

### Langkah 3 — isi dan gunakan SBAR

1. Buka tab **SBAR**.
2. Isi empat kotak berikut:

   - **S — Situation:** masalah/temuan saat ini.
   - **B — Background:** riwayat obat atau konteks yang relevan.
   - **A — Assessment:** penilaian apoteker atas temuan.
   - **R — Recommendation:** rekomendasi yang telah ditelaah.

3. Klik **Salin SBAR untuk CPPT** bila teks telah diverifikasi.
4. Tempelkan pada sistem dokumentasi resmi hanya setelah diperiksa apoteker.

Manfaat: format komunikasi konsisten dan lebih mudah dipahami oleh DPJP/tim klinis.

### Langkah 4 — ambil keputusan dan dokumentasikan

Masukkan **Catatan opsional apoteker** bila diperlukan, lalu pilih tindakan:

| Tindakan | Kapan digunakan | Input yang diwajibkan sistem |
|---|---|---|
| **Simpan Draf** | Telaah belum final dan ingin dilanjutkan. | Tidak ada alasan wajib. |
| **Setujui** | Telaah dan rekomendasi telah diverifikasi serta dapat disetujui. | Konfirmasi tambahan bila ada high-alert belum dikonfirmasi. |
| **Edit & Setujui** | Draf perlu koreksi sebelum disetujui. | Alasan wajib. |
| **Tolak** | Draf/temuan tidak dapat diterima. | Alasan wajib dan dialog konfirmasi. |
| **Eskalasi** | Membutuhkan tindakan atau masukan pihak lain. | Alasan wajib. |

Setelah memilih aksi, sistem menyediakan jendela **Urungkan** selama 10 detik sebelum aksi dikirim. Gunakan waktu ini untuk membatalkan salah klik. Keputusan terminal akan membuat kasus ditandai selesai/ditolak sesuai aksi dan tetap terekam dalam audit trail.

### Langkah 5 — high-alert dan Copilot

Jika terdapat temuan high-alert, **Setujui** memunculkan dialog yang meminta konfirmasi seluruh item sebelum diproses. Ini adalah pengaman agar item berisiko tinggi tidak terlewat.

Untuk bertanya pada AI, klik **Copilot** di kanan bawah. Pilih pertanyaan cepat atau ketik pertanyaan sendiri (maksimum 500 karakter), misalnya:

```text
Apa diskrepansi paling kritis pada kasus ini?
Apakah ada interaksi obat yang perlu diperhatikan?
Mengapa pasien ini mendapat prioritas tinggi?
Obat high-alert apa yang perlu konfirmasi?
```

Tekan `Enter` untuk mengirim atau `Shift+Enter` untuk baris baru. Copilot memberi label draf AI dan sumber jawaban; gunakan hanya sebagai dukungan telaah, bukan otorisasi klinis.

## 8. Mengisi BPMH

Menu **Form BPMH** adalah form riwayat obat. Pilih pasien aktif terlebih dahulu dari worklist pada alur UI klasik/sintetis. Ada dua cara memasukkan data:

### A. Mode Tabel

1. Klik **Tambah obat** untuk menambah baris.
2. Isi minimal **Nama obat** pada setiap baris yang akan disimpan.
3. Lengkapi bila tersedia: dosis, satuan (`mg`, `mcg`, `g`, `unit`, `mL`), frekuensi, rute (Oral/IV/SC/Inhalasi), sumber informasi, disposisi, dan alasan.
4. Pilih disposisi: **Dilanjutkan**, **Ditunda**, **Diganti**, atau **Dihentikan**.
5. Klik **Submit BPMH untuk analisis**.

### B. Mode Tempel Teks

1. Pilih **Mode Tempel Teks**.
2. Tempel satu obat per baris, misalnya:

```text
Warfarin 2 mg 1x sehari oral
Metformin 500 mg 2x sehari oral
```

3. Klik **Parse ke tabel**.
4. Periksa dan koreksi hasil parsing satu per satu; hasil tersebut draf, bukan data tervalidasi.
5. Submit BPMH setelah nama obat minimal terisi.

Manfaat BPMH: membangun daftar obat pra-admisi yang lebih lengkap, sehingga perbandingan dengan order admisi dan penemuan omission/duplication lebih dapat ditelusuri.

## 9. Audit, tutorial, dan pengaturan

### Audit Log

Pilih **Audit Log** untuk melihat waktu, aksi, pasien, pengguna, catatan, serta versi sumber model/rule. Akun ADMIN atau AUDITOR dapat menekan **Verifikasi Rantai Hash** untuk memeriksa integritas seluruh jejak audit. Hasil `Valid` berarti rantai yang diperiksa konsisten; hasil `Rusak` harus diinvestigasi sesuai tata kelola keamanan.

### Tutorial

Pilih **Tutorial** untuk navigasi terpandu: Worklist → BPMH → analisis → audit. Ini bermanfaat bagi demonstrator atau pengguna baru karena menekankan bahwa AI hanya membantu, sedangkan keputusan akhir berada pada apoteker.

### Pengaturan

Di **Pengaturan**, pengguna dapat melihat/mengedit daftar high-alert dan kapasitas review per bangsal. Fitur ini hanya prototipe lokal: perubahan disimpan pada memori browser selama sesi dan kembali semula ketika halaman direfresh. Tombol impor CSV/XLSX hanya menjalankan validasi simulasi nama file; tidak mengunggah atau menyimpan berkas ke server.

## 10. Pemeriksaan setelah instalasi dan pengujian

Jalankan pemeriksaan berikut dari root repositori:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_api.py tests/test_model.py

Set-Location web
npm run build
```

Checklist demo singkat:

1. `http://localhost:8000/health` merespons sukses.
2. `http://localhost:8000/docs` dapat dibuka.
3. Login dengan `apoteker1 / demo1234` berhasil.
4. Worklist menampilkan data demo.
5. Membuka satu kasus, melihat Temuan, mengisi SBAR, lalu menyimpan draf atau melakukan keputusan sesuai skenario demo.
6. Audit Log menunjukkan tindakan tersebut.
7. Login sebagai `admin` dan jalankan verifikasi rantai hash (opsional).

## 11. Troubleshooting

| Gejala | Pemeriksaan dan tindakan |
|---|---|
| Browser gagal memuat data atau login | Pastikan backend masih berjalan di port 8000, lalu buka `/health`. Pastikan frontend memakai `$env:VITE_DATA_MODE = "live"` sebelum `npm run dev`. |
| CORS error di browser | Pastikan `CORS_ALLOWED_ORIGINS` mencakup `http://localhost:5173`, lalu restart FastAPI. |
| Worklist kosong | Lihat log backend saat startup. Pada database kosong, seed demo seharusnya mengisi 10 skenario selama `AUTO_SEED_DEMO` tidak disetel `false`. |
| Copilot gagal | Alur utama tetap dapat digunakan. Periksa konfigurasi AI Gateway/Langflow/LLM dan kunci API; jangan memasukkan kunci ke frontend. |
| Model tidak termuat | Jalankan `scripts\validate_data_layout.py`, kemudian periksa artefak `models/` dan log startup API. Jangan mengganti model di `models/` dengan file dari `medrec_xgboost/` karena kontrak fiturnya berbeda. |
| Tampilan tidak berubah setelah mengedit Pengaturan | Itu perilaku prototype: perubahan hanya ada dalam sesi browser dan akan reset setelah refresh. |

## 12. Batas aman sebelum penggunaan klinis nyata

Sebelum pilot klinis atau produksi, lakukan setidaknya hal berikut:

1. Ganti semua secret, hapus akun demo, dan gunakan autentikasi/otorisasi institusional.
2. Batasi CORS hanya pada domain UI yang benar.
3. Terapkan tata kelola akses data, privasi, logging, backup, dan retensi sesuai kebijakan rumah sakit.
4. Validasi ingestion data pasien nyata, kalibrasi model, ambang prioritas, dan daftar high-alert secara lokal bersama tim klinis.
5. Uji prospektif alur kerja; pantau false negative, beban alert, keterlambatan SLA, dan drift model.
6. Pastikan semua keputusan klinis tetap dilakukan, didokumentasikan, dan dipertanggungjawabkan oleh apoteker.

