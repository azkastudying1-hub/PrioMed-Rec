"""
tests/test_fase1_b107_audit.py
--------------------------------
Tes unit untuk B-107: audit service hash-chain.
"""
import pytest


def _make_session():
    """Create an in-memory SQLite session for testing."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from api.db.models import Base
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_append_audit_creates_entry():
    from api.services.audit_service import append_audit
    session = _make_session()
    entry = append_audit(session, action="LOGIN", actor_id="u1", encounter_id=None, note="test")
    session.commit()
    assert entry.seq == 1
    assert entry.hash is not None
    assert entry.prev_hash == ""
    session.close()


def test_chain_grows_correctly():
    from api.services.audit_service import append_audit
    session = _make_session()
    e1 = append_audit(session, action="LOGIN", actor_id="u1")
    session.commit()
    e2 = append_audit(session, action="APPROVE", actor_id="u1", encounter_id="enc-1")
    session.commit()
    assert e2.seq == 2
    assert e2.prev_hash == e1.hash
    session.close()


def test_verify_chain_valid():
    from api.services.audit_service import append_audit, verify_chain_full
    session = _make_session()
    append_audit(session, action="LOGIN", actor_id="u1")
    session.commit()
    append_audit(session, action="APPROVE", actor_id="u1", encounter_id="enc-1")
    session.commit()
    result = verify_chain_full(session)
    assert result["valid"] is True
    assert result["count"] == 2
    session.close()


def test_verify_chain_empty():
    from api.services.audit_service import verify_chain
    session = _make_session()
    result = verify_chain(session)
    assert result["valid"] is True
    assert result["count"] == 0
    session.close()


def test_verify_chain_detects_tampering():
    """Simulate tampering by directly modifying prev_hash of entry 2."""
    import sqlalchemy as sa
    from api.services.audit_service import append_audit, verify_chain
    session = _make_session()
    append_audit(session, action="LOGIN", actor_id="u1")
    session.commit()
    append_audit(session, action="APPROVE", actor_id="u1")
    session.commit()

    # Tamper: set prev_hash of seq=2 to wrong value
    session.execute(
        sa.text("UPDATE audit_entries SET prev_hash='TAMPERED' WHERE seq=2")
    )
    session.commit()

    result = verify_chain(session)
    assert result["valid"] is False
    assert result["first_broken_seq"] == 2
    session.close()
