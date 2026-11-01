# Bugfix Requirements Document

## Introduction

Bug terjadi ketika pengguna mencoba login ke sistem PrioMed-Rec dan mendapatkan pesan error "Gagal masuk" serta "Sesi habis. Silakan login kembali." Pesan "sesi habis" tidak sesuai untuk proses login awal karena seharusnya hanya muncul ketika sesi yang aktif sudah kedaluwarsa. Bug ini menyebabkan kebingungan pengguna dan menghambat akses ke sistem.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN pengguna mencoba login dengan kredensial yang tidak valid THEN sistem menampilkan pesan error "Gagal masuk" dengan detail "Sesi habis. Silakan login kembali" (pesan yang tidak sesuai)
1.2 WHEN endpoint `/auth/login` mengembalikan status 401 (kredensial salah) THEN logika auto-refresh token di apiClient.ts mencoba melakukan refresh token (yang tidak mungkin karena belum ada sesi)
1.3 WHEN auto-refresh token gagal untuk endpoint login THEN sistem melemparkan error "Sesi habis. Silakan login kembali" alih-alih menggunakan pesan error dari backend ("Username atau password salah")
1.4 WHEN pengguna sudah memiliki sesi aktif yang kedaluwarsa DAN mencoba mengakses endpoint yang memerlukan autentikasi THEN sistem menampilkan pesan "Sesi habis. Silakan login kembali" (perilaku yang benar)

### Expected Behavior (Correct)

2.1 WHEN pengguna mencoba login dengan kredensial yang valid THEN sistem SHALL mengautentikasi pengguna dan memberikan akses ke dashboard tanpa error
2.2 WHEN pengguna mencoba login dengan kredensial yang tidak valid THEN sistem SHALL menampilkan pesan error spesifik "Username atau password salah" (dari backend) tanpa menyebutkan "sesi habis"
2.3 WHEN endpoint `/auth/login` mengembalikan status 401 THEN logika auto-refresh token di apiClient.ts SHALL dilewati (skip) karena belum ada sesi untuk di-refresh
2.4 WHEN auto-refresh token di-trigger untuk endpoint selain `/auth/login` DAN refresh berhasil THEN sistem SHALL melanjutkan request asli dengan token yang baru
2.5 WHEN auto-refresh token di-trigger untuk endpoint selain `/auth/login` DAN refresh gagal THEN sistem SHALL menampilkan pesan "Sesi habis. Silakan login kembali"

### Unchanged Behavior (Regression Prevention)

3.1 WHEN pengguna sudah login dan melakukan aktivitas normal THEN sistem SHALL CONTINUE TO menjaga sesi aktif selama 15 menit (sesuai konfigurasi JWT_ACCESS_EXPIRE_MINUTES)
3.2 WHEN pengguna idle selama 30 menit THEN sistem SHALL CONTINUE TO mengunci sesi (idle lock) sesuai implementasi existing
3.3 WHEN terjadi error koneksi jaringan selama login THEN sistem SHALL CONTINUE TO menampilkan pesan "Gagal terhubung ke server. Periksa koneksi Anda."
3.4 WHEN backend mengembalikan error 401 untuk endpoint selain login DAN token refresh masih valid THEN sistem SHALL CONTINUE TO mencoba refresh token secara otomatis