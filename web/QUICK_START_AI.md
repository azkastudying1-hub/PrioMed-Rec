# Quick Start: Mengaktifkan Analisis AI

## Status Saat Ini

⚠️ **Analisis AI belum aktif** karena LLM API key belum dikonfigurasi.

Sistem akan menampilkan **fallback report** (berbasis aturan) yang tetap informatif, tetapi tanpa narasi AI.

## Cara Mengaktifkan AI dalam 5 Menit

### Opsi 1: Groq (GRATIS, Recommended) ⭐

Groq adalah platform LLM gratis yang sangat cepat dan tidak memiliki batasan ketat.

**Langkah-langkah:**

1. **Daftar akun Groq** (gratis, tidak perlu kartu kredit):
   - Buka https://console.groq.com
   - Klik "Sign Up" atau login dengan Google/GitHub

2. **Buat API Key**:
   - Buka https://console.groq.com/keys
   - Klik "Create API Key"
   - Beri nama (misal: "priomed-local")
   - **Copy API key** yang muncul (dimulai dengan `gsk_`)

3. **Update file `.env`**:
   Buka file `.env` di root project, lalu uncomment dan isi:
   ```env
   LLM_PROVIDER=groq
   LLM_API_KEY=gsk_YOUR_ACTUAL_KEY_HERE
   LLM_MODEL_NAME=llama-3.3-70b-versatile
   LLM_BASE_URL=https://api.groq.com/openai/v1
   ```

4. **Restart backend**:
   ```bash
   # Stop backend yang sedang berjalan (Ctrl+C)
   # Lalu jalankan lagi:
   cd backend
   python -m uvicorn api.main:app --reload --port 8001
   ```

5. **Test**:
   - Buka http://localhost:5173
   - Login dan buat pasien di BPMH
   - Klik tombol **"Analisis AI"** di halaman analisis
   - Seharusnya muncul laporan AI yang detail

### Opsi 2: Google Gemini (GRATIS dengan Kuota Harian)

Gemini adalah LLM dari Google yang gratis dengan kuota harian.

**Langkah-langkah:**

1. **Dapatkan API Key**:
   - Buka https://aistudio.google.com/app/apikey
   - Login dengan akun Google
   - Klik "Create API Key"
   - **Copy API key** (dimulai dengan `AIza`)

2. **Update file `.env`**:
   ```env
   LLM_PROVIDER=gemini
   LLM_API_KEY=AIza_YOUR_ACTUAL_KEY_HERE
   LLM_MODEL_NAME=gemini-2.5-flash
   LLM_FALLBACK_MODEL=gemini-1.5-flash-8b
   ```

3. **Restart backend** (sama seperti di atas)

## Mode Tanpa AI

Jika tidak ingin menggunakan AI, sistem tetap berfungsi dengan fitur:

✅ **ML Prioritization** - Skor risiko berdasarkan 16 fitur
✅ **Rule Engine** - Deteksi diskrepansi obat otomatis
✅ **SBAR Draft** - Template laporan berbasis aturan
✅ **Safety Flags** - Deteksi obat high-alert, NTI, Beers PIM

## Troubleshooting

### Error: "API key tidak valid"
- Pastikan API key sudah benar (copy-paste tanpa spasi)
- Untuk Groq: key harus dimulai dengan `gsk_`
- Untuk Gemini: key harus dimulai dengan `AIza`

### Error: "Quota exceeded"
- Kuota Gemini habis → gunakan Groq sebagai fallback
- Tambahkan `LLM_GROQ_API_KEY` di `.env`

### Error: "LLM not configured"
- Pastikan `LLM_API_KEY` sudah diisi di `.env`
- Restart backend setelah mengubah `.env`

### Tetap error?
1. Periksa log backend di terminal
2. Lihat `docs/LLM_SETUP.md` untuk panduan lengkap
3. Buka issue di GitHub dengan menyertakan error log

## Keamanan

⚠️ **PENTING**:
- **JANGAN** commit file `.env` ke Git
- File `.env` sudah ada di `.gitignore`
- Gunakan API key yang berbeda untuk development dan production
- Untuk production, gunakan environment variables atau secret manager

## Model yang Tersedia

### Groq (Recommended)
- `llama-3.3-70b-versatile` - Model utama, sangat cepat dan capable
- `llama-3.1-8b-instant` - Lebih cepat untuk task sederhana
- `mixtral-8x7b-32768` - Context window lebih besar

### Gemini
- `gemini-2.5-flash` - Model utama, balance kecepatan dan kualitas
- `gemini-1.5-flash-8b` - Lebih cepat, untuk fallback
- `gemini-1.5-pro` - Lebih powerful, kuota terbatas

## Cost

- **Groq**: GRATIS, unlimited
- **Gemini**: GRATIS dengan kuota harian (sekitar 60 requests/hari untuk flash model)

## Support

Jika mengalami masalah:
1. Baca `docs/LLM_SETUP.md`
2. Cek log backend
3. Buat issue di GitHub dengan error message
