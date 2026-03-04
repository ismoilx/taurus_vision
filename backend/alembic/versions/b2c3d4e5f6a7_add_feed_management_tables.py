"""add_feed_management_tables

Sprint 20: Ozuqa boshqaruvi uchun feed_stocks va feed_records jadvallari.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-04 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision:      str              = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # ── feed_stocks ──────────────────────────────────────────────────────
    op.create_table(
        "feed_stocks",
        sa.Column("id",         sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),

        sa.Column("feed_type",        sa.String(30),  nullable=False),
        sa.Column("name",             sa.String(200), nullable=False),
        sa.Column("description",      sa.Text(),      nullable=True),
        sa.Column("unit",             sa.String(10),  nullable=False, server_default="kg"),

        sa.Column("current_kg",       sa.Float(), nullable=False, server_default="0"),
        sa.Column("min_threshold_kg", sa.Float(), nullable=False, server_default="100"),

        sa.Column("unit_cost_uzs",    sa.Integer(),              nullable=True),
        sa.Column("supplier",         sa.String(200),            nullable=True),
        sa.Column("purchase_date",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("expiry_date",      sa.DateTime(timezone=True), nullable=True),

        sa.Column("is_active",          sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("low_stock_alerted",  sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes",              sa.Text(),    nullable=True),
    )
    op.create_index("ix_feed_stocks_feed_type",   "feed_stocks", ["feed_type"])
    op.create_index("ix_feed_stocks_type_active", "feed_stocks", ["feed_type", "is_active"])
    op.create_index("ix_feed_stocks_expiry",      "feed_stocks", ["expiry_date"])

    # ── feed_records ─────────────────────────────────────────────────────
    op.create_table(
        "feed_records",
        sa.Column("id",         sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),

        sa.Column("stock_id",    sa.Integer(),
                  sa.ForeignKey("feed_stocks.id",  ondelete="RESTRICT"),  nullable=False),
        sa.Column("animal_id",   sa.Integer(),
                  sa.ForeignKey("animals.id",      ondelete="SET NULL"),   nullable=True),
        sa.Column("fed_by",      sa.Integer(),
                  sa.ForeignKey("users.id",        ondelete="SET NULL"),   nullable=True),

        sa.Column("quantity_kg", sa.Float(),                    nullable=False),
        sa.Column("fed_at",      sa.DateTime(timezone=True),    nullable=False),
        sa.Column("notes",       sa.Text(),                     nullable=True),
        sa.Column("meta",        postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_feed_records_stock_date",  "feed_records", ["stock_id", "fed_at"])
    op.create_index("ix_feed_records_animal_date", "feed_records", ["animal_id", "fed_at"])
    op.create_index("ix_feed_records_fed_by",      "feed_records", ["fed_by"])
    op.create_index("ix_feed_records_fed_at",      "feed_records", ["fed_at"])


def downgrade() -> None:
    op.drop_index("ix_feed_records_fed_at",      "feed_records")
    op.drop_index("ix_feed_records_fed_by",       "feed_records")
    op.drop_index("ix_feed_records_animal_date",  "feed_records")
    op.drop_index("ix_feed_records_stock_date",   "feed_records")
    op.drop_table("feed_records")

    op.drop_index("ix_feed_stocks_expiry",        "feed_stocks")
    op.drop_index("ix_feed_stocks_type_active",   "feed_stocks")
    op.drop_index("ix_feed_stocks_feed_type",     "feed_stocks")
    op.drop_table("feed_stocks")