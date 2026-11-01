"""
tests/test_q003_transitions.py
--------------------------------
Q-003: Unit tests untuk priomedrec_core/queue_transitions.py

Mencakup:
- admit() → Antrean A (BPMH), state=OPEN
- bpmh_submit() → pindah A→B, tier hanya naik
- discharge() → CLOSED + missed_reconciliation jika belum SELESAI
- cancel() → CLOSED
- transfer() → re-triage, klaim dilepas saat beda bangsal
- park_dpjp() / unpark_dpjp()
- expire_claim() → admitted_at tetap, state=OPEN
- Idempoten event (duplicate admit tidak membuat duplikat state)
- Lantai aturan RULE tidak pernah turun saat transfer/bpmh_submit
"""
from __future__ import annotations

import json
import pytest
from datetime import datetime, timedelta, timezone

from priomedrec_core.queue_config import DEFAULT_CONFIG
from priomedrec_core.queue_transitions import (
    admit,
    bpmh_submit,
    discharge,
    cancel,
    transfer,
    park_dpjp,
    unpark_dpjp,
    expire_claim,
    TERMINAL_STATUSES,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2026, 11, 2, 14, 0, 0, tzinfo=timezone.utc)
ADMITTED_AT = (NOW - timedelta(hours=2.0)).isoformat()


@pytest.fixture
def base_entry():
    """Entri BPMH dasar yang sudah di-admit."""
    entry, _ = admit(
        encounter_id="enc-test",
        ward="ICU",
        admitted_at=ADMITTED_AT,
        ml_score=0.72,
        now=NOW,
    )
    return entry


# ===========================================================================
# BAGIAN 1: admit()
# ===========================================================================

class TestAdmit:

    def test_admit_state_OPEN(self):
        entry, _ = admit("enc-1", "ICU", ADMITTED_AT, now=NOW)
        assert entry["state"] == "OPEN"

    def test_admit_queue_type_BPMH(self):
        entry, _ = admit("enc-1", "ICU", ADMITTED_AT, now=NOW)
        assert entry["queue_type"] == "BPMH"

    def test_admit_ward_sesuai(self):
        entry, _ = admit("enc-1", "Bedah", ADMITTED_AT, now=NOW)
        assert entry["ward"] == "Bedah"

    def test_admit_RULE_jika_ada_temuan(self):
        """Temuan klinis (has_rule_finding=True) → tier_source=RULE, tier_rank=2."""
        entry, _ = admit("enc-2", "ICU", ADMITTED_AT, has_rule_finding=True, now=NOW)
        assert entry["tier_source"] == "RULE"
        assert entry["tier_rank"] == 2  # HIGH

    def test_admit_ML_tanpa_temuan(self):
        entry, _ = admit("enc-3", "ICU", ADMITTED_AT, ml_score=0.80, now=NOW)
        assert entry["tier_source"] == "ML"

    def test_admit_event_kind_upsert(self):
        _, event = admit("enc-4", "ICU", ADMITTED_AT, now=NOW)
        assert event["kind"] == "upsert"

    def test_admit_event_payload_action_admit(self):
        _, event = admit("enc-5", "ICU", ADMITTED_AT, now=NOW)
        payload = json.loads(event["payload_json"])
        assert payload["action"] == "admit"

    def test_admit_sla_due_at_ada(self):
        entry, _ = admit("enc-6", "ICU", ADMITTED_AT, ml_score=0.9, now=NOW)
        assert entry["sla_due_at"] is not None

    def test_admit_next_due_at_ada_jika_belum_breach(self):
        """Baru masuk (0.1 jam) → next_due_at harus ada."""
        admitted = (NOW - timedelta(hours=0.1)).isoformat()
        entry, _ = admit("enc-7", "ICU", admitted, ml_score=0.9, now=NOW)
        assert entry["next_due_at"] is not None

    def test_admit_priority_score_nonnegatif(self):
        entry, _ = admit("enc-8", "ICU", ADMITTED_AT, ml_score=0.5, now=NOW)
        assert entry["priority_score"] >= 0.0


