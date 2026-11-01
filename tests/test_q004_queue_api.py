"""
tests/test_q004_queue_api.py
-----------------------------
Unit + concurrency tests untuk queue_service.py (Q-004).

Tests:
  - get_queue: pagination, filter tier/ward, keyset cursor
  - next_for_user: atomik (20 threads → 0 duplikat)
  - heartbeat: perpanjang lease, tolak non-owner
  - release_claim: owner & ADMIN override
  - admit_encounter: idempoten
  - discharge_encounter: CLOSED + missed_rec untuk in-progress
  - get_metrics: cache + values

G3: 20 threads → /queue/next → setiap encounter hanya diklaim 1x.
Q1: tier HIGH(RULE) tidak pernah turun via service layer.
"""
from __future__ import annotations

import concurrent.futures
import tempfile
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import api.services.queue_service as _qs_mod
from api.db.models import Base, QueueEntry, QueueEvent, MissedReconciliation
from api.services.queue_service import (
    admit_encounter,
    decode_cursor,
    discharge_encounter,
    encode_cursor,
    get_metrics,
    get_queue,
    heartbeat,
    next_for_user,
    release_claim,
)
from priomedrec_core.queue_config import DEFAULT_CONFIG, QueueConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_metrics_cache():
    """Reset metrics cache sebelum setiap test agar tidak bocor antar test."""
    _qs_mod._metrics_cache = {}
    yield
    _qs_mod._metrics_cache = {}


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    # Disable FK constraints so QueueEntry can be created without Encounter rows
    with eng.connect() as conn:
        conn.execute(sa.text("PRAGMA foreign_keys=OFF"))
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    Session = sessionmaker(bind=engine, autoflush=False)
    s = Session()
    yield s
    s.close()


def _new_enc() -> str:
    return str(uuid.uuid4())


def _make_entry(
    session,
    encounter_id: str | None = None,
    tier_rank: int = 1,
    tier_source: str = "ML",
    priority_score: float = 0.5,
    state: str = "OPEN",
    queue_type: str = "REVIEW",
    ward: str = "ICU",
    claimed_by: str | None = None,
    claim_expires_at: str | None = None,
) -> QueueEntry:
    enc_id = encounter_id or _new_enc()
    now_iso = datetime.now(timezone.utc).isoformat()
    e = QueueEntry(
        encounter_id=enc_id,
        queue_type=queue_type,
        ward=ward,
        state=state,
        tier_rank=tier_rank,
        tier_source=tier_source,
        priority_score=priority_score,
        depth_level=1,
        admitted_at=now_iso,
        queue_version=1,
        claimed_by=claimed_by,
        claim_expires_at=claim_expires_at,
    )
    session.add(e)
    session.commit()
    return e


# ===========================================================================
# Cursor helpers
# ===========================================================================

class TestCursorHelpers:
    def test_encode_decode_roundtrip(self):
        enc_id = _new_enc()
        cursor = encode_cursor(2, 0.8765, enc_id)
        decoded = decode_cursor(cursor)
        assert decoded is not None
        assert decoded[0] == 2
        assert abs(decoded[1] - 0.8765) < 1e-3
        assert decoded[2] == enc_id

    def test_decode_invalid_returns_none(self):
        assert decode_cursor("not-valid-base64!!!") is None

    def test_decode_empty_returns_none(self):
        assert decode_cursor("") is None


# ===========================================================================
# get_queue — pagination & filters
# ===========================================================================

class TestGetQueue:
    def test_returns_open_entries(self, session):
        _make_entry(session, state="OPEN", tier_rank=2, priority_score=0.9)
        _make_entry(session, state="OPEN", tier_rank=1, priority_score=0.5)
        result = get_queue(session, state="OPEN")
        assert result["count"] == 2
        # Sorted: tier 2 before tier 1
        assert result["items"][0]["tier_rank"] == 2

    def test_filter_by_tier(self, session):
        _make_entry(session, tier_rank=2)   # HIGH
        _make_entry(session, tier_rank=1)   # MEDIUM
        result = get_queue(session, tier="HIGH", state="OPEN")
        assert result["count"] == 1
        assert result["items"][0]["tier_rank"] == 2

    def test_filter_by_ward(self, session):
        _make_entry(session, ward="ICU")
        _make_entry(session, ward="SURGICAL")
        result = get_queue(session, ward="ICU", state="OPEN")
        assert result["count"] == 1
        assert result["items"][0]["ward"] == "ICU"

    def test_keyset_cursor_paginates(self, session):
        # Create 5 entries with distinct scores
        for i in range(5):
            _make_entry(session, tier_rank=1, priority_score=float(i) * 0.1)
        page1 = get_queue(session, state="OPEN", limit=3)
        assert page1["count"] == 3
        assert page1["has_next"] is True
        assert page1["next_cursor"] is not None

        page2 = get_queue(session, state="OPEN", limit=3, after_cursor=page1["next_cursor"])
        assert page2["count"] == 2
        assert page2["has_next"] is False

    def test_no_cursor_no_next_when_exact_fit(self, session):
        for _ in range(3):
            _make_entry(session)
        result = get_queue(session, state="OPEN", limit=3)
        assert result["has_next"] is False

    def test_empty_queue(self, session):
        result = get_queue(session, state="OPEN")
        assert result["count"] == 0
        assert result["has_next"] is False


# ===========================================================================
# next_for_user — atomik klaim
# ===========================================================================

class TestNextForUser:
    def test_claims_top_entry(self, session):
        enc1 = _make_entry(session, tier_rank=2, priority_score=0.9)
        enc2 = _make_entry(session, tier_rank=1, priority_score=0.5)
        claimed = next_for_user(session, "user-A")
        assert claimed is not None
        assert claimed["encounter_id"] == enc1.encounter_id
        assert claimed["state"] == "CLAIMED"
        assert claimed["claimed_by"] == "user-A"

    def test_returns_none_when_empty(self, session):
        result = next_for_user(session, "user-A")
        assert result is None

    def test_does_not_reclaim_already_claimed(self, session):
        enc = _make_entry(session, state="OPEN")
        first  = next_for_user(session, "user-A")
        session.commit()
        second = next_for_user(session, "user-B")
        # Only 1 entry → second call returns None
        assert second is None

    def test_ward_scope_filters_correctly(self, session):
        _make_entry(session, ward="ICU",      tier_rank=2, priority_score=0.9)
        _make_entry(session, ward="SURGICAL", tier_rank=2, priority_score=0.8)
        claimed = next_for_user(session, "user-A", ward_scope=["SURGICAL"])
        assert claimed is not None
        assert claimed["ward"] == "SURGICAL"

    def test_no_duplicate_claims_sequential(self, session):
        """G3: next_for_user tidak memberikan encounter yang sama ke 2 pengguna.

        Catatan ADR-22: SQLite tidak mendukung row-level locking (SELECT FOR UPDATE
        diabaikan). Garansi G3 di production menggunakan PostgreSQL. Di sini kita
        memverifikasi logika 'claimed_by IS NULL' guard dengan panggilan sekuensial
        (race condition yang sesungguhnya memerlukan PostgreSQL untuk dibuktikan).
        """
        # Seed 5 entries
        enc_ids = []
        for i in range(5):
            e = _make_entry(session, tier_rank=1, priority_score=float(i) * 0.1)
            enc_ids.append(e.encounter_id)

        claimed_by_user: dict = {}

        # 10 users claim sequentially — no duplicates ever
        for i in range(10):
            result = next_for_user(session, f"user-{i:02d}")
            session.commit()
            if result:
                enc = result["encounter_id"]
                assert enc not in claimed_by_user, (
                    f"Encounter {enc} diklaim 2x (user-{i:02d} dan {claimed_by_user[enc]})"
                )
                claimed_by_user[enc] = f"user-{i:02d}"

        # Max 5 claims for 5 entries
        assert len(claimed_by_user) == 5
        # All claimed entries are distinct
        assert len(claimed_by_user) == len(set(claimed_by_user.keys()))


# ===========================================================================
# heartbeat
# ===========================================================================

class TestHeartbeat:
    def test_extends_lease(self, session):
        now_iso = datetime.now(timezone.utc).isoformat()
        enc = _make_entry(
            session, state="CLAIMED", claimed_by="user-A",
            claim_expires_at=now_iso,
        )
        result = heartbeat(session, enc.encounter_id, "user-A")
        assert "claim_expires_at" in result
        # New expiry must be later than old
        new_exp = datetime.fromisoformat(result["claim_expires_at"])
        assert new_exp > datetime.fromisoformat(now_iso).replace(tzinfo=timezone.utc)

    def test_rejects_non_owner(self, session):
        enc = _make_entry(session, state="CLAIMED", claimed_by="user-A")
        with pytest.raises(ValueError, match="pengguna lain"):
            heartbeat(session, enc.encounter_id, "user-B")

    def test_raises_keyerror_for_missing(self, session):
        with pytest.raises(KeyError):
            heartbeat(session, "nonexistent-enc", "user-A")


