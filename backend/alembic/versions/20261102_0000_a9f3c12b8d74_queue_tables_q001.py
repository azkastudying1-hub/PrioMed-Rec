"""queue_tables_q001

Revision ID: a9f3c12b8d74
Revises: 8a108615ebc8
Create Date: 2026-11-02 00:00:00.000000+00:00

Fase Q-001: Tabel manajemen antrean skala RS.
  - queue_entries      — antrean terdenormalisasi (A: BPMH, B: Telaah)
  - queue_events       — jejak diff SSE + audit operasional
  - missed_reconciliations — pasien pulang sebelum rekonsiliasi (Q7)

Tidak ada perubahan pada tabel lama (backward-compatible).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a9f3c12b8d74'
down_revision: Union[str, None] = '8a108615ebc8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # queue_entries — antrean terdenormalisasi
    # -----------------------------------------------------------------
    op.create_table(
        'queue_entries',
        sa.Column('encounter_id',         sa.String(),     nullable=False),
        sa.Column('queue_type',           sa.String(),     nullable=False),  # BPMH|REVIEW
        sa.Column('ward',                 sa.String(),     nullable=False),
        sa.Column('state',                sa.String(),     nullable=False, server_default='OPEN'),
        sa.Column('tier_rank',            sa.SmallInteger(), nullable=False, server_default='1'),
        sa.Column('tier_source',          sa.String(),     nullable=False, server_default='ML'),
        sa.Column('priority_score',       sa.Float(),      nullable=False, server_default='0.0'),
        sa.Column('ml_percentile',        sa.Float(),      nullable=True),
        sa.Column('depth_level',          sa.SmallInteger(), nullable=False, server_default='2'),
        sa.Column('admitted_at',          sa.String(),     nullable=False),
        sa.Column('sla_due_at',           sa.String(),     nullable=True),
        sa.Column('next_due_at',          sa.String(),     nullable=True),
        sa.Column('discharge_planned_at', sa.String(),     nullable=True),
        sa.Column('claimed_by',           sa.String(),     nullable=True),
        sa.Column('claim_expires_at',     sa.String(),     nullable=True),
        sa.Column('queue_version',        sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at',           sa.String(),     nullable=False),
        sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], ),
        sa.ForeignKeyConstraint(['claimed_by'],   ['users.id'], ),
        sa.PrimaryKeyConstraint('encounter_id'),
    )
    with op.batch_alter_table('queue_entries', schema=None) as batch_op:
        # Indeks utama untuk GET /queue (tier DESC, score DESC, encounter_id — keyset)
        batch_op.create_index(
            'ix_qe_list',
            ['queue_type', 'ward', 'state', 'tier_rank', 'priority_score', 'encounter_id'],
        )
        # Indeks untuk tick SLA
        batch_op.create_index('ix_qe_due',   ['next_due_at', 'state'])
        # Indeks untuk lease cleanup
        batch_op.create_index('ix_qe_claim', ['claimed_by', 'claim_expires_at'])

    # -----------------------------------------------------------------
    # queue_events — jejak diff SSE
    # -----------------------------------------------------------------
    op.create_table(
        'queue_events',
        sa.Column('seq',          sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('encounter_id', sa.String(),     nullable=False),
        sa.Column('kind',         sa.String(),     nullable=False),
        sa.Column('payload_json', sa.Text(),       nullable=False, server_default='{}'),
        sa.Column('at',           sa.String(),     nullable=False),
        sa.PrimaryKeyConstraint('seq'),
    )
    with op.batch_alter_table('queue_events', schema=None) as batch_op:
        batch_op.create_index('ix_qev_encounter', ['encounter_id'])
        batch_op.create_index('ix_qev_at',        ['at'])

    # -----------------------------------------------------------------
    # missed_reconciliations — indikator keselamatan Q7
    # -----------------------------------------------------------------
    op.create_table(
        'missed_reconciliations',
        sa.Column('encounter_id',  sa.String(), nullable=False),
        sa.Column('discharged_at', sa.String(), nullable=False),
        sa.Column('last_state',    sa.String(), nullable=True),
        sa.Column('last_tier',     sa.String(), nullable=True),
        sa.Column('reason',        sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('encounter_id'),
    )


def downgrade() -> None:
    op.drop_table('missed_reconciliations')
    with op.batch_alter_table('queue_events', schema=None) as batch_op:
        batch_op.drop_index('ix_qev_at')
        batch_op.drop_index('ix_qev_encounter')
    op.drop_table('queue_events')
    with op.batch_alter_table('queue_entries', schema=None) as batch_op:
        batch_op.drop_index('ix_qe_claim')
        batch_op.drop_index('ix_qe_due')
        batch_op.drop_index('ix_qe_list')
    op.drop_table('queue_entries')
