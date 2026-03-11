"""add_slaughter_records_table

Revision ID: u1v2w3x4y5z6
Revises: t1u2v3w4x5y6
Create Date: 2025-03-10 12:00:00.000000

Go'sht ishlab chiqarish moduli uchun slaughter_records jadvali yaratish.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'u1v2w3x4y5z6'
down_revision = 't1u2v3w4x5y6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enum turlari ──────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE slaughter_purpose AS ENUM (
                'sale', 'own_use', 'export', 'processing'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE meat_quality_grade AS ENUM (
                'premium', 'choice', 'select', 'standard', 'low'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # ── Asosiy jadval ─────────────────────────────────────────────────
    op.create_table(
        'slaughter_records',

        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Foreign key
        sa.Column('animal_id', sa.Integer(), nullable=False),

        # Sana va maqsad
        sa.Column('slaughter_date', sa.Date(), nullable=False),
        sa.Column('purpose', postgresql.ENUM('sale', 'own_use', 'export', 'processing',
                                              name='slaughter_purpose', create_type=False),
                  nullable=False, server_default='sale'),

        # Vazn ma'lumotlari
        sa.Column('live_weight_kg',    sa.Float(), nullable=True),
        sa.Column('carcass_weight_kg', sa.Float(), nullable=True),
        sa.Column('dressing_percent',  sa.Float(), nullable=True),
        sa.Column('meat_kg',           sa.Float(), nullable=False),
        sa.Column('bone_kg',           sa.Float(), nullable=True),
        sa.Column('fat_kg',            sa.Float(), nullable=True),
        sa.Column('offal_kg',          sa.Float(), nullable=True),
        sa.Column('hide_kg',           sa.Float(), nullable=True),

        # Sifat parametrlari
        sa.Column('quality_grade', postgresql.ENUM(
            'premium', 'choice', 'select', 'standard', 'low',
            name='meat_quality_grade', create_type=False
        ), nullable=True),
        sa.Column('ph_value',       sa.Float(),   nullable=True),
        sa.Column('color_score',    sa.Integer(), nullable=True),
        sa.Column('marbling_score', sa.Integer(), nullable=True),
        sa.Column('temperature_c',  sa.Float(),   nullable=True),

        # Moliyaviy
        sa.Column('price_per_kg',   sa.Float(), nullable=True),
        sa.Column('total_revenue',  sa.Float(), nullable=True),

        # Qo'shimcha
        sa.Column('veterinary_check', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('slaughtered_by',   sa.String(200), nullable=True),
        sa.Column('notes',            sa.Text(), nullable=True),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['animal_id'], ['animals.id'], ondelete='CASCADE'),

        sa.CheckConstraint('meat_kg >= 0',                                     name='check_meat_kg_positive'),
        sa.CheckConstraint('live_weight_kg IS NULL OR live_weight_kg > 0',     name='check_live_weight_positive'),
        sa.CheckConstraint('carcass_weight_kg IS NULL OR carcass_weight_kg > 0', name='check_carcass_weight_positive'),
        sa.CheckConstraint('dressing_percent IS NULL OR (dressing_percent > 0 AND dressing_percent <= 100)', name='check_dressing_percent_range'),
        sa.CheckConstraint('ph_value IS NULL OR (ph_value >= 0 AND ph_value <= 14)', name='check_ph_range'),
        sa.CheckConstraint('color_score IS NULL OR (color_score >= 1 AND color_score <= 5)',       name='check_color_score_range'),
        sa.CheckConstraint('marbling_score IS NULL OR (marbling_score >= 1 AND marbling_score <= 5)', name='check_marbling_score_range'),
    )

    # Indekslar
    op.create_index('ix_slaughter_records_id',          'slaughter_records', ['id'])
    op.create_index('ix_slaughter_records_animal_id',   'slaughter_records', ['animal_id'])
    op.create_index('ix_slaughter_records_slaughter_date', 'slaughter_records', ['slaughter_date'])
    op.create_index('ix_slaughter_animal_date',         'slaughter_records', ['animal_id', 'slaughter_date'])
    op.create_index('ix_slaughter_date',                'slaughter_records', ['slaughter_date'])

    # Animal modeliga slaughter_records relationship qo'shish uchun
    # (SQLAlchemy relationship Animal modelida qo'lda qo'shiladi)


def downgrade() -> None:
    op.drop_table('slaughter_records')
    op.execute("DROP TYPE IF EXISTS slaughter_purpose")
    op.execute("DROP TYPE IF EXISTS meat_quality_grade")