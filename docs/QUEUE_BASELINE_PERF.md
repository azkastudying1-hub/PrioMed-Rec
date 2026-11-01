# QUEUE_BASELINE_PERF.md — Baseline Performa Worklist

**Fase:** Q0.5  
**Tanggal:** 2026-10-29  
**Metode:** Direct SQLAlchemy query (bukan HTTP) — 5 ulangan, ambil rata-rata  
**Catatan:** OFFSET-based query + Python sort (kondisi *saat ini*, sebelum refactor keyset)  

## Hasil

| N entri terbuka | Dikembalikan | avg (ms) | min (ms) | max (ms) | P95 (ms) |
|:-:|:-:|:-:|:-:|:-:|:-:|
| 1,000 | 50 | 4.6 | 3.0 | 10.1 | 10.1 |
| 5,000 | 50 | 7.6 | 5.2 | 11.5 | 11.5 |

## Interpretasi

- Untuk demo ukuran S/M (≤300 entri terbuka), performa OFFSET query saat ini memadai.
- Untuk ukuran L/XL (2.000–5.000 entri), performa OFFSET + Python sort **tidak memadai** —
  halaman ke-2 bisa salah urut karena sort di Python hanya pada page tersebut.
- **Target Q-001:** ganti ke `queue_entries` terdenormalisasi + **keyset pagination**
  → diperkirakan < 50 ms untuk semua ukuran (indeks dioptimalkan).

## Target setelah Q-001..Q-005

| Operasi | Target P95 | Status |
|---------|-----------|--------|
| `GET /queue` (50 baris, keyset) | < 300 ms | ⏳ Diukur ulang setelah Q-005 |
| `POST /queue/next` (atomik) | < 200 ms | ⏳ Belum diimplementasikan |
| Tick batch 5.000 entri | < 800 ms | ⏳ Belum diimplementasikan |

> Semua angka di atas adalah **kondisi baseline sebelum implementasi Q-001..Q-012**.
> Akan diperbarui setelah setiap fase selesai.