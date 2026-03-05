"""add muzzle_image to animals

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7o8p9q0
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'm6n7o8p9q0r1'
down_revision = 'l5m6n7o8p9q0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('animals', sa.Column(
        'muzzle_image',
        sa.String(length=500),
        nullable=True,
        comment="Tumshuq (muzzle) rasmi fayl yo'li — identifikatsiya uchun asosiy",
    ))


def downgrade() -> None:
    op.drop_column('animals', 'muzzle_image')