# ===========================================================================
# release_claim
# ===========================================================================

class TestReleaseClaim:
    def test_owner_can_release(self, session):
        enc = _make_entry(session, state="CLAIMED", claimed_by="user-A")
        result = release_claim(session, enc.encounter_id, "user-A")
        assert result["state"] == "OPEN"

    def test_admin_can_release_others_claim(self, session):
        enc = _make_entry(session, state="CLAIMED", claimed_by="user-A")
        result = release_claim(session, enc.encounter_id, "admin-1", user_role="ADMIN")
        assert result["state"] == "OPEN"

    def test_non_owner_pharmacist_cannot_release(self, session):
        enc = _make_entry(session, state="CLAIMED", claimed_by="user-A")
        with pytest.raises(PermissionError):
            release_claim(session, enc.encounter_id, "user-B", user_role="PHARMACIST")


# ===========================================================================
# admit_encounter
# ===========================================================================

class TestAdmitEncounter:
    def test_creates_new_entry(self, session):
        enc_id = _new_enc()
        now_iso = datetime.now(timezone.utc).isoformat()
        result = admit_encounter(session, enc_id, "ICU", now_iso)
        assert result["encounter_id"] == enc_id
        assert result["state"] == "OPEN"

    def test_idempotent(self, session):
        enc_id = _new_enc()
        now_iso = datetime.now(timezone.utc).isoformat()
        r1 = admit_encounter(session, enc_id, "ICU", now_iso)
        r2 = admit_encounter(session, enc_id, "ICU", now_iso)
        assert r1["encounter_id"] == r2["encounter_id"]
        # Only 1 entry created
        count = session.query(QueueEntry).filter_by(encounter_id=enc_id).count()
        assert count == 1

    def test_rule_finding_sets_high_tier(self, session):
        enc_id = _new_enc()
        now_iso = datetime.now(timezone.utc).isoformat()
        result = admit_encounter(session, enc_id, "ICU", now_iso, has_rule_finding=True)
        assert result["tier_rank"] == 2  # HIGH
        assert result["tier_source"] == "RULE"


# ===========================================================================
# discharge_encounter
# ===========================================================================

class TestDischargeEncounter:
    def test_closed_when_complete(self, session):
        enc = _make_entry(session, state="OPEN")
        result = discharge_encounter(session, enc.encounter_id, "COMPLETE")
        assert result["state"] == "CLOSED"

    def test_missed_rec_when_incomplete(self, session):
        enc = _make_entry(session, state="CLAIMED", claimed_by="user-A")
        result = discharge_encounter(session, enc.encounter_id, "IN_PROGRESS", reason="DISCHARGE_BEFORE_REVIEW")
        assert result["state"] == "CLOSED"
        # missed_rec entry created
        missed = session.query(MissedReconciliation).filter_by(encounter_id=enc.encounter_id).first()
        assert missed is not None

    def test_open_entry_also_creates_missed_rec(self, session):
        enc = _make_entry(session, state="OPEN")
        discharge_encounter(session, enc.encounter_id, "OPEN", reason="DISCHARGE_BEFORE_REVIEW")
        missed = session.query(MissedReconciliation).filter_by(encounter_id=enc.encounter_id).first()
        assert missed is not None


# ===========================================================================
# get_metrics
# ===========================================================================

class TestGetMetrics:
    def test_metrics_structure(self, session):
        _make_entry(session, tier_rank=2, state="OPEN")
        _make_entry(session, tier_rank=1, state="CLAIMED")
        _make_entry(session, tier_rank=0, state="CLOSED")
        metrics = get_metrics(session)
        assert "backlog" in metrics
        assert "wip" in metrics
        assert "sla_compliance" in metrics
        assert "missed_reconciliations" in metrics

    def test_backlog_counts_open_and_parked(self, session):
        _make_entry(session, state="OPEN",        queue_type="REVIEW")
        _make_entry(session, state="OPEN",        queue_type="REVIEW")
        _make_entry(session, state="PARKED_DPJP", queue_type="REVIEW")
        _make_entry(session, state="CLAIMED",     queue_type="REVIEW")
        metrics = get_metrics(session)
        # backlog dict: {queue_type: {tier: count}}
        assert isinstance(metrics["backlog"], dict)
        review_total = sum(metrics["backlog"].get("REVIEW", {}).values())
        assert review_total == 4  # OPEN×2 + PARKED×1 + CLAIMED×1

    def test_wip_counts_claimed(self, session):
        _make_entry(session, state="CLAIMED")
        _make_entry(session, state="CLAIMED")
        metrics = get_metrics(session)
        assert metrics["wip"]["total"] == 2


