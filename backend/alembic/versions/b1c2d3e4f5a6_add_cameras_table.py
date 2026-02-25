"""add cameras table

Revision ID: b1c2d3e4f5a6
Revises: a2e5c73483c5
Create Date: 2026-02-25 08:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a2e5c73483c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # PostgreSQL'da xavfsiz TYPE yaratish (agar yo'q bo'lsa)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'camera_type') THEN
                CREATE TYPE camera_type AS ENUM ('simulated', 'usb', 'rtsp');
            END IF;
        END
        $$;
    """)
    op.create_table(
        'cameras',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('camera_id', sa.String(64), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('type', ENUM('simulated', 'usb', 'rtsp', name='camera_type', create_type=False), nullable=False),
        sa.Column('source', sa.String(512), nullable=True),
        sa.Column('device_index', sa.Integer(), nullable=True),
        sa.Column('fps', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('camera_id', name='uq_cameras_camera_id')
    )

def downgrade() -> None:
    op.drop_table('cameras')
    op.execute("DROP TYPE IF EXISTS camera_type")
