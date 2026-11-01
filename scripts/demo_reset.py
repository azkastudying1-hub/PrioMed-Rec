#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/demo_reset.py
----------------------
Reset + re-seed data demo PrioMed-Rec satu perintah.

Penggunaan:
    python scripts/demo_reset.py              # reset lalu seed ulang
    python scripts/demo_reset.py --no-reset   # seed saja tanpa hapus data lama

Setara dengan:
    python scripts/seed_demo.py --reset

Dipakai sebelum demo hackathon untuk memastikan data bersih.
Aman untuk dijalankan berulang kali -- idempoten.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Tambah root proyek ke path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Default DB path
_DEFAULT_DB = os.getenv("DB_PATH", "data/priomed.db")


def main():
    parser = argparse.ArgumentParser(description="Reset & seed ulang data demo PrioMed-Rec")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Seed tanpa menghapus data demo lama (idempoten -- skip yang sudah ada)",
    )
    parser.add_argument(
        "--db-path",
        default=_DEFAULT_DB,
        help="Path SQLite database (default: {})".format(_DEFAULT_DB),
    )
    args = parser.parse_args()

    os.environ.setdefault("DB_PATH", args.db_path)

    from scripts.seed_demo import seed

    do_reset = not args.no_reset
    if do_reset:
        print("[demo-reset] Menghapus data demo lama dan seed ulang...")
    else:
        print("[demo-reset] Seeding demo data (tanpa reset)...")

    seed(db_path=args.db_path, reset=do_reset)
    print()
    print("=" * 50)
    print("  DEMO SIAP")
    print("=" * 50)
    print()
    print("URL:")
    print("  API  : http://localhost:8000/docs")
    print("  Web  : http://localhost:8000/app   (atau http://localhost:5173 dev)")
    print()
    print("Login demo:")
    print("  apoteker1    / demo1234   -> PHARMACIST (akun utama demo)")
    print("  ttk1         / demo1234   -> TECHNICIAN")
    print("  koordinator1 / demo1234   -> COORDINATOR")
    print("  admin        / admin1234  -> ADMIN")
    print()
    print("Skenario yang siap:")
    print("  S1  - Tn. B.S.  HIGH  | warfarin omisi + bisoprolol omisi")
    print("  S2  - Ny. R.H.  HIGH  | DDI warfarin+aspirin + alergi silang")
    print("  S3  - Tn. K.W.  HIGH  | omisi insulin (wajib konfirmasi HA)")
    print("  S4  - Ny. M.S.  MED   | polypharmacy lansia, 2 diskrepansi Tier-2")
    print("  S5  - Tn. P.A.  MED   | skenario LLM fallback - template SBAR")
    print("  S6  - Ny. D.L.  MED   | skenario guardrail obat fiktif")
    print("  S7  - Tn. H.F.  HIGH  | SLA breach (>2 jam), heparin IV omisi")
    print("  S8  - Tn. J.R.  LOW   | tidak minum obat rutin - bersih")
    print("  S9  - Ny. A.N.  MED   | substitusi captopril-enalapril")
    print("  S10 - Ny. F.K.  MED   | bisoprolol omisi - APPROVE - audit hash")


if __name__ == "__main__":
    main()
