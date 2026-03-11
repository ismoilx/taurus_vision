"""add_notifications_table

Revision ID: r2s3t4u5v6w7
Revises: q1r2s3t4u5v6
Create Date: 2026-03-06 14:00:00.000000

In-app notification tizimi uchun notifications jadvali qo'shildi.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str        = 'r2s3t4u5v6w7'
down_revision: Union[str, None] = 'q1r2s3t4u5v6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on:   Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enum turlari — IF NOT EXISTS bilan xavfsiz yaratish ─────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE notification_type_enum AS ENUM
                ('info', 'success', 'warning', 'alert', 'system');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE notification_entity_type_enum AS ENUM
                ('animal', 'camera', 'sensor', 'alert', 'task',
                 'training', 'report', 'system', 'user');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # ── notifications jadvali mavjudligini tekshir ────────────────────────────
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='notifications')"
    ))
    if result.scalar():
        return  # jadval allaqachon bor — o'tkazib yuborish

    # ── notifications jadvali — String ishlatamiz (enum yuqorida yaratilgan) ──
    op.create_table(
        "notifications",

        sa.Column("id",           sa.Integer(),    nullable=False, primary_key=True, autoincrement=True),
        sa.Column("user_id",      sa.Integer(),    nullable=True,
                  comment="NULL = broadcast (barcha foydalanuvchilarga)"),

        sa.Column("n_type",       sa.String(20),   nullable=False, server_default="info"),

        sa.Column("title",        sa.String(120),  nullable=False),
        sa.Column("message",      sa.Text(),       nullable=False),

        sa.Column("entity_type",  sa.String(20),   nullable=True),
        sa.Column("entity_id",    sa.Integer(),    nullable=True),
        sa.Column("action_url",   sa.String(255),  nullable=True),

        sa.Column("is_read",      sa.Boolean(),    nullable=False, server_default="false"),
        sa.Column("read_at",      sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_dismissed", sa.Boolean(),    nullable=False, server_default="false"),

        sa.Column("extra_data",   postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        sa.Column("created_at",   sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at",   sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),

        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_notifications_user_id",
            ondelete="CASCADE",
        ),
    )

    # ── Indekslar ─────────────────────────────────────────────────────────────
    op.create_index(
        "ix_notification_user_unread",
        "notifications",
        ["user_id", "is_read"],
        postgresql_where=sa.text("is_dismissed = false"),
    )
    op.create_index(
        "ix_notification_user_created",
        "notifications",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_notification_type_created",
        "notifications",
        ["n_type", "created_at"],
    )
    op.create_index(
        "ix_notification_broadcast",
        "notifications",
        ["is_read", "created_at"],
        postgresql_where=sa.text("user_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_notification_broadcast",    table_name="notifications")
    op.drop_index("ix_notification_type_created", table_name="notifications")
    op.drop_index("ix_notification_user_created", table_name="notifications")
    op.drop_index("ix_notification_user_unread",  table_name="notifications")
    op.drop_table("notifications")

    op.execute("DROP TYPE IF EXISTS notification_entity_type_enum;")
    op.execute("DROP TYPE IF EXISTS notification_type_enum;")