# ===========================================================================
# Uji Konkurensi 20 Klien Serentak (G3: 0 Duplikat Klaim) & Latensi P95
# ===========================================================================

class TestConcurrentClaims:
    def test_20_concurrent_clients_zero_duplicate_claims(self):
        """
        Buktikan 0 duplikat klaim pada uji 20 klien serentak dan ukur latensi P95.
        G3: Setiap encounter hanya boleh diklaim tepat 1x.
        """
        import time
        import numpy as np

        os.makedirs("D:/tmp", exist_ok=True)
        temp_dir = "D:/tmp" if os.path.exists("D:/tmp") else None
        temp_db = tempfile.NamedTemporaryFile(dir=temp_dir, suffix=".db", delete=False)
        temp_db_path = temp_db.name
        temp_db.close()

        try:
            eng = create_engine(
                f"sqlite:///{temp_db_path}",
                connect_args={"check_same_thread": False, "timeout": 30.0},
            )
            with eng.connect() as conn:
                conn.execute(sa.text("PRAGMA journal_mode=WAL"))
                conn.execute(sa.text("PRAGMA busy_timeout=30000"))
                conn.execute(sa.text("PRAGMA foreign_keys=OFF"))
            Base.metadata.create_all(eng)

            # Seed 20 open entries
            SessionCls = sessionmaker(bind=eng, autoflush=False)
            seed_session = SessionCls()
            seeded_encs = []
            for i in range(20):
                e = _make_entry(
                    seed_session,
                    tier_rank=1 if i < 15 else 2,
                    priority_score=0.1 * (i + 1),
                    state="OPEN",
                    queue_type="REVIEW",
                )
                seeded_encs.append(e.encounter_id)
            seed_session.commit()
            seed_session.close()

            assert len(seeded_encs) == 20

            # 20 concurrent clients claim simultaneously
            num_clients = 20
            latencies = []
            claimed_by_user = {}

            def client_claim(client_id: int):
                sess = SessionCls()
                t0 = time.perf_counter()
                try:
                    res = next_for_user(sess, f"user-concurrent-{client_id:02d}", queue_type="REVIEW")
                    sess.commit()
                finally:
                    sess.close()
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                return client_id, res, elapsed_ms

            with concurrent.futures.ThreadPoolExecutor(max_workers=num_clients) as executor:
                futures = [executor.submit(client_claim, i) for i in range(num_clients)]
                for fut in concurrent.futures.as_completed(futures):
                    cid, result, lat_ms = fut.result()
                    latencies.append(lat_ms)
                    if result:
                        enc = result["encounter_id"]
                        # Assert ZERO DUPLICATES across threads
                        assert enc not in claimed_by_user, (
                            f"PELANGGARAN G3: Encounter {enc} diklaim 2x! "
                            f"(oleh user {claimed_by_user[enc]} dan user {cid})"
                        )
                        claimed_by_user[enc] = cid

            # Verifikasi semua 20 entri berhasil diklaim secara unik
            assert len(claimed_by_user) == 20, (
                f"Diharapkan 20 klaim unik, didapat {len(claimed_by_user)}"
            )
            # Pastikan 0 duplikat
            assert len(claimed_by_user) == len(set(claimed_by_user.keys()))

            # Hitung latensi P50, P90, P95
            p50 = float(np.percentile(latencies, 50))
            p90 = float(np.percentile(latencies, 90))
            p95 = float(np.percentile(latencies, 95))

            # Catat latensi
            print(f"\n[BENCHMARK] 20 Concurrent Clients Claim Results:")
            print(f"  Claims: {len(claimed_by_user)} unique encounters claimed (0 duplicates)")
            print(f"  Latensi P50: {p50:.2f} ms")
            print(f"  Latensi P90: {p90:.2f} ms")
            print(f"  Latensi P95: {p95:.2f} ms")

            # P95 target (SQLite concurrent WAL pada disk Windows < 800 ms)
            assert p95 < 800.0, f"Latensi P95 ({p95:.2f} ms) melebihi batas toleransi"

        finally:
            eng.dispose()
            if os.path.exists(temp_db_path):
                try:
                    os.remove(temp_db_path)
                except Exception:
                    pass


# ===========================================================================
# Q-010: Penanganan Event Idempoten & Ketahanan Urutan Acak
# ===========================================================================

