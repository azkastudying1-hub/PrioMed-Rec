#!/usr/bin/env python3
"""Seed banyak pasien sintetis untuk demo antrean skala RS (rotasi/bergantian)."""
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.db.session import session_scope
from api.db.models import Base, Encounter, QueueEntry, User
from api.services.queue_service import _synthetic_initials
from sqlalchemy import inspect


def _now() -> datetime:
    return datetime.now(timezone.utc)


def seed(count: int = 100, prefix: str = "BULK", reset: bool = False) -> int:
    Base.metadata.create_all(__import__("api.db.session", fromlist=["engine"]).engine)
    created = 0
    rng = random.Random(42)
    wards = ["ICU", "Bedah", "Interna", "Anak", "Saraf"]
    tier_distribution = [2] * 20 + [1] * 30 + [0] * 50  # HIGH/MEDIUM/LOW

    with session_scope() as session:
        if reset:
            session.execute(__import__("sqlalchemy", fromlist=["text"]).text(
                "DELETE FROM queue_entries WHERE encounter_id LIKE :p"
            ), {"p": f"{prefix}-%"})
            session.execute(__import__("sqlalchemy", fromlist=["text"]).text(
                "DELETE FROM encounters WHERE id LIKE :p"
            ), {"p": f"{prefix}-%"})
            session.commit()

        for i in range(1, count + 1):
            enc_id = f"{prefix}-{i:04d}"
            exists = session.query(Encounter).filter(Encounter.id == enc_id).first()
            if exists:
                continue
            ward = rng.choice(wards)
            tier_rank = rng.choice(tier_distribution)
            tier_source = rng.choice(["ML", "RULE", "SLA"])
            priority_score = round(rng.uniform(0.1, 0.99), 4)
            admitted_hours_ago = rng.uniform(0, 8)
            admitted_at = (_now() - timedelta(hours=admitted_hours_ago)).isoformat()
            ml_score = round(rng.uniform(0.05, 0.95), 4)

            enc = Encounter(
                id=enc_id,
                patient_id=f"PAT-{enc_id}",
                patient_name=_synthetic_initials(enc_id),
                ward=ward,
                admitted_at=admitted_at,
                workflow_status="MENUNGGU_REVIEW",
                ml_score=ml_score,
            )
            session.add(enc)

            entry = QueueEntry(
                encounter_id=enc_id,
                queue_type="REVIEW",
                ward=ward,
                state="OPEN",
                tier_rank=tier_rank,
                tier_source=tier_source,
                priority_score=priority_score,
                depth_level=rng.choice([1, 2, 3]),
                admitted_at=admitted_at,
                queue_version=1,
                updated_at=_now().isoformat(),
            )
            session.add(entry)
            created += 1

        session.commit()

    print(f"Seeded {created} pasien bulk (prefix={prefix}).")
    return created


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--prefix", default="BULK")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    seed(args.count, args.prefix, args.reset)