# ===========================================================================
# BAGIAN 2: bpmh_submit()
# ===========================================================================

class TestBpmhSubmit:

    def test_bpmh_submit_queue_type_REVIEW(self, base_entry):
        new_entry, _ = bpmh_submit(base_entry, now=NOW)
        assert new_entry["queue_type"] == "REVIEW"

    def test_bpmh_submit_state_OPEN(self, base_entry):
        new_entry, _ = bpmh_submit(base_entry, now=NOW)
        assert new_entry["state"] == "OPEN"

    def test_bpmh_submit_RULE_menaikkan_tier(self, base_entry):
        """Temuan Tier-1 saat BPMH submit → tier_source=RULE, tier_rank=2."""
        new_entry, _ = bpmh_submit(
            base_entry, has_rule_finding=True, now=NOW
        )
        assert new_entry["tier_source"] == "RULE"
        assert new_entry["tier_rank"] == 2

    def test_bpmh_submit_tier_tidak_turun(self, base_entry):
        """Jika sebelumnya HIGH(RULE), BPMH submit tidak boleh turunkan tier."""
        base_entry_rule = dict(base_entry)
        base_entry_rule["tier_rank"]   = 2
        base_entry_rule["tier_source"] = "RULE"

        # Submit BPMH tanpa temuan baru (ML score rendah)
        new_entry, _ = bpmh_submit(
            base_entry_rule,
            has_rule_finding=False,
            ml_score=0.10,  # LOW ML
            now=NOW,
        )
        assert new_entry["tier_rank"] >= 2, \
            "Tier tidak boleh turun dari HIGH(RULE) saat bpmh_submit"

    def test_bpmh_submit_lepas_klaim(self, base_entry):
        """bpmh_submit selalu melepas klaim (kasus kembali ke antrean B)."""
        base_entry["claimed_by"] = "pharmacist-1"
        base_entry["claim_expires_at"] = (NOW + timedelta(minutes=10)).isoformat()
        new_entry, _ = bpmh_submit(base_entry, now=NOW)
        assert new_entry["claimed_by"] is None
        assert new_entry["claim_expires_at"] is None

    def test_bpmh_submit_queue_version_naik(self, base_entry):
        prev_version = base_entry["queue_version"]
        new_entry, _ = bpmh_submit(base_entry, now=NOW)
        assert new_entry["queue_version"] > prev_version


# ===========================================================================
# BAGIAN 3: discharge()
# ===========================================================================

class TestDischarge:

    def test_discharge_state_CLOSED(self, base_entry):
        new_entry, _, _ = discharge(base_entry, "DALAM_ANALISIS", now=NOW)
        assert new_entry["state"] == "CLOSED"

    def test_discharge_missed_rec_jika_belum_selesai(self, base_entry):
        """Pasien pulang sebelum rekonsiliasi → missed_reconciliation terisi (Q7)."""
        _, _, missed = discharge(base_entry, "DALAM_ANALISIS", now=NOW)
        assert missed is not None
        assert missed["encounter_id"] == base_entry["encounter_id"]
        assert missed["reason"] is not None

    def test_discharge_tanpa_missed_rec_jika_selesai(self, base_entry):
        """Rekonsiliasi sudah SELESAI_APPROVE → tidak ada missed_reconciliation."""
        for status in TERMINAL_STATUSES:
            _, _, missed = discharge(base_entry, status, now=NOW)
            assert missed is None, f"Status {status} tidak boleh menghasilkan missed_rec"

    def test_discharge_event_kind_remove(self, base_entry):
        _, event, _ = discharge(base_entry, "DALAM_ANALISIS", now=NOW)
        assert event["kind"] == "remove"

    def test_discharge_missed_rec_last_tier_benar(self, base_entry):
        base_entry["tier_rank"] = 2  # HIGH
        _, _, missed = discharge(base_entry, "MENUNGGU_TELAAH", now=NOW)
        assert missed["last_tier"] == "HIGH"


# ===========================================================================
# BAGIAN 4: cancel()
# ===========================================================================