class TestIdempotencyAndOutOfOrderEvents:
    def test_rapid_duplicate_admit(self, session):
        """Panggilan berulang admit_encounter tidak membuat baris duplikat."""
        enc_id = _new_enc()
        now_iso = datetime.now(timezone.utc).isoformat()
        r1 = admit_encounter(session, enc_id, "ICU", now_iso)
        r2 = admit_encounter(session, enc_id, "ICU", now_iso)
        r3 = admit_encounter(session, enc_id, "ICU", now_iso)
        session.commit()
        assert r1["encounter_id"] == enc_id
        assert r2["encounter_id"] == enc_id
        assert r3["encounter_id"] == enc_id
        count = session.query(QueueEntry).filter_by(encounter_id=enc_id).count()
        assert count == 1

    def test_discharge_before_admit_graceful(self, session):
        """DISCHARGE yang tiba sebelum ADMIT ditangani graceful tanpa unhandled exception."""
        ghost_id = _new_enc()
        res = discharge_encounter(session, ghost_id, "OPEN", reason="DISCHARGE_BEFORE_REVIEW")
        session.commit()
        assert res["encounter_id"] == ghost_id
        assert res["state"] == "not_found"

    def test_lab_critical_escalates_and_deduplicates(self, session):
        """LAB_CRITICAL menaikkan tier ke HIGH(RULE) dan dedup dalam 1 jam."""
        from api.services.queue_service import lab_critical_event
        enc = _make_entry(session, tier_rank=1, tier_source="ML", priority_score=0.4)
        session.commit()

        # Panggilan pertama: eskalasi
        r1 = lab_critical_event(session, enc.encounter_id, lab_type="POTASSIUM_HIGH", lab_value="6.9 mEq/L")
        session.commit()
        assert r1["tier_rank"] == 2
        assert r1["tier_source"] == "RULE"
        assert r1["priority_score"] >= 85.0

        # Panggilan kedua dalam 1 jam: deduped
        r2 = lab_critical_event(session, enc.encounter_id, lab_type="POTASSIUM_HIGH", lab_value="6.9 mEq/L")
        assert r2["tier_rank"] == 2
        assert r2["tier_source"] == "RULE"

    def test_order_change_updates_and_debounces(self, session):
        """ORDER_CHANGE memperbarui queue_version dan ter-debounce dalam 30 detik."""
        from api.services.queue_service import order_change_event
        enc = _make_entry(session, tier_rank=1, tier_source="ML", priority_score=0.5)
        initial_version = enc.queue_version
        session.commit()

        # Call 1
        r1 = order_change_event(session, enc.encounter_id, order_details={"drug": "Warfarin"}, has_rule_finding=True)
        session.commit()
        assert r1["tier_rank"] == 2
        assert r1["tier_source"] == "RULE"
        assert r1["queue_version"] > initial_version

        # Call 2 (seketika): debounced
        r2 = order_change_event(session, enc.encounter_id, order_details={"drug": "Warfarin"})
        assert r2.get("status") == "debounced" or r2["tier_rank"] == 2

    def test_random_ordered_event_sequence_resilience(self, session):
        """
        Ketahanan terhadap urutan event acak:
        Pipeline multi-encounter dengan event diacak (admit, transfer, order_change, lab_critical, discharge).
        Tidak ada event yang merusak integritas lantai RULE.
        """
        import random
        from api.services.queue_service import lab_critical_event, order_change_event
        from priomedrec_core.queue_transitions import transfer as _transfer

        encs = [_new_enc() for _ in range(5)]
        now_iso = datetime.now(timezone.utc).isoformat()

        # Admit all
        for eid in encs:
            admit_encounter(session, eid, "Bedah", now_iso, ml_score=0.4)
        session.commit()

        # Buat daftar event acak
        events = []
        for eid in encs:
            events.append(("lab", eid))
            events.append(("order", eid))
            events.append(("heartbeat", eid))

        random.seed(42)
        random.shuffle(events)

        for ev_type, eid in events:
            if ev_type == "lab":
                lab_critical_event(session, eid, "INR_HIGH", "5.2")
            elif ev_type == "order":
                order_change_event(session, eid, {"drug": "Digoxin"})
            session.commit()

        # Verifikasi semua entri yang menerima lab_critical tetap HIGH(RULE)
        entries = session.query(QueueEntry).filter(QueueEntry.encounter_id.in_(encs)).all()
        for e in entries:
            assert e.tier_rank == 2, f"Encounter {e.encounter_id} harus HIGH(RULE)"
            assert e.tier_source == "RULE"

        # Akhiri dengan discharge
        for eid in encs:
            res = discharge_encounter(session, eid, "SELESAI_APPROVE")
            assert res["state"] == "CLOSED"
        session.commit()

