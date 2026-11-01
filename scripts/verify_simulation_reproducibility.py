"""
scripts/verify_simulation_reproducibility.py
--------------------------------------------
Menjalankan simulasi 24 jam virtual dua kali dengan seed yang sama (--seed 42),
lalu memverifikasi bahwa kedua run menghasilkan metrik dan statistik yang identik.

LABEL WAJIB:
  "Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS"
"""
import sys
import os
import json

# Setup import path
sys.path.insert(0, os.path.abspath("."))

from simulator.config import SimulatorConfig
from simulator.run import run
import api.db.models
from api.db.session import Base, engine

SIMULATION_LABEL = "[SIMULASI] Data simulasi - parameter berbasis asumsi, belum dikalibrasi dengan RS"

def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def main():
    print("=" * 70)
    print("UJI DETERMINISTIK SIMULATOR: 2x 24 Jam Virtual dengan Seed Sama (42)")
    print(SIMULATION_LABEL)
    print("=" * 70)

    # Konfigurasi simulasi: 24 jam virtual pada kecepatan 2880x (30 detik per run)
    cfg1 = SimulatorConfig(
        size="S",
        speed=120.0,
        scenario="normal",
        seed=42,
        deterministic=True,
        max_virtual_hours=24.0,
        verbose=False,
    )

    print("\n--- RESET DATABASE & JALANKAN RUN 1 (Seed 42) ---")
    reset_db()
    res1 = run(cfg1)

    cfg2 = SimulatorConfig(
        size="S",
        speed=120.0,
        scenario="normal",
        seed=42,
        deterministic=True,
        max_virtual_hours=24.0,
        verbose=False,
    )

    print("\n--- RESET DATABASE & JALANKAN RUN 2 (Seed 42) ---")
    reset_db()
    res2 = run(cfg2)

    print("\n" + "=" * 70)
    print("PERBANDINGAN HASIL RUN 1 VS RUN 2")
    print("=" * 70)

    keys = sorted(list(set(res1.keys()) | set(res2.keys())))
    mismatch = False
    for k in keys:
        v1 = res1.get(k, 0)
        v2 = res2.get(k, 0)
        match = "OK (IDENTIK)" if v1 == v2 else "DIFF (BERBEDA)"
        if v1 != v2:
            mismatch = True
        print(f"  {k:22s} : Run1 = {v1:4d} | Run2 = {v2:4d} | {match}")

    print("-" * 70)
    if not mismatch:
        print("HASIL: 100% REPRODUSIBEL DAN IDENTIK DENGAN SEED SAMA! [LULUS]")
        print(SIMULATION_LABEL)
        with open("D:/tmp/sim_reproducibility.json", "w") as f:
            json.dump({"run1": res1, "run2": res2, "status": "IDENTICAL"}, f, indent=2)
        sys.exit(0)
    else:
        print("HASIL: Ditemukan perbedaan antar run!")
        sys.exit(1)

if __name__ == "__main__":
    main()
