# Panduan Setup LLM untuk PrioMed-Rec

## Masalah Umum

Error `Cannot read properties of undefined (reading 'map')` terjadi karena:
1. API key LLM tidak valid atau belum diset
2. Response dari API tidak sesuai format yang diharapkan
3. Kuota LLM habis

## Solusi Cepat: Gunakan Groq (GRATIS)

Groq menyediakan API LLM gratis yang sangat cepat tanpa batas ketat. Ini adalah pilihan terbaik untuk testing dan development.

### Langkah-langkah Setup Groq

1. **Daftar akun Groq (gratis)**:
   - Buka https://console.groq.com
   - Klik "Sign Up" atau "Login with Google/GitHub"
   - Tidak perlu kartu kredit

2. **Buat API Key**:
   - Setelah login, buka https://console.groq.com/keys
   - Klik "Create API Key"
   - Beri nama (misal: "priomed-rec-dev")
   - Copy API key yang muncul (dimulai dengan `gsk_`)

3. **Update file `.env`**:
   Buka file `.env` di root project dan ubah menjadi:
   
   ```env
   # Gunakan Groq sebagai provider utama (GRATIS dan CEPAT)
   LLM_PROVIDER=groq
   LLM_API_KEY=gsk_YOUR_ACTUAL_GROQ_API_KEY_HERE
   LLM_MODEL_NAME=llama-3.3-70b-versatile
   LLM_BASE_URL=https://api.groq.com/openai/v1

   # Fallback configuration
   LLM_GROQ_API_KEY=gsk_YOUR_ACTUAL_GROQ_API_KEY_HERE
   LLM_GROQ_MODEL=llama-3.3-70b-versatile
   ```

4. **Restart backend**:
   ```bash
   # Hentikan backend yang sedang berjalan (Ctrl+C)
   # Lalu jalankan kembali
   cd backend
   python -m uvicorn api.main:app --reload --port 8001
   ```

## Alternatif: Google Gemini

Jika ingin menggunakan Gemini:

1. **Dapatkan API Key Gemini (gratis)**:
   - Buka https://aistudio.google.com/app/apikey
   - Klik "Create API Key"
   - Pilih project atau buat baru
   - Copy API key

2. **Update `.env`**:
   ```env
   LLM_PROVIDER=gemini
   LLM_API_KEY=AIza YOUR_ACTUAL_GEMINI_API_KEY_HERE
   LLM_MODEL_NAME=gemini-2.5-flash
   
   # Tambahkan fallback model untuk menghindari kuota habis
   LLM_FALLBACK_MODEL=gemini-1.5-flash-8b
   LLM_GROQ_API_KEY=gsk_YOUR_GROQ_KEY_AS_BACKUP
   ```

## Verifikasi Setup

Setelah mengupdate `.env`, test apakah LLM berfungsi:

```bash
# Test via API
curl -X POST http://localhost:8001/api/v1/ai/health

# Atau lihat log backend saat tombol "Analisis AI" ditekan
# Seharusnya ada output: "[LLM] ✓ Used Groq fallback: llama-3.3-70b-versatile"
```

## Troubleshooting

### Error: "LLM_API_KEY not set in .env"
- Pastikan file `.env` ada di root project
- Pastikan ada baris `LLM_API_KEY=gsk_...`
- Restart backend setelah mengubah `.env`

### Error: "401 Unauthorized" / "Invalid API Key"
- Periksa API key sudah benar (copy-paste tanpa spasi)
- Untuk Groq, key harus dimulai dengan `gsk_`
- Untuk Gemini, key harus dimulai dengan `AIza`

### Error: "429 Quota Exceeded"
- Kuota Gemini harian habis → gunakan Groq sebagai fallback
- Tambahkan `LLM_GROQ_API_KEY` di `.env`

### Error: "Cannot read properties of undefined"
- Sudah diperbaiki di kode frontend (v2024.11)
- Pastikan menggunakan kode terbaru
- Jika masih error, periksa console browser untuk detail error

## Model yang Tersedia

### Groq (Recommended - Gratis & Cepat)
- `llama-3.3-70b-versatile` - Model utama, sangat cepat
- `llama-3.1-8b-instant` - Lebih cepat, untuk task sederhana
- `mixtral-8x7b-32768` - Alternatif dengan context lebih besar

### Gemini (Gratis dengan Kuota Harian)
- `gemini-2.5-flash` - Model utama
- `gemini-1.5-flash-8b` - Fallback yang lebih kecil
- `gemini-1.5-pro` - Model lebih powerful (kuota terbatas)

## Mode Tanpa LLM

Jika tidak ingin menggunakan LLM sama sekali, sistem akan otomatis menampilkan laporan berbasis aturan (rule-based fallback) yang masih informatif tanpa AI.

Untuk menonaktifkan LLM sepenuhnya:
```env
EXECUTION_MODE=direct_only
# Hapus atau kosongkan LLM_API_KEY
```