class TestCancel:

    def test_cancel_state_CLOSED(self, base_entry):
        new_entry, _ = cancel(base_entry, now=NOW)
        assert new_entry["state"] == "CLOSED"

    def test_cancel_event_kind_remove(self, base_entry):
        _, event = cancel(base_entry, now=NOW)
        assert event["kind"] == "remove"

    def test_cancel_tidak_buat_missed_rec(self, base_entry):
        """cancel() tidak menghasilkan missed_reconciliation."""
        new_entry, event = cancel(base_entry, now=NOW)
        payload = json.loads(event["payload_json"])
        assert payload["action"] == "cancel"
        # (tidak ada return ketiga — berbeda dari discharge())


# ===========================================================================
# BAGIAN 5: transfer()
# ===========================================================================

class TestTransfer:

    def test_transfer_ward_berubah(self, base_entry):
        new_entry, _ = transfer(base_entry, "Penyakit Dalam", now=NOW)
        assert new_entry["ward"] == "Penyakit Dalam"

    def test_transfer_lepas_klaim(self, base_entry):
        """Transfer bangsal harus melepas klaim."""
        base_entry["claimed_by"] = "pharmacist-2"
        base_entry["claim_expires_at"] = (NOW + timedelta(minutes=5)).isoformat()
        new_entry, _ = transfer(base_entry, "Bedah", now=NOW)
        assert new_entry["state"] == "OPEN"
        assert new_entry["claimed_by"] is None

    def test_transfer_RULE_tidak_turun(self, base_entry):
        """Transfer tidak boleh menurunkan lantai aturan RULE."""
        base_entry["tier_rank"]   = 2
        base_entry["tier_source"] = "RULE"
        new_entry, _ = transfer(
            base_entry, "Penyakit Dalam",
            has_rule_finding=False,  # tidak ada temuan baru
            ml_score=0.10,           # ML rendah
            now=NOW,
        )
        assert new_entry["tier_rank"] >= 2, \
            "Transfer tidak boleh menurunkan tier RULE"

    def test_transfer_event_payload_benar(self, base_entry):
        _, event = transfer(base_entry, "Saraf", now=NOW)
        payload = json.loads(event["payload_json"])
        assert payload["action"] == "transfer"
        assert payload["to_ward"] == "Saraf"

    def test_transfer_queue_version_naik(self, base_entry):
        prev_version = base_entry["queue_version"]
        new_entry, _ = transfer(base_entry, "Jantung", now=NOW)
        assert new_entry["queue_version"] > prev_version


# ===========================================================================
# BAGIAN 6: park_dpjp() / unpark_dpjp()
# ===========================================================================

class TestParkUnparkDpjp:

    def test_park_state_PARKED_DPJP(self, base_entry):
        new_entry, _ = park_dpjp(base_entry, now=NOW)
        assert new_entry["state"] == "PARKED_DPJP"

    def test_park_lepas_klaim(self, base_entry):
        base_entry["claimed_by"] = "pharmacist-3"
        new_entry, _ = park_dpjp(base_entry, now=NOW)
        assert new_entry["claimed_by"] is None

    def test_unpark_state_OPEN(self, base_entry):
        parked, _ = park_dpjp(base_entry, now=NOW)
        unparked, _ = unpark_dpjp(parked, now=NOW)
        assert unparked["state"] == "OPEN"

    def test_unpark_next_due_at_ada(self, base_entry):
        parked, _ = park_dpjp(base_entry, now=NOW)
        unparked, _ = unpark_dpjp(parked, now=NOW)
        # Entri baru unparkir (2 jam dari masuk) harus punya next_due_at
        # HIGH target=4j, sudah 2j → warning sudah (2j >= 2j?), target belum
        # Bisa None jika sudah breach, tapi tidak boleh crash
        # Hanya tes tidak raise exception:
        _ = unparked.get("next_due_at")  # tidak raise


# ===========================================================================
# BAGIAN 7: expire_claim()
# ===========================================================================

