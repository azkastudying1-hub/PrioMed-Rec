#!/usr/bin/env python3
"""
scripts/seed_demo.py
---------------------
Seed deterministik skenario demo S1–S10 (B-115).

Skenario (dari dokumen strategi Bagian 5.5):
  S1  — Pasien high-risk, banyak diskrepansi omisi, high-alert (warfarin) → tier HIGH
  S2  — Pasien dengan interaksi obat kritis (DDI) + alergi silang
  S3  — Pasien dengan diskrepansi Tier-1 (omisi insulin) → wajib konfirmasi high-alert sebelum APPROVE
  S4  — Pasien lansia polypharmacy, diskrepansi banyak → tier MEDIUM
  S5  — Skenario fallback LLM: SBAR dari template deterministik
  S6  — Skenario guardrail: LLM menyebut obat fiktif → ditolak
  S7  — Pasien SLA breach: sudah menunggu > 2 jam (tier HIGH) → eskalasi otomatis
  S8  — Pasien tanpa obat rutin ("tidak minum obat") → worklist BPMH selesai tanpa diskrepansi
  S9  — Apoteker EDIT resep + alasan lengkap → SELESAI_EDIT
  S10 — TTK submit BPMH → Apoteker telaah → APPROVE → Audit trail hash-chain valid

Penggunaan:
    python scripts/seed_demo.py [--reset] [--db-path data/priomed.db]

--reset: hapus semua data demo dan seed ulang (data user dipertahankan kecuali demo users)

STATUS: Semua data adalah data SINTETIS (S9 dari prinsip keselamatan).
JANGAN masukkan data pasien nyata.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts(hours_ago: float = 0.0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return dt.isoformat()


def seed(db_path: str = "data/priomed.db", reset: bool = False):
    from api.db.session import session_scope as get_session, engine
    from api.db.models import Base, User, Encounter, BpmhItem, AnalysisRun, Discrepancy, SlaConfig, AuditEntry
    from api.auth.password import hash_password
    from api.services.audit_service import append_audit

    # Ensure tables exist
    Base.metadata.create_all(engine)

    with get_session() as session:
        if reset:
            print("[seed] Reset: menghapus data demo lama...")
            import sqlalchemy as _sa
            # Delete encounters + cascade (SQLite no FK cascade by default — delete manually)
            demo_patient_ids = [f"DEMO-S{i:02d}" for i in range(1, 11)]
            # Detect whether audit_entries uses new schema (encounter_id) or legacy (case_id)
            _audit_col = "encounter_id"
            try:
                _cols = [r[1] for r in session.execute(_sa.text("PRAGMA table_info(audit_entries)")).fetchall()]
                if "encounter_id" not in _cols:
                    _audit_col = "case_id"
            except Exception:
                pass
            for pid in demo_patient_ids:
                encs = session.execute(
                    _sa.text("SELECT id FROM encounters WHERE patient_id = :pid"),
                    {"pid": pid}
                ).fetchall()
                for (enc_id,) in encs:
                    for tbl, col in [
                        ("bpmh_items",    "encounter_id"),
                        ("discrepancies", "encounter_id"),
                        ("status_history","encounter_id"),
                        ("sla_events",    "encounter_id"),
                        ("sbar_drafts",   "encounter_id"),
                        ("analysis_runs", "encounter_id"),
                        ("audit_entries", _audit_col),
                    ]:
                        try:
                            session.execute(_sa.text(f"DELETE FROM {tbl} WHERE {col} = :id"), {"id": enc_id})
                        except Exception:
                            pass  # Table or column may not exist yet
                session.execute(_sa.text("DELETE FROM encounters WHERE patient_id = :pid"), {"pid": pid})
            # Keep demo users (do not reset passwords)
            session.commit()
            print("[seed] Data demo lama dihapus.")

        # -----------------------------------------------------------------------
        # Demo users
        # -----------------------------------------------------------------------
        _ensure_user(session, User,
            user_id="user-apoteker-001",
            username="apoteker1",
            full_name="Apt. Sari Dewi, S.Farm.",
            role="PHARMACIST",
            password="demo1234",
            hash_password=hash_password,
        )
        _ensure_user(session, User,
            user_id="user-ttk-001",
            username="ttk1",
            full_name="Ahmad TTK",
            role="TECHNICIAN",
            password="demo1234",
            hash_password=hash_password,
        )
        _ensure_user(session, User,
            user_id="user-admin-001",
            username="admin",
            full_name="Admin PrioMed",
            role="ADMIN",
            password="admin1234",
            hash_password=hash_password,
        )
        _ensure_user(session, User,
            user_id="user-koordinator-001",
            username="koordinator1",
            full_name="Koordinator Farmasi",
            role="COORDINATOR",
            password="demo1234",
            hash_password=hash_password,
        )
        session.commit()
        print("[seed] Demo users siap.")

        # -----------------------------------------------------------------------
        # SLA Config defaults
        # -----------------------------------------------------------------------
        _ensure_sla_config(session, SlaConfig)
        session.commit()

        # -----------------------------------------------------------------------
        # S1: High-risk, omisi warfarin (HIGH ALERT), tier HIGH
        # -----------------------------------------------------------------------
        s1_id = _enc("DEMO-S01", "Tn. B.S.", "JANTUNG", 3.5, session, tier="HIGH", ml_score=0.89)
        _bpmh(s1_id, session, [
            {"drug": "warfarin", "dose": "5mg", "route": "oral", "freq": "1x1", "is_high_alert": True},
            {"drug": "bisoprolol", "dose": "5mg", "route": "oral", "freq": "1x1"},
            {"drug": "furosemide", "dose": "40mg", "route": "oral", "freq": "1x1"},
        ])
        _analysis(s1_id, session, [
            {"rule_type": "omission", "severity_tier": 1, "drug_name": "warfarin", "is_high_alert": True,
             "evidence": "Warfarin tidak dilanjutkan pada pesanan admisi. Pasien riwayat AF kronik."},
            {"rule_type": "omission", "severity_tier": 2, "drug_name": "bisoprolol", "is_high_alert": False,
             "evidence": "Bisoprolol tidak tertulis pada pesanan admisi."},
        ], ml_score=0.89, tier="HIGH")

        # -----------------------------------------------------------------------
        # S2: DDI + alergi silang (penisilin → sefalosporin)
        # -----------------------------------------------------------------------
        s2_id = _enc("DEMO-S02", "Ny. R.H.", "PENYAKIT_DALAM", 5.0, session, tier="HIGH", ml_score=0.78)
        _bpmh(s2_id, session, [
            {"drug": "warfarin", "dose": "3mg", "route": "oral", "freq": "1x1", "is_high_alert": True},
            {"drug": "aspirin", "dose": "100mg", "route": "oral", "freq": "1x1"},
        ])
        _analysis(s2_id, session, [
            {"rule_type": "ddi", "severity_tier": 1, "drug_name": "warfarin + aspirin", "is_high_alert": True,
             "evidence": "Kombinasi warfarin + aspirin: risiko perdarahan mayor. DDI Tier-1."},
            {"rule_type": "allergy_conflict", "severity_tier": 1, "drug_name": "cefadroxil",
             "is_high_alert": False,
             "evidence": "Pasien alergi penisilin. Cefadroxil (sefalosporin) berpotensi reaksi silang (~5-10%)."},
        ], ml_score=0.78, tier="HIGH")

        # -----------------------------------------------------------------------
        # S3: Omisi insulin — harus konfirmasi high-alert sebelum APPROVE
        # -----------------------------------------------------------------------
        s3_id = _enc("DEMO-S03", "Tn. K.W.", "PENYAKIT_DALAM", 1.5, session, tier="HIGH", ml_score=0.82)
        _bpmh(s3_id, session, [
            {"drug": "insulin glargine", "dose": "20IU", "route": "SC", "freq": "1x malam", "is_high_alert": True},
            {"drug": "metformin", "dose": "500mg", "route": "oral", "freq": "2x1"},
        ])
        _analysis(s3_id, session, [
            {"rule_type": "omission", "severity_tier": 1, "drug_name": "insulin glargine", "is_high_alert": True,
             "evidence": "Insulin basal tidak dilanjutkan pada pesanan admisi. Risiko hiperglikemia berat.",
             "is_relevant": None},  # Belum dikonfirmasi → blokir APPROVE
        ], ml_score=0.82, tier="HIGH")

        # -----------------------------------------------------------------------
        # S4: Polypharmacy lansia, banyak diskrepansi Tier-2
        # -----------------------------------------------------------------------
        s4_id = _enc("DEMO-S04", "Ny. M.S.", "GERIATRI", 6.0, session, tier="MEDIUM", ml_score=0.55)
        _bpmh(s4_id, session, [
            {"drug": "amlodipine", "dose": "10mg", "route": "oral", "freq": "1x1"},
            {"drug": "metformin", "dose": "500mg", "route": "oral", "freq": "3x1"},
            {"drug": "omeprazole", "dose": "20mg", "route": "oral", "freq": "1x1"},
            {"drug": "atorvastatin", "dose": "40mg", "route": "oral", "freq": "1x malam"},
            {"drug": "aspirin", "dose": "100mg", "route": "oral", "freq": "1x1"},
        ])
        _analysis(s4_id, session, [
            {"rule_type": "omission", "severity_tier": 2, "drug_name": "omeprazole",
             "evidence": "Omeprazole tidak tertulis pada pesanan admisi."},
            {"rule_type": "duplication", "severity_tier": 2, "drug_name": "aspirin + clopidogrel",
             "evidence": "Duplikasi antiplatelet tanpa indikasi jelas (ACS?)."},
        ], ml_score=0.55, tier="MEDIUM")

        # -----------------------------------------------------------------------
        # S5: LLM fallback — encounter untuk tes fallback template SBAR
        # -----------------------------------------------------------------------
        s5_id = _enc("DEMO-S05", "Tn. P.A.", "BEDAH", 2.0, session, tier="MEDIUM", ml_score=0.48)
        _bpmh(s5_id, session, [
            {"drug": "metoprolol", "dose": "50mg", "route": "oral", "freq": "2x1"},
            {"drug": "losartan", "dose": "50mg", "route": "oral", "freq": "1x1"},
        ])
        _analysis(s5_id, session, [
            {"rule_type": "omission", "severity_tier": 2, "drug_name": "metoprolol",
             "evidence": "Metoprolol tidak tertulis pada pesanan pra-operasi."},
        ], ml_score=0.48, tier="MEDIUM")

        # -----------------------------------------------------------------------
        # S6: Guardrail test — encounter untuk tes penolakan LLM menyebut obat fiktif
        # -----------------------------------------------------------------------
        s6_id = _enc("DEMO-S06", "Ny. D.L.", "NEUROLOGI", 4.0, session, tier="MEDIUM", ml_score=0.52)
        _bpmh(s6_id, session, [
            {"drug": "phenytoin", "dose": "100mg", "route": "oral", "freq": "3x1"},
        ])
        _analysis(s6_id, session, [
            {"rule_type": "omission", "severity_tier": 2, "drug_name": "phenytoin",
             "evidence": "Phenytoin tidak tertulis pada pesanan admisi."},
        ], ml_score=0.52, tier="MEDIUM")

        # -----------------------------------------------------------------------
        # S7: SLA breach — menunggu > 2 jam, tier HIGH, belum diklaim
        # -----------------------------------------------------------------------
        # S7: 3 jam lalu → SLA breach (HIGH SLA = 2 jam target)
        s7_id = _enc("DEMO-S07", "Tn. H.F.", "ICU", 3.0, session, tier="HIGH", ml_score=0.91)
        _bpmh(s7_id, session, [
            {"drug": "heparin", "dose": "5000IU", "route": "IV", "freq": "tiap 8 jam", "is_high_alert": True},
            {"drug": "fentanyl", "dose": "50mcg", "route": "IV", "freq": "PRN", "is_high_alert": True},
        ])
        _analysis(s7_id, session, [
            {"rule_type": "omission", "severity_tier": 1, "drug_name": "heparin", "is_high_alert": True,
             "evidence": "Heparin IV tidak tertulis pada pesanan ICU. Pasien post-op by-pass."},
        ], ml_score=0.91, tier="HIGH")

        # -----------------------------------------------------------------------
        # S8: Tidak minum obat rutin — BPMH selesai, tidak ada diskrepansi
        # -----------------------------------------------------------------------
        s8_id = _enc("DEMO-S08", "Tn. J.R.", "BEDAH", 1.0, session, tier="LOW", ml_score=0.22)
        _bpmh(s8_id, session, [], no_routine_meds=True)
        _analysis(s8_id, session, [], ml_score=0.22, tier="LOW")

        # -----------------------------------------------------------------------
        # S9: Apoteker EDIT → SELESAI_EDIT (akan dijalankan oleh test/demo)
        # -----------------------------------------------------------------------
        s9_id = _enc("DEMO-S09", "Ny. A.N.", "PENYAKIT_DALAM", 2.5, session, tier="MEDIUM", ml_score=0.61)
        _bpmh(s9_id, session, [
            {"drug": "captopril", "dose": "25mg", "route": "oral", "freq": "2x1"},
            {"drug": "simvastatin", "dose": "20mg", "route": "oral", "freq": "1x malam"},
        ])
        _analysis(s9_id, session, [
            {"rule_type": "substitution", "severity_tier": 2, "drug_name": "captopril → enalapril",
             "evidence": "Captopril diganti enalapril pada pesanan admisi tanpa dokumentasi alasan."},
        ], ml_score=0.61, tier="MEDIUM")

        # -----------------------------------------------------------------------
        # S10: Full flow — BPMH → analisis → APPROVE → audit hash valid
        # -----------------------------------------------------------------------
        s10_id = _enc("DEMO-S10", "Ny. F.K.", "JANTUNG", 2.0, session, tier="MEDIUM", ml_score=0.57)
        _bpmh(s10_id, session, [
            {"drug": "bisoprolol", "dose": "5mg", "route": "oral", "freq": "1x1"},
            {"drug": "atorvastatin", "dose": "40mg", "route": "oral", "freq": "1x malam"},
        ])
        _analysis(s10_id, session, [
            {"rule_type": "omission", "severity_tier": 2, "drug_name": "bisoprolol",
             "evidence": "Bisoprolol tidak tertulis pada pesanan admisi."},
        ], ml_score=0.57, tier="MEDIUM")

        session.commit()
        print("[seed] Skenario S1–S10 berhasil di-seed.")
        print()
        print("Akun demo:")
        print("  apoteker1 / demo1234  (PHARMACIST)")
        print("  ttk1 / demo1234       (TECHNICIAN)")
        print("  koordinator1 / demo1234 (COORDINATOR)")
        print("  admin / admin1234     (ADMIN)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_user(session, User, user_id, username, full_name, role, password, hash_password):
    existing = session.query(User).filter(User.id == user_id).first()
    if existing:
        return existing
    u = User(
        id=user_id,
        username=username,
        full_name=full_name,
        role=role,
        hashed_password=hash_password(password),
        is_active=True,
        created_at=_now_utc(),
    )
    session.add(u)
    return u


def _ensure_sla_config(session, SlaConfig):
    if session.query(SlaConfig).count() > 0:
        return
    defaults = [
        SlaConfig(tier="HIGH",   target_hours=2.0,  warning_hours=1.0,  escalate_to_tier=None,     business_hours_only=False),
        SlaConfig(tier="MEDIUM", target_hours=8.0,  warning_hours=4.0,  escalate_to_tier="HIGH",   business_hours_only=False),
        SlaConfig(tier="LOW",    target_hours=24.0, warning_hours=16.0, escalate_to_tier="MEDIUM", business_hours_only=False),
    ]
    for cfg in defaults:
        session.add(cfg)


def _enc(patient_id, patient_name, ward, hours_ago, session,
         tier="MEDIUM", ml_score=None):
    """Create or return existing demo encounter."""
    hours_ago_final = hours_ago
    from api.db.models import Encounter
    existing = session.query(Encounter).filter(Encounter.patient_id == patient_id).first()
    if existing:
        return existing.id

    enc_id = str(uuid.uuid4())
    enc = Encounter(
        id=enc_id,
        patient_id=patient_id,
        patient_name=patient_name,
        ward=ward,
        workflow_status="MENUNGGU_TELAAH",
        latest_tier=tier,
        ml_score=ml_score,
        admitted_at=_ts(hours_ago_final),
        row_version=0,
        created_at=_ts(hours_ago_final),
        updated_at=_now_utc(),
    )
    session.add(enc)
    return enc_id


def _bpmh(encounter_id, session, meds, no_routine_meds=False):
    """Add BPMH items to encounter."""
    from api.db.models import BpmhItem
    if no_routine_meds:
        # Tambah satu item placeholder "tidak minum obat rutin"
        item = BpmhItem(
            id=str(uuid.uuid4()),
            encounter_id=encounter_id,
            drug_name_raw="TIDAK MINUM OBAT RUTIN",
            drug_name_normalized="TIDAK MINUM OBAT RUTIN",
            source="pasien",
            source_reliability="tinggi",
            is_high_alert=False,
            created_at=_now_utc(),
        )
        session.add(item)
        return

    for med in meds:
        item = BpmhItem(
            id=str(uuid.uuid4()),
            encounter_id=encounter_id,
            drug_name_raw=med["drug"],
            drug_name_normalized=med["drug"],
            drug_generic=med["drug"],
            dose=med.get("dose"),
            route=med.get("route"),
            frequency=med.get("freq"),
            source="pasien",
            source_reliability="sedang",
            is_high_alert=med.get("is_high_alert", False),
            normalization_method="exact",
            normalization_confidence=0.95,
            created_at=_now_utc(),
        )
        session.add(item)


def _analysis(encounter_id, session, discs, ml_score=None, tier="MEDIUM"):
    """Add analysis run + discrepancies."""
    from api.db.models import AnalysisRun, Discrepancy
    run_id = str(uuid.uuid4())
    tier1_count = sum(1 for d in discs if d.get("severity_tier", 2) == 1)
    ha_count = sum(1 for d in discs if d.get("is_high_alert", False))
    run = AnalysisRun(
        id=run_id,
        encounter_id=encounter_id,
        run_at=_now_utc(),
        model_version="v4.0.0-demo",
        rule_version="rules-0.2.0",
        ml_score=ml_score,
        ml_tier=tier,
        final_tier=tier,
        findings_count=len(discs),
        tier1_count=tier1_count,
        high_alert_count=ha_count,
        triggered_by="seed_demo",
    )
    session.add(run)

    for d in discs:
        disc = Discrepancy(
            id=str(uuid.uuid4()),
            analysis_run_id=run_id,
            encounter_id=encounter_id,
            rule_type=d.get("rule_type", "omission"),
            severity_tier=d.get("severity_tier", 2),
            drug_name=d.get("drug_name"),
            evidence=d.get("evidence"),
            is_high_alert=d.get("is_high_alert", False),
            is_relevant=d.get("is_relevant"),  # None = belum dikonfirmasi
            verification_required=True,
        )
        session.add(disc)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo data PrioMed-Rec")
    parser.add_argument("--reset", action="store_true", help="Hapus data demo lama sebelum seed")
    parser.add_argument("--db-path", default="data/priomed.db", help="Path database SQLite")
    args = parser.parse_args()

    import os
    os.environ.setdefault("DB_PATH", args.db_path)

    seed(db_path=args.db_path, reset=args.reset)
    print("[seed] Selesai.")
