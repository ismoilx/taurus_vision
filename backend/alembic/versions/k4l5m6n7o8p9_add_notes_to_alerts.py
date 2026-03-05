"""add notes column to alerts table

Revision ID: k4l5m6n7o8p9
Revises: j3k4l5m6n7o8
Create Date: 2026-01-01 00:00:00.000000

alerts jadvaliga notes ustuni qo'shiladi.
Model da mavjud lekin migration da yo'q edi.
"""
from typing import Union
import sqlalchemy as sa
from alembic import op


revision:      str               = 'k4l5m6n7o8p9'
down_revision: Union[str, None]  = 'j3k4l5m6n7o8'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.add_column(
        'alerts',
        sa.Column(
            'notes',
            sa.Text(),
            nullable=True,
            comment='User notes when resolving or reviewing alert',
        ),
    )


def downgrade() -> None:
    op.drop_column('alerts', 'notes')