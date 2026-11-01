"""Backfill nama inisial sintetis untuk encounter lama yang belum punya nama.

Data simulasi PrioMed-Rec memakai inisial (mis. "S.W.") agar tidak menampilkan
identitas nyata. Script ini idempoten: hanya mengisi patient_name yang NULL/kosong.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.db.session import session_scope
from api.db.models import Encounter
from api.services.queue_service import _synthetic_initials


def main() -> None:
    updated = 0
    with session_scope() as session:
        rows = (
            session.query(Encounter)
            .filter((Encounter.patient_name.is_(None)) | (Encounter.patient_name == ""))
            .all()
        )
        for enc in rows:
            enc.patient_name = _synthetic_initials(enc.id)
            updated += 1
        session.commit()
    print(f"Backfilled {updated} encounter name(s).")


if __name__ == "__main__":
    sys.exit(main())
