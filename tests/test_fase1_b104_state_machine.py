"""
tests/test_fase1_b104_state_machine.py
----------------------------------------
Tes unit untuk B-104: case state machine transitions.
"""
import pytest
from fastapi import HTTPException


def _make_encounter(status="MENUNGGU_TELAAH"):
    """Create a mock Encounter-like object."""
    class MockEnc:
        id = "enc-test-001"
        workflow_status = status
        row_version = 0
        updated_at = None

    return MockEnc()


def _make_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from api.db.models import Base
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_valid_transition_menunggu_to_draft():
    from api.services.case_state_service import transition
    session = _make_session()
    enc = _make_encounter("MENUNGGU_TELAAH")
    result = transition(session, enc, "DRAFT_REVIEW", actor_id="u1", check_high_alert=False)
    assert result.workflow_status == "DRAFT_REVIEW"
    session.close()


def test_valid_transition_draft_to_approve():
    from api.services.case_state_service import transition
    session = _make_session()
    enc = _make_encounter("DRAFT_REVIEW")
    result = transition(session, enc, "SELESAI_APPROVE", actor_id="u1", check_high_alert=False)
    assert result.workflow_status == "SELESAI_APPROVE"
    session.close()


def test_invalid_transition_raises_422():
    from api.services.case_state_service import transition
    session = _make_session()
    enc = _make_encounter("MENUNGGU_BPMH")
    with pytest.raises(HTTPException) as exc_info:
        transition(session, enc, "SELESAI_APPROVE", actor_id="u1", check_high_alert=False)
    assert exc_info.value.status_code == 422
    session.close()


def test_reason_required_for_reject():
    from api.services.case_state_service import transition
    session = _make_session()
    enc = _make_encounter("DRAFT_REVIEW")
    with pytest.raises(HTTPException) as exc_info:
        transition(session, enc, "DITOLAK", actor_id="u1", reason=None, check_high_alert=False)
    assert exc_info.value.status_code == 422
    assert "Alasan wajib" in exc_info.value.detail
    session.close()


def test_reason_provided_for_reject_ok():
    from api.services.case_state_service import transition
    session = _make_session()
    enc = _make_encounter("DRAFT_REVIEW")
    result = transition(session, enc, "DITOLAK", actor_id="u1", reason="Resep tidak sesuai", check_high_alert=False)
    assert result.workflow_status == "DITOLAK"
    session.close()


def test_high_alert_blocks_approve():
    """APPROVE harus ditolak jika ada diskrepansi high-alert belum dikonfirmasi (S3 scenario)."""
    from api.services.case_state_service import transition
    from api.db.models import Discrepancy
    import uuid

    session = _make_session()
    enc_id = "enc-ha-001"

    # Create mock encounter row (we add directly to the mock)
    from api.db.models import Encounter
    enc_orm = Encounter(
        id=enc_id, patient_id="P001", workflow_status="DRAFT_REVIEW",
        admitted_at="2025-01-01T00:00:00+00:00", row_version=0,
        created_at="2025-01-01T00:00:00+00:00", updated_at="2025-01-01T00:00:00+00:00",
    )
    session.add(enc_orm)

    # Add unconfirmed high-alert discrepancy
    disc = Discrepancy(
        id=str(uuid.uuid4()),
        analysis_run_id=str(uuid.uuid4()),
        encounter_id=enc_id,
        rule_type="omission",
        severity_tier=1,
        is_high_alert=True,
        is_relevant=None,  # Not confirmed!
        verification_required=True,
    )
    session.add(disc)
    session.commit()

    with pytest.raises(HTTPException) as exc_info:
        transition(session, enc_orm, "SELESAI_APPROVE", actor_id="u1", check_high_alert=True)
    assert exc_info.value.status_code == 422
    assert "high-alert" in exc_info.value.detail.lower()
    session.close()


def test_can_transition_helper():
    from api.services.case_state_service import can_transition
    assert can_transition("MENUNGGU_TELAAH", "DRAFT_REVIEW") is True
    assert can_transition("MENUNGGU_TELAAH", "SELESAI_APPROVE") is False
    assert can_transition("DRAFT_REVIEW", "ESKALASI") is True
