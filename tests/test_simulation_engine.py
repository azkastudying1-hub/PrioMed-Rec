"""
tests/test_simulation_engine.py
-------------------------------
Uji engine replay CSV (demo): prediksi XGBoost asli + rule engine asli +
penulisan antrean, transisi BPMH→REVIEW, dan eskalasi SLA.

Semua test memakai SQLite temporer dan CSV kecil — tidak menyentuh
`data/priomed.db` maupun dataset produksi.
"""
from __future__ import annotations

import csv
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.db.models import Base, Encounter, QueueEntry, QueueEvent, SlaEvent
from api.services.simulation_service import (
    MODEL_FEATURES,
    SimulationDataset,
    SimulationEngine,
    _priority_for,
    _run_rules,
    scaled_queue_config,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FEATURES = {
    "age": 72.0,
    "age_65_plus": 1.0,
    "gender_encoded": 1.0,
    "polypharmacy_flag": 1.0,
    "high_alert_flag": 1.0,
    "high_alert_count": 2.0,
    "active_condition_count": 8.0,
    "prior_encounter_count": 12.0,
    "allergy_count": 0.0,
    "has_drug_allergy": 0.0,
}


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session_scope(engine):
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    @contextmanager
    def _scope():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return _scope


def _write_dataset(tmp_path: Path) -> Path:
    """CSV model-ready kecil: 3 encounter (duplikasi, omisi, tanpa diskrepansi)."""
    path = tmp_path / "model_ready.csv"
    header = ["encounter_id", "patient_id", "has_discrepancy", *MODEL_FEATURES]
    rows = [
        ("E-DUP", "P-1", 1, *[FEATURES[k] for k in MODEL_FEATURES]),
        ("E-OMIT", "P-2", 1, *[FEATURES[k] for k in MODEL_FEATURES]),
        ("E-NONE", "P-3", 0, *[FEATURES[k] for k in MODEL_FEATURES]),
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def _write_cases(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic_cases.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "encounter_id",
                "baseline_medications",
                "admission_medications",
                "mutation_type",
            ]
        )
        # Warfarin muncul sekali, lalu digandakan oleh loader → duplikasi nyata.
        writer.writerow(["E-DUP", "Warfarin 5 MG Oral Tablet", "Warfarin 5 MG Oral Tablet", "DUPLICATION"])
        writer.writerow(["E-OMIT", "Metformin 500 MG Oral Tablet", "", "OMISSION"])
        writer.writerow(["E-NONE", "Amlodipine 5 MG Oral Tablet", "Amlodipine 5 MG Oral Tablet", "NONE"])
    return path


@pytest.fixture()
def dataset(tmp_path: Path) -> SimulationDataset:
    return SimulationDataset(
        dataset_path=_write_dataset(tmp_path),
        cases_path=_write_cases(tmp_path),
    ).load()


# ---------------------------------------------------------------------------
# Dataset & rule engine
# ---------------------------------------------------------------------------

def test_dataset_reconstructs_duplication_and_omission(dataset):
    assert len(dataset) == 3
    by_id = {p.encounter_id: p for p in dataset.rows}

    dup = by_id["E-DUP"]
    assert dup.mutation_type == "DUPLICATION"
    # Loader menggandakan daftar admission agar rule duplikasi menyala.
    assert len(dup.admission_medications) == 2
    assert dup.admission_medications[0] == dup.admission_medications[1]

    omit = by_id["E-OMIT"]
    assert omit.mutation_type == "OMISSION"
    assert omit.admission_medications == ()

    none = by_id["E-NONE"]
    assert none.mutation_type == "NONE"


def test_rule_engine_flags_duplication_and_omission(dataset):
    by_id = {p.encounter_id: p for p in dataset.rows}

    dup_flags = _run_rules(by_id["E-DUP"])
    assert any(f["flag_type"] == "POTENTIAL_DUPLICATION" for f in dup_flags)

    omit_flags = _run_rules(by_id["E-OMIT"])
    assert any(
        f["flag_type"].endswith("OMISSION") for f in omit_flags
    ), omit_flags

    none_flags = _run_rules(by_id["E-NONE"])
    assert none_flags == []


def test_priority_uses_real_model_score_and_rule_floor(dataset):
    patient = {p.encounter_id: p for p in dataset.rows}["E-DUP"]

    from src.models.predict import load_metadata, load_model, load_thresholds, predict_single
    from api.services.simulation_service import MODEL_DIR

    model = load_model(str(MODEL_DIR / "priomed_prioritization_model.pkl"))
    thresholds = load_thresholds(str(MODEL_DIR / "thresholds.json"))
    metadata = load_metadata(str(MODEL_DIR / "metadata.json"))
    pred = predict_single(
        feature_dict={**patient.features, "encounter_id": patient.encounter_id},
        model=model,
        thresholds=thresholds,
        metadata=metadata,
    )
    assert 0.0 <= pred["risk_probability"] <= 1.0

    priority = _priority_for(patient, pred["risk_probability"], scaled_queue_config(0.0025))
    # Warfarin = high-alert → lantai aturan HIGH (ADR-21).
    assert priority["has_rule_finding"] is True
    assert priority["final_tier"] == "HIGH"
    assert priority["rules_floor"] == "HIGH"
    assert priority["discrepancy_counts"]["tier1"] >= 1


# ---------------------------------------------------------------------------
# Engine: antrean + BPMH → REVIEW
# ---------------------------------------------------------------------------

def _engine(dataset, session_scope) -> SimulationEngine:
    eng = SimulationEngine(session_scope_factory=session_scope)
    eng._dataset = dataset
    eng._cfg = scaled_queue_config(0.0025)
    eng._status.max_patients = len(dataset)
    eng._status.dataset_rows = len(dataset)
    return eng


def test_engine_admits_then_moves_to_review(dataset, session_scope):
    eng = _engine(dataset, session_scope)

    first = eng._step_once()
    assert first is not None and first["event"] == "admitted"

    # Dua tick cukup: pasien pertama selesai BPMH, pasien berikutnya masuk.
    for _ in range(2):
        eng._step_once()

    status = eng.status()
    assert status["errors"] == 0
    assert status["admitted"] >= 1
    assert status["bpmh_completed"] >= 1

    with session_scope() as session:
        entries = session.query(QueueEntry).all()
        assert entries, "queue_entries harus terisi"
        assert all(e.state in ("OPEN", "CLAIMED") for e in entries)
        # Semua yang BPMH-nya selesai sudah di Antrean B.
        review = [e for e in entries if e.queue_type == "REVIEW"]
        assert review, "minimal satu entri harus pindah ke REVIEW"
        assert session.query(QueueEvent).count() > 0
        assert session.query(Encounter).count() == len(entries)


def test_no_orphan_entries_or_duplicate_encounters(dataset, session_scope):
    eng = _engine(dataset, session_scope)
    for _ in range(8):
        eng._step_once()

    with session_scope() as session:
        entries = session.query(QueueEntry).all()
        encounters = session.query(Encounter).all()
        entry_ids = {e.encounter_id for e in entries}
        encounter_ids = {e.id for e in encounters}

        assert len(entry_ids) == len(entries), "tidak boleh ada duplikat queue_entry"
        assert entry_ids == encounter_ids, "setiap queue_entry harus punya encounter"
        assert eng.status()["admitted"] == len(entries)


# ---------------------------------------------------------------------------
# Eskalasi SLA
# ---------------------------------------------------------------------------

def test_sla_escalation_raises_tier_and_writes_event(dataset, session_scope):
    eng = _engine(dataset, session_scope)
    eng._step_once()

    past = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    with session_scope() as session:
        entry = session.query(QueueEntry).first()
        entry.tier_rank = 0
        entry.tier_source = "ML"
        entry.next_due_at = past
        session.flush()

    escalated = eng._escalate_due(datetime.now(timezone.utc))
    assert escalated == 1

    with session_scope() as session:
        entry = session.query(QueueEntry).first()
        assert entry.tier_rank == 1
        assert entry.tier_source == "SLA"
        assert session.query(SlaEvent).count() == 1
        promote = (
            session.query(QueueEvent)
            .filter(QueueEvent.kind == "promote")
            .count()
        )
        assert promote >= 1


def test_tier_never_drops_below_rule_floor(dataset, session_scope):
    eng = _engine(dataset, session_scope)
    eng._step_once()

    with session_scope() as session:
        entry = session.query(QueueEntry).first()
        entry.tier_rank = 2
        entry.tier_source = "RULE"
        session.flush()

    # Eskalasi tidak boleh menurunkan tier; hanya menaikkan (maks HIGH).
    eng._escalate_due(datetime.now(timezone.utc))

    with session_scope() as session:
        entry = session.query(QueueEntry).first()
        assert entry.tier_rank == 2
        assert entry.tier_source == "RULE"
