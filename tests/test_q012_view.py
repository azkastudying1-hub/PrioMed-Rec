"""
tests/test_q012_view.py
------------------------
Uji lapisan tampilan antrean (queue_view_service) untuk menu
"Antrean Farmasi" dan "Command Center".

  - enrich_entries   : tier, SLA, alasan prioritas ("mengapa dia?")
  - get_my_queue     : klaim aktif + pratinjau berikutnya
  - get_command_center: kapasitas, panas bangsal, aging, risiko SLA, mode lonjakan
  - advance_encounter / sync_after_review: sinkron status encounter ↔ antrean
  - get_queue(search): pencarian nama/ID
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import api.services.queue_service as _qs
from api.db.models import Base, Encounter, QueueEntry
from api.services.queue_service import admit_encounter, get_queue, next_for_user
from api.services.queue_view_service import (
    advance_encounter,
    enrich_entries,
    get_command_center,
    get_my_queue,
    sync_after_review,
)
from priomedrec_core.queue_transitions import bpmh_submit
from api.services.queue_service import _entry_to_dict


@pytest.fixture(autouse=True)
def _reset_cache():
    _qs._metrics_cache = {}
    yield
    _qs._metrics_cache = {}


@pytest.fixture()
def session():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng, autoflush=False)()
    yield s
    s.close()
    eng.dispose()


def _admit(session, ward="ICU", hours_ago=1.0, rule=False, ml=0.4, to_review=True) -> str:
    eid = str(uuid.uuid4())
    at = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    admit_encounter(session, eid, ward, at, ml_score=ml, has_rule_finding=rule)
    if to_review:
        entry = session.query(QueueEntry).filter_by(encounter_id=eid).first()
        updated, _ = bpmh_submit(_entry_to_dict(entry), has_rule_finding=rule, ml_score=ml)
        entry.queue_type = "REVIEW"
        entry.tier_rank = updated["tier_rank"]
        entry.tier_source = updated["tier_source"]
        entry.priority_score = updated["priority_score"]
    session.commit()
    return eid


class TestEnrich:
    def test_adds_patient_sla_and_reasons(self, session):
        eid = _admit(session, hours_ago=3.0, rule=True)
        items = get_queue(session, queue_type="REVIEW")["items"]
        enrich_entries(session, items)
        it = items[0]
        assert it["encounter_id"] == eid
        assert it["tier"] == "HIGH"
        assert it["patient_name"]                     # inisial sintetis
        assert it["sla_target_hours"] == 4.0
        assert 0.7 < it["sla_ratio"] < 0.8            # 3j / 4j
        assert any("aturan klinis" in w.lower() for w in it["why"])
        assert it["priority_reasons"][0]["source"] == "rules"

    def test_claimed_entry_has_lease_and_name(self, session):
        _admit(session)
        claimed = next_for_user(session, "user-A")
        session.commit()
        enrich_entries(session, [claimed])
        assert claimed["lease_seconds_left"] > 800    # lease 15 menit
        assert claimed["claimed_by_name"]


class TestSearch:
    def test_search_by_patient_name_and_id(self, session):
        eid = _admit(session)
        enc = session.query(Encounter).filter_by(id=eid).first()
        by_name = get_queue(session, search=enc.patient_name)
        by_id = get_queue(session, search=enc.patient_id)
        assert by_name["total"] >= 1 and by_id["total"] == 1
        assert get_queue(session, search="zzz-tidak-ada")["total"] == 0


class TestMyQueue:
    def test_mine_and_upcoming(self, session):
        for _ in range(4):
            _admit(session)
        first = next_for_user(session, "user-A")
        session.commit()
        mine = get_my_queue(session, "user-A", next_n=2)
        assert [c["encounter_id"] for c in mine["claimed"]] == [first["encounter_id"]]
        assert len(mine["upcoming"]) == 2
        assert first["encounter_id"] not in {u["encounter_id"] for u in mine["upcoming"]}


class TestCommandCenter:
    def test_structure_and_heatmap(self, session):
        _admit(session, ward="ICU", rule=True)
        _admit(session, ward="BEDAH", ml=0.1)
        _admit(session, ward="ICU", to_review=False)   # masih Antrean BPMH
        cc = get_command_center(session)
        assert cc["totals"]["open_total"] == 3
        assert cc["totals"]["bpmh_open"] == 1
        assert cc["totals"]["review_open"] == 2
        assert set(cc["heatmap"]["wards"]) == {"ICU", "BEDAH"}
        assert sum(sum(r.values()) for r in cc["heatmap"]["cells"].values()) == 3
        assert cc["capacity"]["assumption_note"]
        assert "simulasi" in cc["simulated_label"].lower()

    def test_surge_is_recommendation_only(self, session):
        for _ in range(25):
            _admit(session, hours_ago=2.0, rule=True)
        before = sorted((e.encounter_id, e.tier_rank) for e in session.query(QueueEntry))
        cc = get_command_center(session, pharmacists=1)
        after = sorted((e.encounter_id, e.tier_rank) for e in session.query(QueueEntry))
        assert cc["surge"]["active"] is True
        assert cc["capacity"]["load_ratio"] > 1.3
        assert cc["capacity"]["extra_pharmacist_hours"] > 0
        assert cc["surge"]["recommendations"]
        assert before == after                         # tier tak pernah berubah (aturan §3.5)

    def test_more_pharmacists_lowers_load(self, session):
        for _ in range(10):
            _admit(session)
        low = get_command_center(session, pharmacists=1)["capacity"]["load_ratio"]
        _qs._metrics_cache = {}
        high = get_command_center(session, pharmacists=5)["capacity"]["load_ratio"]
        assert high < low

    def test_at_risk_lists_sla_pressure_first(self, session):
        _admit(session, hours_ago=0.2, rule=True)
        late = _admit(session, hours_ago=6.0, rule=True)      # > 4j SLA HIGH
        cc = get_command_center(session)
        assert cc["at_risk"]["total"] == 1
        assert cc["at_risk"]["items"][0]["encounter_id"] == late
        assert cc["at_risk"]["items"][0]["sla_ratio"] > 1.0

    def test_aging_buckets_sum_to_open(self, session):
        for h in (0.1, 0.5, 2.0, 3.5, 9.0):
            _admit(session, hours_ago=h, rule=True)
        cc = get_command_center(session)
        total = sum(sum(v) for v in cc["aging"]["by_tier"].values())
        assert total == cc["totals"]["open_total"] == 5


class TestEncounterSync:
    def test_advance_walks_valid_path(self, session):
        eid = _admit(session, to_review=False)
        assert advance_encounter(session, eid, "MENUNGGU_TELAAH") == "MENUNGGU_TELAAH"
        assert advance_encounter(session, eid, "DRAFT_REVIEW", claimed_by=None) == "DRAFT_REVIEW"
        rows = session.execute(sa.text(
            "SELECT to_status FROM status_history WHERE encounter_id=:e ORDER BY changed_at"
        ), {"e": eid}).fetchall()
        assert [r[0] for r in rows] == [
            "BPMH_LENGKAP", "DALAM_ANALISIS", "MENUNGGU_TELAAH", "DRAFT_REVIEW",
        ]

    def test_advance_never_moves_backwards_or_past_terminal(self, session):
        eid = _admit(session, to_review=False)
        enc = session.query(Encounter).filter_by(id=eid).first()
        enc.workflow_status = "SELESAI_APPROVE"
        session.commit()
        assert advance_encounter(session, eid, "DRAFT_REVIEW") == "SELESAI_APPROVE"

    def test_review_actions_close_or_park_queue(self, session):
        a, b, c = _admit(session), _admit(session), _admit(session)
        assert sync_after_review(session, a, "APPROVE") == "CLOSED"
        assert sync_after_review(session, b, "ESCALATE") == "PARKED_DPJP"
        assert sync_after_review(session, c, "DRAFT_REVIEW") == "OPEN"
        session.commit()
        cc = get_command_center(session)
        assert cc["totals"]["parked_dpjp"] == 1
        assert cc["flow"]["closed_total"] == 1
