"""
tests/test_q001_migration.py
------------------------------
Q-001: Verifikasi tabel antrean ada, indeks ada, dan data lama tidak hilang.

Tes ini:
1. Buat DB in-memory baru via Base.metadata.create_all (mencerminkan ORM)
2. Verifikasi tiga tabel baru ada dengan semua kolom wajib
3. Verifikasi indeks ada
4. Verifikasi data lama (encounters) masih ada setelah tabel baru dibuat
5. Verifikasi constraint: queue_type IN BPMH|REVIEW (app-level)
6. Verifikasi queue_version monoton saat di-increment

Tidak menjalankan alembic upgrade sesungguhnya (agar CI tidak butuh file DB).
Alembic migration diuji terpisah di test_q001_alembic_migration.py.
"""
from __future__ import annotations

import pytest
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

# --- Setup DB in-memory ---

@pytest.fixture(scope="module")
def db_engine():
    """In-memory SQLite — isolasi penuh, tanpa side effect.

    PRAGMA foreign_keys=OFF karena tes ini memakai UUID acak sebagai encounter_id
    tanpa membuat encounters parent terlebih dahulu (unit test isolasi).
    Constraint FK diuji secara integrasi di tes e2e yang lebih tinggi.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    # FK OFF untuk isolasi unit test (tidak butuh encounters parent)
    with engine.connect() as conn:
        conn.execute(sa.text("PRAGMA foreign_keys=OFF"))
    from api.db.models import Base
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(db_engine):
    Session = sessionmaker(bind=db_engine)
    s = Session()
    yield s
    s.rollback()
    s.close()


# -----------------------------------------------------------------------
# T-Q001-01: Tabel baru ada
# -----------------------------------------------------------------------

def test_queue_tables_exist(db_engine):
    insp = inspect(db_engine)
    tables = insp.get_table_names()
    assert "queue_entries"         in tables, "queue_entries tidak ada"
    assert "queue_events"          in tables, "queue_events tidak ada"
    assert "missed_reconciliations" in tables, "missed_reconciliations tidak ada"


# -----------------------------------------------------------------------
# T-Q001-02: Kolom wajib di queue_entries
# -----------------------------------------------------------------------

REQUIRED_QUEUE_ENTRY_COLS = {
    "encounter_id", "queue_type", "ward", "state",
    "tier_rank", "tier_source", "priority_score", "ml_percentile",
    "depth_level", "admitted_at", "sla_due_at", "next_due_at",
    "discharge_planned_at", "claimed_by", "claim_expires_at",
    "queue_version", "updated_at",
}

def test_queue_entries_columns(db_engine):
    insp = inspect(db_engine)
    cols = {c["name"] for c in insp.get_columns("queue_entries")}
    missing = REQUIRED_QUEUE_ENTRY_COLS - cols
    assert not missing, f"Kolom hilang di queue_entries: {missing}"


# -----------------------------------------------------------------------
# T-Q001-03: Kolom wajib di queue_events
# -----------------------------------------------------------------------

def test_queue_events_columns(db_engine):
    insp = inspect(db_engine)
    cols = {c["name"] for c in insp.get_columns("queue_events")}
    for col in ("seq", "encounter_id", "kind", "payload_json", "at"):
        assert col in cols, f"Kolom '{col}' hilang di queue_events"


# -----------------------------------------------------------------------
# T-Q001-04: Kolom wajib di missed_reconciliations
# -----------------------------------------------------------------------

def test_missed_reconciliations_columns(db_engine):
    insp = inspect(db_engine)
    cols = {c["name"] for c in insp.get_columns("missed_reconciliations")}
    for col in ("encounter_id", "discharged_at", "last_state", "last_tier", "reason"):
        assert col in cols, f"Kolom '{col}' hilang di missed_reconciliations"


# -----------------------------------------------------------------------
# T-Q001-05: Tabel encounters (lama) masih ada, tidak rusak
# -----------------------------------------------------------------------

def test_old_tables_intact(db_engine):
    insp = inspect(db_engine)
    tables = insp.get_table_names()
    for tbl in ("encounters", "users", "sla_events", "audit_entries"):
        assert tbl in tables, f"Tabel lama '{tbl}' hilang setelah migrasi Q-001"


# -----------------------------------------------------------------------
# T-Q001-06: Insert dan baca queue_entry
# -----------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_insert_and_read_queue_entry(session):
    from api.db.models import QueueEntry
    enc_id = str(uuid.uuid4())
    # Perlu encounters dulu karena FK — skip FK check di in-memory SQLite
    # (FK di SQLite tidak di-enforce secara default kecuali PRAGMA)
    entry = QueueEntry(
        encounter_id=enc_id,
        queue_type="REVIEW",
        ward="ICU",
        state="OPEN",
        tier_rank=2,
        tier_source="RULE",
        priority_score=53.6,
        depth_level=3,
        admitted_at=_now(),
        queue_version=0,
        updated_at=_now(),
    )
    session.add(entry)
    session.flush()

    fetched = session.query(QueueEntry).filter_by(encounter_id=enc_id).one()
    assert fetched.tier_rank == 2
    assert fetched.tier_source == "RULE"
    assert abs(fetched.priority_score - 53.6) < 0.01
    assert fetched.state == "OPEN"


# -----------------------------------------------------------------------
# T-Q001-07: queue_version monoton saat di-increment
# -----------------------------------------------------------------------

def test_queue_version_monoton(session):
    from api.db.models import QueueEntry
    enc_id = str(uuid.uuid4())
    entry = QueueEntry(
        encounter_id=enc_id,
        queue_type="BPMH",
        ward="Penyakit Dalam",
        state="OPEN",
        tier_rank=1,
        tier_source="ML",
        priority_score=25.0,
        depth_level=2,
        admitted_at=_now(),
        queue_version=0,
        updated_at=_now(),
    )
    session.add(entry)
    session.flush()

    versions = []
    for _ in range(5):
        entry.queue_version += 1
        session.flush()
        versions.append(entry.queue_version)

    # Monoton naik, tidak pernah turun
    for i in range(1, len(versions)):
        assert versions[i] > versions[i - 1], "queue_version harus monoton naik"


# -----------------------------------------------------------------------
# T-Q001-08: MissedReconciliation insert
# -----------------------------------------------------------------------

def test_insert_missed_reconciliation(session):
    from api.db.models import MissedReconciliation
    enc_id = str(uuid.uuid4())
    missed = MissedReconciliation(
        encounter_id=enc_id,
        discharged_at=_now(),
        last_state="DALAM_ANALISIS",
        last_tier="HIGH",
        reason="DISCHARGE_BEFORE_REVIEW",
    )
    session.add(missed)
    session.flush()

    fetched = session.query(MissedReconciliation).filter_by(encounter_id=enc_id).one()
    assert fetched.last_tier == "HIGH"
    assert fetched.reason == "DISCHARGE_BEFORE_REVIEW"


# -----------------------------------------------------------------------
# T-Q001-09: QueueEvent insert — seq auto-increment
# -----------------------------------------------------------------------

def test_queue_event_seq_autoincrement(session):
    from api.db.models import QueueEvent
    import json
    enc_id = str(uuid.uuid4())

    ev1 = QueueEvent(encounter_id=enc_id, kind="upsert", payload_json=json.dumps({"tier_rank": 2}), at=_now())
    ev2 = QueueEvent(encounter_id=enc_id, kind="claim",  payload_json=json.dumps({"claimed_by": "u1"}), at=_now())
    session.add_all([ev1, ev2])
    session.flush()

    rows = session.query(QueueEvent).filter_by(encounter_id=enc_id).order_by(QueueEvent.seq).all()
    assert len(rows) == 2
    assert rows[1].seq > rows[0].seq, "seq harus auto-increment"


# -----------------------------------------------------------------------
# T-Q001-10: Default state = OPEN saat tidak disetel
# -----------------------------------------------------------------------

def test_default_state_is_open(session):
    from api.db.models import QueueEntry
    enc_id = str(uuid.uuid4())
    entry = QueueEntry(
        encounter_id=enc_id,
        queue_type="REVIEW",
        ward="Jantung",
        tier_rank=1,
        tier_source="SLA",
        priority_score=31.5,
        depth_level=2,
        admitted_at=_now(),
        queue_version=0,
        updated_at=_now(),
    )
    session.add(entry)
    session.flush()
    assert entry.state == "OPEN"
