"""
api/db/models.py
-----------------
SQLAlchemy ORM models untuk semua tabel PrioMed-Rec.

Tabel legacy (migrasi dari api/database.py raw SQLite):
  - bpmh_records       — BPMH per patient/encounter (legacy, dipertahankan)
  - ward_configs       — Konfigurasi kapasitas bangsal
  - local_high_alert   — Registri obat high-alert lokal RS

Tabel baru (B-102 — skema lengkap):
  - users              — Pengguna sistem (apoteker, TTK, koordinator, admin, auditor)
  - encounters         — Encounter admisi pasien
  - bpmh_items         — Item BPMH (obat individual per encounter)
  - analysis_runs      — Hasil analisis ML + rule engine per encounter
  - discrepancies      — Temuan diskrepansi per analisis
  - sbar_drafts        — Draf SBAR per encounter
  - sbar_revisions     — Revisi SBAR (history)
  - status_history     — Riwayat perubahan status encounter
  - sla_events         — Event SLA (WARNING, BREACH, ESCALATED)
  - notifications      — Notifikasi per pengguna
  - drug_alias         — Tabel alias nama obat (merek dagang → generik)
  - sla_config         — Konfigurasi SLA (dapat diubah Admin)
  - audit_entries      — Audit trail append-only dengan hash-chain (ADR-12)

Tabel antrean (Q-001 — manajemen antrean skala RS):
  - queue_entries      — Antrean terdenormalisasi (A: BPMH, B: Telaah) — ADR-19
  - queue_events       — Jejak diff SSE + audit operasional
  - missed_reconciliations — Pasien pulang sebelum rekonsiliasi selesai (Q7)

Prinsip:
  - Semua tabel menggunakan UUID string sebagai PK
  - Semua timestamp dalam ISO 8601 UTC (string untuk SQLite portability)
  - audit_entries hanya boleh di-INSERT, tidak boleh di-UPDATE/DELETE (dijaga di app level)
  - queue_entries: tier_rank hanya boleh NAIK oleh aturan/SLA (ADR-21)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, ForeignKey, Index, Integer, Numeric,
    SmallInteger, String, Text, Float, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from api.db.session import Base


def _now_utc() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Tabel legacy (kompatibilitas dengan api/database.py)
# ---------------------------------------------------------------------------

class BpmhRecord(Base):
    """BPMH per patient/encounter — tabel legacy, dipertahankan untuk kompatibilitas."""
    __tablename__ = "bpmh_records"

    patient_id       = Column(String, nullable=False)
    encounter_id     = Column(String, nullable=False)
    pharmacist_id    = Column(String, nullable=True)
    saved_at         = Column(String, nullable=False, default=_now_utc)
    source_notes     = Column(Text, nullable=True)
    medications_json = Column(Text, nullable=False, default="[]")

    __table_args__ = (
        UniqueConstraint("patient_id", "encounter_id", name="uq_bpmh_patient_encounter"),
        {"extend_existing": True},
    )
    # Composite PK via text (biarkan sqlalchemy handle via __mapper_args__)
    patient_id.__doc__ = "Part of composite PK"
    # Workaround: define a surrogate PK untuk SQLAlchemy
    id = Column(Integer, primary_key=True, autoincrement=True)


class WardConfig(Base):
    """Konfigurasi kapasitas bangsal."""
    __tablename__ = "ward_configs"

    ward_id      = Column(String, primary_key=True)
    ward_name    = Column(String, nullable=False)
    capacity     = Column(Integer, nullable=False, default=10)
    allocated    = Column(Integer, nullable=False, default=0)
    pharmacists  = Column(Integer, nullable=False, default=1)
    updated_at   = Column(String, nullable=True)


class LocalHighAlert(Base):
    """Registri obat high-alert lokal RS."""
    __tablename__ = "local_high_alert"

    drug_name  = Column(String, primary_key=True)
    category   = Column(String, nullable=True)
    added_by   = Column(String, nullable=True)
    added_at   = Column(String, nullable=True)


# ---------------------------------------------------------------------------
# Tabel baru — B-102
# ---------------------------------------------------------------------------

class User(Base):
    """Pengguna sistem PrioMed-Rec."""
    __tablename__ = "users"

    id           = Column(String, primary_key=True)   # UUID
    username     = Column(String, unique=True, nullable=False, index=True)
    full_name    = Column(String, nullable=False)
    role         = Column(String, nullable=False)  # PHARMACIST | TECHNICIAN | COORDINATOR | ADMIN | AUDITOR
    hashed_password = Column(String, nullable=False)
    is_active    = Column(Boolean, nullable=False, default=True)
    created_at   = Column(String, nullable=False, default=_now_utc)
    last_login   = Column(String, nullable=True)

    # Relationships
    reviews      = relationship("AuditEntry", back_populates="actor", foreign_keys="AuditEntry.actor_id")


class Encounter(Base):
    """Encounter admisi pasien."""
    __tablename__ = "encounters"

    id               = Column(String, primary_key=True)  # UUID
    patient_id       = Column(String, nullable=False, index=True)
    patient_name     = Column(String, nullable=True)  # Inisial saja (privacy)
    patient_dob      = Column(String, nullable=True)
    patient_gender   = Column(String, nullable=True)
    ward             = Column(String, nullable=True, index=True)
    dpjp_name        = Column(String, nullable=True)
    admitted_at      = Column(String, nullable=False, default=_now_utc)
    workflow_status  = Column(String, nullable=False, default="MENUNGGU_BPMH", index=True)
    latest_tier      = Column(String, nullable=True, index=True)  # Denormalized untuk performa worklist
    ml_score         = Column(Float, nullable=True)
    priority_reason  = Column(Text, nullable=True)  # JSON array of reason objects
    assigned_to      = Column(String, ForeignKey("users.id"), nullable=True)
    claimed_by       = Column(String, ForeignKey("users.id"), nullable=True)
    claimed_at       = Column(String, nullable=True)
    row_version      = Column(Integer, nullable=False, default=0)  # Optimistic concurrency
    created_at       = Column(String, nullable=False, default=_now_utc)
    updated_at       = Column(String, nullable=False, default=_now_utc, onupdate=_now_utc)

    # Relationships
    bpmh_items       = relationship("BpmhItem", back_populates="encounter")
    analysis_runs    = relationship("AnalysisRun", back_populates="encounter")
    status_history   = relationship("StatusHistory", back_populates="encounter")
    sla_events       = relationship("SlaEvent", back_populates="encounter")
    sbar_drafts      = relationship("SbarDraft", back_populates="encounter")
    audit_entries    = relationship("AuditEntry", back_populates="encounter")

    __table_args__ = (
        Index("ix_encounters_ward_status", "ward", "workflow_status"),
        Index("ix_encounters_tier_sla", "latest_tier", "admitted_at"),
    )


class BpmhItem(Base):
    """Item obat individual dalam BPMH."""
    __tablename__ = "bpmh_items"

    id              = Column(String, primary_key=True)  # UUID
    encounter_id    = Column(String, ForeignKey("encounters.id"), nullable=False, index=True)
    drug_name_raw   = Column(String, nullable=False)   # Nama asli dari input
    drug_name_normalized = Column(String, nullable=True)  # Setelah normalisasi
    drug_generic    = Column(String, nullable=True)    # Nama generik
    drug_atc        = Column(String, nullable=True)    # Kode ATC
    dose            = Column(String, nullable=True)
    route           = Column(String, nullable=True)
    frequency       = Column(String, nullable=True)
    last_taken      = Column(String, nullable=True)
    adherence       = Column(String, nullable=True)
    indication      = Column(String, nullable=True)
    disposition     = Column(String, nullable=True)  # DILANJUTKAN | DITUNDA | DIGANTI | DIHENTIKAN
    disposition_reason = Column(Text, nullable=True)
    source          = Column(String, nullable=True)  # pasien | keluarga | kemasan | apotek | rekam_medis
    source_reliability = Column(String, nullable=True)  # tinggi | sedang | rendah
    normalization_method = Column(String, nullable=True)  # exact | alias | fuzzy | kfa | unresolved
    normalization_confidence = Column(Float, nullable=True)
    is_high_alert   = Column(Boolean, nullable=False, default=False)
    created_at      = Column(String, nullable=False, default=_now_utc)

    encounter       = relationship("Encounter", back_populates="bpmh_items")


class AnalysisRun(Base):
    """Hasil analisis ML + rule engine (versi berversi — snapshot)."""
    __tablename__ = "analysis_runs"

    id              = Column(String, primary_key=True)  # UUID
    encounter_id    = Column(String, ForeignKey("encounters.id"), nullable=False, index=True)
    run_at          = Column(String, nullable=False, default=_now_utc)
    model_version   = Column(String, nullable=True)
    rule_version    = Column(String, nullable=True)
    guardrail_version = Column(String, nullable=True)
    ml_score        = Column(Float, nullable=True)
    ml_tier         = Column(String, nullable=True)
    final_tier      = Column(String, nullable=True)
    priority_reason = Column(Text, nullable=True)  # JSON
    shap_values     = Column(Text, nullable=True)  # JSON
    findings_count  = Column(Integer, nullable=False, default=0)
    tier1_count     = Column(Integer, nullable=False, default=0)
    high_alert_count = Column(Integer, nullable=False, default=0)
    triggered_by    = Column(String, nullable=True)  # manual | auto | retriage

    encounter       = relationship("Encounter", back_populates="analysis_runs")
    discrepancies   = relationship("Discrepancy", back_populates="analysis_run")


class Discrepancy(Base):
    """Temuan diskrepansi dari rule engine."""
    __tablename__ = "discrepancies"

    id              = Column(String, primary_key=True)  # UUID
    analysis_run_id = Column(String, ForeignKey("analysis_runs.id"), nullable=False, index=True)
    encounter_id    = Column(String, ForeignKey("encounters.id"), nullable=False, index=True)
    rule_type       = Column(String, nullable=False)  # omission | duplication | allergy_conflict | ddi | substitution
    severity_tier   = Column(Integer, nullable=False, default=2)  # 1 | 2 | 3
    drug_name       = Column(String, nullable=True)
    drug_code       = Column(String, nullable=True)
    evidence        = Column(Text, nullable=True)
    suggestion      = Column(Text, nullable=True)
    is_high_alert   = Column(Boolean, nullable=False, default=False)
    is_relevant     = Column(Boolean, nullable=True)   # Umpan balik apoteker
    feedback_by     = Column(String, ForeignKey("users.id"), nullable=True)
    feedback_at     = Column(String, nullable=True)
    verification_required = Column(Boolean, nullable=False, default=True)

    analysis_run    = relationship("AnalysisRun", back_populates="discrepancies")


class SbarDraft(Base):
    """Draf SBAR per encounter."""
    __tablename__ = "sbar_drafts"

    id              = Column(String, primary_key=True)  # UUID
    encounter_id    = Column(String, ForeignKey("encounters.id"), nullable=False, index=True)
    version         = Column(Integer, nullable=False, default=1)
    situation       = Column(Text, nullable=True)
    background      = Column(Text, nullable=True)
    assessment      = Column(Text, nullable=True)
    recommendation  = Column(Text, nullable=True)
    source          = Column(String, nullable=True)  # langflow | llm | template
    llm_provider    = Column(String, nullable=True)
    prompt_version  = Column(String, nullable=True)
    guardrail_passed = Column(Boolean, nullable=True)
    guardrail_report = Column(Text, nullable=True)  # JSON
    is_sent_to_dpjp = Column(Boolean, nullable=False, default=False)
    sent_at         = Column(String, nullable=True)
    created_at      = Column(String, nullable=False, default=_now_utc)
    created_by      = Column(String, ForeignKey("users.id"), nullable=True)

    encounter       = relationship("Encounter", back_populates="sbar_drafts")
    revisions       = relationship("SbarRevision", back_populates="sbar_draft")


class SbarRevision(Base):
    """Revisi SBAR oleh apoteker (history)."""
    __tablename__ = "sbar_revisions"

    id              = Column(String, primary_key=True)  # UUID
    sbar_draft_id   = Column(String, ForeignKey("sbar_drafts.id"), nullable=False, index=True)
    version         = Column(Integer, nullable=False)
    field_changed   = Column(String, nullable=False)  # situation | background | assessment | recommendation
    old_text        = Column(Text, nullable=True)
    new_text        = Column(Text, nullable=True)
    revised_by      = Column(String, ForeignKey("users.id"), nullable=True)
    revised_at      = Column(String, nullable=False, default=_now_utc)

    sbar_draft      = relationship("SbarDraft", back_populates="revisions")


class StatusHistory(Base):
    """Riwayat perubahan status encounter."""
    __tablename__ = "status_history"

    id              = Column(String, primary_key=True)  # UUID
    encounter_id    = Column(String, ForeignKey("encounters.id"), nullable=False, index=True)
    from_status     = Column(String, nullable=True)
    to_status       = Column(String, nullable=False)
    changed_by      = Column(String, ForeignKey("users.id"), nullable=True)
    changed_by_type = Column(String, nullable=False, default="human")  # human | system | agent_via_mcp
    reason          = Column(Text, nullable=True)
    changed_at      = Column(String, nullable=False, default=_now_utc, index=True)

    encounter       = relationship("Encounter", back_populates="status_history")


class SlaEvent(Base):
    """Event SLA per encounter."""
    __tablename__ = "sla_events"

    id              = Column(String, primary_key=True)  # UUID
    encounter_id    = Column(String, ForeignKey("encounters.id"), nullable=False, index=True)
    event_type      = Column(String, nullable=False)  # WARNING | BREACH | ESCALATED
    from_tier       = Column(String, nullable=True)
    to_tier         = Column(String, nullable=True)
    wait_hours      = Column(Float, nullable=True)
    sla_target_hours = Column(Float, nullable=True)
    occurred_at     = Column(String, nullable=False, default=_now_utc, index=True)
    notified        = Column(Boolean, nullable=False, default=False)

    encounter       = relationship("Encounter", back_populates="sla_events")


class Notification(Base):
    """Notifikasi in-app per pengguna."""
    __tablename__ = "notifications"

    id              = Column(String, primary_key=True)  # UUID
    user_id         = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    encounter_id    = Column(String, ForeignKey("encounters.id"), nullable=True)
    type            = Column(String, nullable=False)  # SLA_WARNING | SLA_BREACH | HIGH_ALERT | RETRIAGE
    title           = Column(String, nullable=False)
    body            = Column(Text, nullable=True)
    is_read         = Column(Boolean, nullable=False, default=False)
    created_at      = Column(String, nullable=False, default=_now_utc, index=True)


class DrugAlias(Base):
    """Tabel alias nama obat (merek dagang → generik)."""
    __tablename__ = "drug_alias"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    brand_name      = Column(String, nullable=False, index=True)  # Nama merek dagang
    generic_name    = Column(String, nullable=False, index=True)  # Nama generik
    atc_code        = Column(String, nullable=True)
    drug_class      = Column(String, nullable=True)
    is_high_alert   = Column(Boolean, nullable=False, default=False)
    confidence      = Column(Float, nullable=False, default=1.0)
    source          = Column(String, nullable=True)  # manual | kfa | rxnorm
    status          = Column(String, nullable=False, default="DRAFT_PERLU_VALIDASI_APOTEKER")
    owner           = Column(String, nullable=False, default="TBD-apoteker")
    created_at      = Column(String, nullable=False, default=_now_utc)

    __table_args__ = (
        Index("ix_drug_alias_brand", "brand_name"),
        UniqueConstraint("brand_name", "generic_name", name="uq_alias_brand_generic"),
    )


class SlaConfig(Base):
    """Konfigurasi SLA per tier (dapat diubah Admin)."""
    __tablename__ = "sla_config"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    tier             = Column(String, nullable=False, unique=True)  # HIGH | MEDIUM | LOW
    target_hours     = Column(Float, nullable=False)   # SLA target
    warning_hours    = Column(Float, nullable=False)   # Kapan peringatan dikirim
    escalate_to_tier = Column(String, nullable=True)   # Naik ke tier apa saat breach
    business_hours_only = Column(Boolean, nullable=False, default=False)
    updated_at       = Column(String, nullable=True)
    updated_by       = Column(String, nullable=True)


class AuditEntry(Base):
    """
    Audit trail append-only dengan rantai hash (ADR-12).

    PENTING:
    - Tabel ini HANYA boleh di-INSERT (tidak UPDATE/DELETE)
    - Setiap entri memiliki prev_hash dan hash untuk integritas rantai
    - Koreksi dilakukan dengan entri baru (amendment), bukan mengubah entri lama
    - actor_id dan actor_type HARUS berasal dari token (bukan dari body request)
    """
    __tablename__ = "audit_entries"

    id              = Column(String, primary_key=True)  # UUID
    seq             = Column(Integer, nullable=False, index=True)  # Sequence number untuk verifikasi chain
    encounter_id    = Column(String, ForeignKey("encounters.id"), nullable=True, index=True)
    actor_id        = Column(String, ForeignKey("users.id"), nullable=True)
    actor_type      = Column(String, nullable=False, default="human")  # human | system | agent_via_mcp
    action          = Column(String, nullable=False)  # APPROVE | EDIT | REJECT | ESCALATE | DRAFT_REVIEW | SLA_BREACH | ...
    reason_code     = Column(String, nullable=True)
    note            = Column(Text, nullable=True)
    ai_snapshot     = Column(Text, nullable=True)  # JSON: hasil ML/rules/SBAR yang dilihat saat memutuskan
    model_version   = Column(String, nullable=True)
    rule_version    = Column(String, nullable=True)
    guardrail_version = Column(String, nullable=True)
    client_ip       = Column(String, nullable=True)
    prev_hash       = Column(String, nullable=True)  # Hash entri sebelumnya
    hash            = Column(String, nullable=True)  # SHA256(prev_hash || canonical_json(payload))
    ts              = Column(String, nullable=False, default=_now_utc, index=True)

    # Backward compatibility fields (dari database.py lama)
    case_id         = Column(String, nullable=True)   # Alias encounter_id untuk legacy
    patient_id      = Column(String, nullable=True)   # Denormalized dari encounter
    pharmacist_id   = Column(String, nullable=True)   # Alias actor_id untuk legacy
    timestamp       = Column(String, nullable=True)   # Alias ts untuk legacy
    ai_result_json  = Column(Text, nullable=True)     # Alias ai_snapshot untuk legacy

    actor           = relationship("User", back_populates="reviews", foreign_keys=[actor_id])
    encounter       = relationship("Encounter", back_populates="audit_entries")

    __table_args__ = (
        Index("ix_audit_actor_ts", "actor_id", "ts"),
        Index("ix_audit_encounter_ts", "encounter_id", "ts"),
    )


# ---------------------------------------------------------------------------
# Tabel antrean — Q-001 (ADR-19, ADR-21)
# ---------------------------------------------------------------------------

class QueueEntry(Base):
    """
    Antrean terdenormalisasi untuk worklist apoteker/TTK.

    ADR-19: dua antrean (queue_type=BPMH|REVIEW) + pull-based + lease 15 menit.
    ADR-21: tier_rank hanya boleh NAIK; lantai aturan klinis tidak pernah turun.
    Q5    : tidak ada panggilan LLM di jalur antrean ini.

    state: OPEN | CLAIMED | PARKED_DPJP | CLOSED
    tier_rank: 2=HIGH  1=MEDIUM  0=LOW
    tier_source: RULE | ML | SLA
    depth_level: 3=penuh  2=standar  1=ringan (default OFF, Q-020)
    """
    __tablename__ = "queue_entries"

    encounter_id         = Column(String, ForeignKey("encounters.id"), primary_key=True)
    queue_type           = Column(String, nullable=False)          # BPMH | REVIEW
    ward                 = Column(String, nullable=False)
    state                = Column(String, nullable=False, default="OPEN")  # OPEN|CLAIMED|PARKED_DPJP|CLOSED
    tier_rank            = Column(SmallInteger, nullable=False, default=1)  # 2=HIGH 1=MED 0=LOW
    tier_source          = Column(String, nullable=False, default="ML")    # RULE|ML|SLA
    priority_score       = Column(Float, nullable=False, default=0.0)      # 0–100
    ml_percentile        = Column(Float, nullable=True)                    # 0–1, dalam bangsal
    depth_level          = Column(SmallInteger, nullable=False, default=2) # 3|2|1
    admitted_at          = Column(String, nullable=False)
    sla_due_at           = Column(String, nullable=True)
    next_due_at          = Column(String, nullable=True)           # ambang SLA berikutnya
    discharge_planned_at = Column(String, nullable=True)
    claimed_by           = Column(String, ForeignKey("users.id"), nullable=True)
    claim_expires_at     = Column(String, nullable=True)           # TTL lease
    queue_version        = Column(BigInteger, nullable=False, default=0)
    updated_at           = Column(String, nullable=False, default=_now_utc)

    __table_args__ = (
        # Indeks utama untuk GET /queue — tier DESC, score DESC, encounter_id (keyset)
        Index("ix_qe_list", "queue_type", "ward", "state", "tier_rank", "priority_score", "encounter_id"),
        # Indeks untuk tick SLA — ambil entri yang jatuh tempo
        Index("ix_qe_due", "next_due_at", "state"),
        # Indeks untuk lease cleanup
        Index("ix_qe_claim", "claimed_by", "claim_expires_at"),
    )


class QueueEvent(Base):
    """
    Jejak operasional antrean — dipakai untuk diff SSE dan audit.

    kind: upsert | remove | claim | release | promote | expire
    Catatan: BigInteger PK di SQLite memerlukan nullable=False + autoincrement via Integer.
    Di PostgreSQL gunakan BIGSERIAL (Alembic handle otomatis via sa.BigInteger).
    """
    __tablename__ = "queue_events"

    seq          = Column(Integer, primary_key=True, autoincrement=True)
    encounter_id = Column(String, nullable=False, index=True)
    kind         = Column(String, nullable=False)   # upsert|remove|claim|release|promote|expire
    payload_json = Column(Text, nullable=False, default="{}")
    at           = Column(String, nullable=False, default=_now_utc, index=True)


class MissedReconciliation(Base):
    """
    Pasien yang pulang (DISCHARGE) sebelum rekonsiliasi selesai.

    Indikator keselamatan utama (Q7 aturan antrean):
    'Pasien pulang sebelum rekonsiliasi selesai HARUS tercatat di sini (bukan hilang diam-diam).'
    """
    __tablename__ = "missed_reconciliations"

    encounter_id  = Column(String, primary_key=True)
    discharged_at = Column(String, nullable=False)
    last_state    = Column(String, nullable=True)
    last_tier     = Column(String, nullable=True)
    reason        = Column(String, nullable=True)   # DISCHARGE_BEFORE_REVIEW|CANCEL|TIMEOUT
