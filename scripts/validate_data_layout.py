"""Non-destructive data-layout checks for PrioMed-Rec."""
from __future__ import annotations

from pathlib import Path
import csv
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "data/processed/model_ready.csv": {"encounter_id", "patient_id", "has_discrepancy"},
    "data/processed/feature_matrix.csv": {"encounter_id", "age"},
    "data/drug_risk_lookup.csv": {"drug_name", "high_alert", "nti", "beers_pim"},
}

def columns(path: Path) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return set(next(csv.reader(file)))

def main() -> int:
    failed = False
    for relative, required in EXPECTED.items():
        path = ROOT / relative
        if not path.exists():
            print(f"FAIL  {relative}: file missing")
            failed = True
            continue
        missing = required - columns(path)
        if missing:
            print(f"FAIL  {relative}: missing columns {sorted(missing)}")
            failed = True
        else:
            print(f"PASS  {relative}")
    print("No files were modified.")
    return int(failed)

if __name__ == "__main__":
    sys.exit(main())
