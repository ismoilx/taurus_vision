"""merge heads

Revision ID: j3k4l5m6n7o8
Revises: b2c3d4e5f6a7, i2j3k4l5m6n7
Create Date: 2025-01-01 00:00:00.000000

Ikki tarmoqqa ajralib qolgan migration zanjirini birlashtiradi:
  - b2c3d4e5f6a7 (add_feed_management_tables)
  - i2j3k4l5m6n7 (add_integration_tables)
"""
from typing import Union
from alembic import op


# revision identifiers
revision:      str               = 'j3k4l5m6n7o8'
down_revision: Union[str, tuple] = ('b2c3d4e5f6a7', 'i2j3k4l5m6n7')
branch_labels = None
depends_on    = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass