"""
scripts/seed_queue.py
----------------------
Isi antrean farmasi dengan data simulasi (QUEUE_PLAN §9) agar menu
"Antrean Farmasi" & "Command Center" langsung hidup saat demo.

Pasien di-admit ke Antrean A (BPMH) lewat servis antrean yang sama dengan API,
lalu sebagian BPMH-nya "diselesaikan" sehingga Antrean B (Telaah) juga berisi.

Pakai:
    python -m scripts.seed_queue                 # ukuran S (80 entri) bila antrean kosong
    python -m scripts.seed_queue --size M --reset
    python -m scripts.seed_queue --size S --bpmh-done 0.6 --max-age-hours 30

Label wajib: "Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS"
"""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone
from typing import Dict

SIM_LABEL = "Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS"


def seed_queue(
    size: str = "S",
    seed: int = 42,
    bpmh_done_fraction: float = 0.6,
    max_age_hours: float = 30.0,
    reset: bool = False,
    only_if_empty: bool = True,
) -> Dict[str, int]:
    """Kembalikan ringkasan {'admitted': n, 'review': m, 'bpmh': k}."""
    from api.db.models import (
        Base, Encounter, MissedReconciliation, QueueEntry, QueueEvent, StatusHistory,
    )
    from api.db.session import engine, session_scope
    from api.services.queue_service import admit_encounter, _entry_to_dict
    from api.services.queue_view_service import advance_encounter
    from priomedrec_core.queue_transitions import bpmh_submit
    from simulator.config import SEED_SIZES, SimulatorConfig
    from simulator.patient_generator import generate_patient_profile

    Base.metadata.create_all(engine)

    with session_scope() as session:
        existing = session.query(QueueEntry).count()
        if existing and only_if_empty and not reset:
            return {"admitted": 0, "review": 0, "bpmh": 0, "skipped": existing}
        if reset:
            sim_ids = [
                r[0] for r in session.query(QueueEntry.encounter_id).all()
            ]
            session.query(QueueEvent).delete()
            session.query(MissedReconciliation).delete()
            session.query(QueueEntry).delete()
            if sim_ids:
                session.query(StatusHistory).filter(
                    StatusHistory.encounter_id.in_(sim_ids)
                ).delete(synchronize_session=False)
                session.query(Encounter).filter(Encounter.id.in_(sim_ids)).delete(
                    synchronize_session=False
                )
            session.commit()

    cfg = SimulatorConfig(size=size, seed=seed)
    n_open = SEED_SIZES.get(size, SEED_SIZES["S"]).open_entries
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)

    admitted = review = 0
    with session_scope() as session:
        for _ in range(n_open):
            hours_ago = rng.uniform(0.3, max_age_hours)
            admitted_at = now - timedelta(hours=hours_ago)
            p = generate_patient_profile(rng, admitted_at=admitted_at, cfg=cfg)
            admit_encounter(
                session, p["encounter_id"], p["ward"], p["admitted_at"],
                ml_score=p["ml_score"], has_rule_finding=p["has_rule_finding"], now=now,
            )
            admitted += 1

            # sebagian BPMH sudah selesai → masuk Antrean B (Telaah)
            if rng.random() < bpmh_done_fraction:
                entry = session.query(QueueEntry).filter_by(
                    encounter_id=p["encounter_id"]
                ).first()
                has_rule = p["has_rule_finding"] or rng.random() < 0.10
                high_alert = rng.random() < 0.08
                updated, _ev = bpmh_submit(
                    _entry_to_dict(entry), has_rule_finding=has_rule,
                    is_high_alert=high_alert, ml_score=p["ml_score"], now=now,
                )
                entry.queue_type = "REVIEW"
                entry.state = "OPEN"
                entry.tier_rank = updated["tier_rank"]
                entry.tier_source = updated["tier_source"]
                entry.priority_score = updated["priority_score"]
                entry.sla_due_at = updated.get("sla_due_at")
                entry.next_due_at = updated.get("next_due_at")
                entry.queue_version = updated["queue_version"]
                entry.updated_at = updated["updated_at"]
                session.flush()
                advance_encounter(session, p["encounter_id"], "MENUNGGU_TELAAH")
                review += 1
        session.commit()

    return {"admitted": admitted, "review": review, "bpmh": admitted - review}


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed antrean farmasi (data simulasi)")
    ap.add_argument("--size", default="S", choices=["S", "M", "L", "XL"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--bpmh-done", type=float, default=0.6)
    ap.add_argument("--max-age-hours", type=float, default=30.0)
    ap.add_argument("--reset", action="store_true", help="hapus antrean lama dulu")
    args = ap.parse_args()
    print(f"[SIMULASI] {SIM_LABEL}")
    out = seed_queue(args.size, args.seed, args.bpmh_done, args.max_age_hours, args.reset)
    print(out)


if __name__ == "__main__":
    main()
