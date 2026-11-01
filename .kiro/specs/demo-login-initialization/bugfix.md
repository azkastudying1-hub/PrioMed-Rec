# Bugfix Requirements: Demo Login Initialization

## Introduction

Pengguna mengalami kebingungan saat mencoba login untuk pertama kali setelah clone project. Meskipun backend mengembalikan error 401 yang valid ("Username atau password salah"), pengguna tidak menyadari bahwa database perlu di-seed terlebih dahulu dengan data demo sebelum dapat login. Masalah ini adalah issue inisialisasi setup, bukan bug di authentication code. Backend sudah bekerja dengan benar, namun flow setup awal tidak jelas atau tidak otomatis.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN pengguna pertama kali setup project (setelah clone) dan mencoba login dengan credentials demo (apt-01 / demo1234) THEN database SQLite masih kosong, user demo tidak tersedia
1.2 WHEN backend menerima login request untuk user yang tidak ada di database THEN mengembalikan error 401 "Username atau password salah" tanpa penjelasan tentang database kosong
1.3 WHEN pengguna membaca dokumentasi setup project THEN dokumentasi tidak menjelaskan langkah mandatory untuk seed database sebelum login attempt

### Expected Behavior (Correct)

2.1 WHEN pengguna pertama kali setup project THEN dokumentasi atau setup guide SHOULD clearly menginstruksikan untuk menjalankan `python scripts/seed_demo.py` sebelum mencoba login
2.2 WHEN pengguna mencoba login dengan demo credentials ke database kosong THEN sistem SHOULD memberikan pesan error yang informatif menjelaskan bahwa demo data belum tersedia dan perlu menjalankan seed script
2.3 WHEN pengguna menjalankan seed script dengan sukses THEN database SHOULD ter-initialize dengan user demo (apt-01 / demo1234) dan semua data demo yang diperlukan

### Unchanged Behavior (Regression Prevention)

3.1 WHEN pengguna login dengan valid credentials (setelah database ter-seed) THEN sistem SHOULD CONTINUE TO authenticate user dengan benar dan return valid JWT token
3.2 WHEN pengguna login dengan invalid credentials (wrong password atau non-existent user) THEN sistem SHOULD CONTINUE TO return 401 error untuk security reasons (tidak mengungkap apakah username exists)
3.3 WHEN seed script dijalankan pada database yang sudah memiliki data THEN sistem SHOULD CONTINUE TO handle gracefully (tidak crash atau corrupt data)
