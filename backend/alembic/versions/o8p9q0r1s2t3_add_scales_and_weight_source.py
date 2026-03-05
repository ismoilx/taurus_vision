"""add_scales_and_weight_source

Revision ID: o8p9q0r1s2t3
Revises: n7o8p9q0r1s2
Create Date: 2026-03-06 12:00:00.000000

Q7 — Tarozi integratsiyasi:
  - scales jadvali (tarozi qurilmalar registri)
  - weight_measurements.source ENUM qo'shish
  - weight_measurements.actual_weight_kg qo'shish
  - weight_measurements.scale_id FK qo'shish
  - weight_measurements.notes qo'shish
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'o8p9q0r1s2t3'
down_revision: Union[str, None] = 'n7o8p9q0r1s2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── 1. ENUM turlari ──────────────────────────────────────────────────────
    op.execute("CREATE TYPE scale_type   AS ENUM ('manual', 'serial', 'api')")
    op.execute("CREATE TYPE scale_status AS ENUM ('active', 'inactive', 'error')")
    op.execute("CREATE TYPE weight_source AS ENUM ('camera_ai', 'manual', 'scale_serial', 'scale_api')")

    # ─── 2. scales jadvali ────────────────────────────────────────────────────
    op.create_table(
        'scales',
        sa.Column('id',                       sa.Integer(),     primary_key=True, autoincrement=True),
        sa.Column('name',                     sa.String(100),   nullable=False),
        sa.Column('scale_type',               sa.Enum('manual', 'serial', 'api', name='scale_type'), nullable=False, server_default='manual'),
        sa.Column('location',                 sa.String(200),   nullable=True),
        sa.Column('status',                   sa.Enum('active', 'inactive', 'error', name='scale_status'), nullable=False, server_default='active'),
        sa.Column('is_active',                sa.Boolean(),     nullable=False, server_default=sa.text('true')),
        sa.Column('serial_port',              sa.String(50),    nullable=True),
        sa.Column('baud_rate',                sa.Integer(),     nullable=True,  server_default='9600'),
        sa.Column('data_format',              sa.String(50),    nullable=True,  server_default="'8N1'"),
        sa.Column('data_pattern',             sa.String(200),   nullable=True),
        sa.Column('calibration_factor',       sa.Float(),       nullable=False, server_default='1.0'),
        sa.Column('calibration_sample_count', sa.Integer(),     nullable=False, server_default='0'),
        sa.Column('last_calibrated_at',       sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_reading_at',          sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_weight_kg',           sa.Float(),       nullable=True),
        sa.Column('notes',                    sa.Text(),        nullable=True),
        sa.Column('api_token',                sa.String(128),   nullable=True),
        sa.Column('created_at',               sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at',               sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_scales_name',      'scales', ['name'])
    op.create_index('ix_scales_is_active', 'scales', ['is_active'])

    # Default "Qo'lda kiritish" tarozi yaratish
    op.execute("""
        INSERT INTO scales (name, scale_type, location, status, is_active,
                            calibration_factor, calibration_sample_count,
                            created_at, updated_at)
        VALUES ('Qo''lda kiritish', 'manual', NULL, 'active', true,
                1.0, 0, now(), now())
    """)

    # ─── 3. weight_measurements yangi ustunlar ────────────────────────────────
    op.add_column('weight_measurements', sa.Column(
        'source',
        sa.Enum('camera_ai', 'manual', 'scale_serial', 'scale_api', name='weight_source'),
        nullable=False,
        server_default='camera_ai',
    ))

    op.add_column('weight_measurements', sa.Column(
        'actual_weight_kg',
        sa.Float(),
        nullable=True,
        comment="Tarozidan kelgan haqiqiy vazn (kg)",
    ))

    op.add_column('weight_measurements', sa.Column(
        'scale_id',
        sa.Integer(),
        sa.ForeignKey('scales.id', ondelete='SET NULL'),
        nullable=True,
    ))

    op.add_column('weight_measurements', sa.Column(
        'notes',
        sa.Text(),
        nullable=True,
    ))

    op.create_index('ix_weight_measurements_source',   'weight_measurements', ['source'])
    op.create_index('ix_weight_measurements_scale_id', 'weight_measurements', ['scale_id'])


def downgrade() -> None:
    op.drop_index('ix_weight_measurements_scale_id', table_name='weight_measurements')
    op.drop_index('ix_weight_measurements_source',   table_name='weight_measurements')
    op.drop_column('weight_measurements', 'notes')
    op.drop_column('weight_measurements', 'scale_id')
    op.drop_column('weight_measurements', 'actual_weight_kg')
    op.drop_column('weight_measurements', 'source')

    op.drop_index('ix_scales_is_active', table_name='scales')
    op.drop_index('ix_scales_name',      table_name='scales')
    op.drop_table('scales')

    op.execute("DROP TYPE IF EXISTS weight_source")
    op.execute("DROP TYPE IF EXISTS scale_status")
    op.execute("DROP TYPE IF EXISTS scale_type")