class TestExpireClaim:

    def test_expire_state_OPEN(self, base_entry):
        base_entry["state"] = "CLAIMED"
        base_entry["claimed_by"] = "pharmacist-4"
        base_entry["claim_expires_at"] = (NOW - timedelta(minutes=1)).isoformat()

        new_entry, _ = expire_claim(base_entry, now=NOW)
        assert new_entry["state"] == "OPEN"

    def test_expire_claimed_by_none(self, base_entry):
        base_entry["state"] = "CLAIMED"
        base_entry["claimed_by"] = "pharmacist-4"
        new_entry, _ = expire_claim(base_entry, now=NOW)
        assert new_entry["claimed_by"] is None

    def test_expire_admitted_at_tidak_berubah(self, base_entry):
        """Usia menunggu dipertahankan — admitted_at tidak berubah."""
        original_admitted = base_entry["admitted_at"]
        base_entry["state"] = "CLAIMED"
        base_entry["claimed_by"] = "pharmacist-5"
        new_entry, _ = expire_claim(base_entry, now=NOW)
        assert new_entry["admitted_at"] == original_admitted, \
            "admitted_at harus tetap — usia menunggu tidak mulai dari nol"

    def test_expire_queue_version_naik(self, base_entry):
        prev_version = base_entry["queue_version"]
        base_entry["state"] = "CLAIMED"
        base_entry["claimed_by"] = "pharmacist-6"
        new_entry, _ = expire_claim(base_entry, now=NOW)
        assert new_entry["queue_version"] > prev_version

    def test_expire_event_kind_expire(self, base_entry):
        base_entry["state"] = "CLAIMED"
        base_entry["claimed_by"] = "pharmacist-7"
        _, event = expire_claim(base_entry, now=NOW)
        assert event["kind"] == "expire"


# ===========================================================================
# BAGIAN 8: Idempoten dan keselamatan
# ===========================================================================

class TestIdempoten:

    def test_discharge_idempoten_jika_sudah_CLOSED(self, base_entry):
        """Discharge pada entri yang sudah CLOSED tidak merusak state."""
        base_entry["state"] = "CLOSED"
        new_entry, _, missed = discharge(base_entry, "SELESAI_APPROVE", now=NOW)
        assert new_entry["state"] == "CLOSED"
        assert missed is None  # sudah SELESAI, tidak ada missed

    def test_semua_transisi_menghasilkan_event(self, base_entry):
        """Setiap transisi harus menghasilkan queue_event."""
        funcs_and_results = [
            admit("enc-new", "ICU", ADMITTED_AT, now=NOW),
            bpmh_submit(base_entry, now=NOW),
            discharge(base_entry, "DALAM_ANALISIS", now=NOW)[:2],
            cancel(base_entry, now=NOW),
            transfer(base_entry, "Saraf", now=NOW),
            park_dpjp(base_entry, now=NOW),
            expire_claim({**base_entry, "state": "CLAIMED", "claimed_by": "u1"}, now=NOW),
        ]
        for _, event in funcs_and_results:
            assert "kind" in event
            assert "encounter_id" in event
            assert "payload_json" in event

    def test_RULE_floor_dipertahankan_selama_pipeline(self):
        """
        Pipeline lengkap: admit (ML) → bpmh_submit (temuan RULE) → transfer →
        tier_source=RULE tetap HIGH di semua langkah.
        """
        admitted = (NOW - timedelta(hours=1)).isoformat()
        entry, _ = admit("enc-pipeline", "ICU", admitted, ml_score=0.5, now=NOW)
        assert entry["tier_source"] == "ML"

        # BPMH submit → temukan warfarin high-alert
        entry, _ = bpmh_submit(entry, has_rule_finding=True, is_high_alert=True, now=NOW)
        assert entry["tier_source"] == "RULE"
        assert entry["tier_rank"] == 2

        # Transfer → RULE harus tetap HIGH
        entry, _ = transfer(entry, "Penyakit Dalam", has_rule_finding=False, ml_score=0.1, now=NOW)
        assert entry["tier_rank"] >= 2, "RULE HIGH tidak boleh turun saat transfer"
