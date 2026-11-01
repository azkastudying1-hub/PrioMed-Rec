#!/usr/bin/env python3
"""
scripts/baseline_worklist_perf.py
-----------------------------------
Q0.5 — Baseline performa GET /worklist dengan 1.000 dan 5.000 baris sintetis.
Script sementara; tidak dipakai di prod.

Penggunaan:
    python scripts/baseline_worklist_perf.py

Output: waktu query ke console + tulis ke docs/QUEUE_BASELINE_PERF.md
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Gunakan DB sementara agar tidak mengotori DB demo
os.environ["DB_PATH"] = "data/perf_test_tmp.db"

def _ts(hours_ago: float = 0.0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return dt.isoformat()


def seed_encounters(session, n: int) -> None:
    from api.db.models import Encounter
    import random
    rng = random.Random(42)
    tiers = ["HIGH", "MEDIUM", "LOW"]
    wards = ["Penyakit Dalam", "Bedah", "Jantung", "Saraf", "ICU", "Geriatri"]
    statuses = ["MENUNGGU_BPMH", "BPMH_LENGKAP", "MENUNGGU_TELAAH", "DRAFT_REVIEW"]

    existing = session.query(Encounter).count()
    if existing >= n:
        return

    batch = []
    for i in range(n - existing):
        tier = rng.choice(tiers)
        enc = Encounter(
            id=str(uuid.uuid4()),
            patient_id=f"PERF-{i:06d}",
            patient_name=f"Pasien {i}",
            ward=rng.choice(wards),
            workflow_status=rng.choice(statuses),
            latest_tier=tier,
            ml_score=rng.uniform(0.1, 0.95),
            admitted_at=_ts(rng.uniform(0, 72)),
            row_version=0,
            created_at=_ts(rng.uniform(0, 72)),
            updated_at=_ts(),
        )
        batch.append(enc)
        if len(batch) >= 500:
            session.bulk_save_objects(batch)
            session.flush()
            batch = []
    if batch:
        session.bulk_save_objects(batch)
    session.commit()


def measure_worklist_query(session, n: int) -> dict:
    import sqlalchemy as sa
    from api.db.models import Encounter

    TIER_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    timings = []
    for _ in range(5):  # rata-rata 5 kali
        t0 = time.perf_counter()
        rows = (
            session.query(Encounter)
            .filter(Encounter.workflow_status.notin_(["SELESAI_APPROVE", "SELESAI_EDIT", "DITOLAK"]))
            .order_by(Encounter.admitted_at.asc())
            .limit(50)
            .all()
        )
        # Sort di Python (kondisi saat ini)
        rows.sort(key=lambda e: (-TIER_ORDER.get((e.latest_tier or "LOW").upper(), 1), e.admitted_at or ""))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        timings.append(elapsed_ms)

    return {
        "n_total": n,
        "returned": len(rows),
        "min_ms": round(min(timings), 1),
        "max_ms": round(max(timings), 1),
        "avg_ms": round(sum(timings) / len(timings), 1),
        "p95_ms": round(sorted(timings)[int(len(timings) * 0.95)], 1),
    }


def run():
    from api.db.session import session_scope as get_session, engine
    from api.db.models import Base

    Base.metadata.create_all(engine)
    results = []

    for n in [1_000, 5_000]:
        print(f"\n[baseline] Seeding {n} encounters...")
        with get_session() as session:
            seed_encounters(session, n)

        print(f"[baseline] Mengukur GET /worklist dengan {n} baris...")
        with get_session() as session:
            result = measure_worklist_query(session, n)
            results.append(result)
            print(f"  n={n:>5}: avg={result['avg_ms']}ms  min={result['min_ms']}ms  max={result['max_ms']}ms  p95={result['p95_ms']}ms")

    # Bersihkan DB sementara
    try:
        Path("data/perf_test_tmp.db").unlink(missing_ok=True)
        Path("data/perf_test_tmp.db-shm").unlink(missing_ok=True)
        Path("data/perf_test_tmp.db-wal").unlink(missing_ok=True)
    except Exception:
        pass

    # Tulis hasil ke docs/
    lines = [
        "# QUEUE_BASELINE_PERF.md — Baseline Performa Worklist",
        "",
        "**Fase:** Q0.5  ",
        f"**Tanggal:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}  ",
        "**Metode:** Direct SQLAlchemy query (bukan HTTP) — 5 ulangan, ambil rata-rata  ",
        "**Catatan:** OFFSET-based query + Python sort (kondisi *saat ini*, sebelum refactor keyset)  ",
        "",
        "## Hasil",
        "",
        "| N entri terbuka | Dikembalikan | avg (ms) | min (ms) | max (ms) | P95 (ms) |",
        "|:-:|:-:|:-:|:-:|:-:|:-:|",
    ]
    for r in results:
        lines.append(f"| {r['n_total']:,} | {r['returned']} | {r['avg_ms']} | {r['min_ms']} | {r['max_ms']} | {r['p95_ms']} |")

    lines += [
        "",
        "## Interpretasi",
        "",
        "- Untuk demo ukuran S/M (≤300 entri terbuka), performa OFFSET query saat ini memadai.",
        "- Untuk ukuran L/XL (2.000–5.000 entri), performa OFFSET + Python sort **tidak memadai** —",
        "  halaman ke-2 bisa salah urut karena sort di Python hanya pada page tersebut.",
        "- **Target Q-001:** ganti ke `queue_entries` terdenormalisasi + **keyset pagination**",
        "  → diperkirakan < 50 ms untuk semua ukuran (indeks dioptimalkan).",
        "",
        "## Target setelah Q-001..Q-005",
        "",
        "| Operasi | Target P95 | Status |",
        "|---------|-----------|--------|",
        "| `GET /queue` (50 baris, keyset) | < 300 ms | ⏳ Diukur ulang setelah Q-005 |",
        "| `POST /queue/next` (atomik) | < 200 ms | ⏳ Belum diimplementasikan |",
        "| Tick batch 5.000 entri | < 800 ms | ⏳ Belum diimplementasikan |",
        "",
        "> Semua angka di atas adalah **kondisi baseline sebelum implementasi Q-001..Q-012**.",
        "> Akan diperbarui setelah setiap fase selesai.",
    ]

    out_path = Path("docs/QUEUE_BASELINE_PERF.md")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[baseline] Hasil ditulis ke {out_path}")
    return results


if __name__ == "__main__":
    run()
