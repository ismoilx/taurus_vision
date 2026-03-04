"""add_farm_tasks_table

Sprint 19-20: Ferma vazifalari boshqaruvi uchun farm_tasks jadvali.

Revision ID: a1b2c3d4e5f6
Revises: 0f8f38fe3f92
Create Date: 2026-03-04 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision:      str               = "a1b2c3d4e5f6"
down_revision: Union[str, None]  = "0f8f38fe3f92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on:    Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "farm_tasks",

        # PK + timestamps (BaseModel pattern)
        sa.Column("id",         sa.Integer(),                    nullable=False, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True),      nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),      nullable=False, server_default=sa.text("now()"),
                  onupdate=sa.text("now()")),

        # Core fields
        sa.Column("title",       sa.String(300),  nullable=False,
                  comment="Vazifa sarlavhasi"),
        sa.Column("description", sa.Text(),        nullable=True,
                  comment="Batafsil tavsif"),
        sa.Column("task_type",   sa.String(30),   nullable=False,
                  comment="Vazifa turi: vaccination, health_check, feeding..."),
        sa.Column("priority",    sa.String(20),   nullable=False, server_default="medium",
                  comment="Muhimlik darajasi: low, medium, high, critical"),
        sa.Column("status",      sa.String(20),   nullable=False, server_default="pending",
                  comment="Holat: pending, in_progress, completed, overdue, cancelled"),

        # Timestamps
        sa.Column("due_date",      sa.DateTime(timezone=True), nullable=True,
                  comment="Bajarish muddati"),
        sa.Column("started_at",    sa.DateTime(timezone=True), nullable=True,
                  comment="Bajarishga kirishilgan vaqt"),
        sa.Column("completed_at",  sa.DateTime(timezone=True), nullable=True,
                  comment="Bajarilgan vaqt"),

        # FK
        sa.Column("animal_id",   sa.Integer(), sa.ForeignKey("animals.id",  ondelete="SET NULL"), nullable=True,
                  comment="Qaysi jonivorga tegishli"),
        sa.Column("assigned_to", sa.Integer(), sa.ForeignKey("users.id",    ondelete="SET NULL"), nullable=True,
                  comment="Kim bajaradi"),
        sa.Column("created_by",  sa.Integer(), sa.ForeignKey("users.id",    ondelete="SET NULL"), nullable=True,
                  comment="Kim yaratdi"),
        sa.Column("recurring_source_id", sa.Integer(),
                  sa.ForeignKey("farm_tasks.id", ondelete="SET NULL"), nullable=True,
                  comment="Takrorlanuvchi vazifa manba ID si"),

        # Extra
        sa.Column("notes", sa.Text(),                    nullable=True,
                  comment="Bajaruvchi izohi"),
        sa.Column("meta",  postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment="Qo'shimcha ma'lumot: doza, mahsulot, miqdor"),

        sa.PrimaryKeyConstraint("id", name="pk_farm_tasks"),
    )

    # Indekslar
    op.create_index("ix_farm_tasks_status",          "farm_tasks", ["status"])
    op.create_index("ix_farm_tasks_task_type",        "farm_tasks", ["task_type"])
    op.create_index("ix_farm_tasks_priority",         "farm_tasks", ["priority"])
    op.create_index("ix_farm_tasks_due_date",         "farm_tasks", ["due_date"])
    op.create_index("ix_farm_tasks_animal_id",        "farm_tasks", ["animal_id"])
    op.create_index("ix_farm_tasks_assigned_to",      "farm_tasks", ["assigned_to"])

    # Composite indekslar
    op.create_index("ix_farm_tasks_status_due",      "farm_tasks", ["status", "due_date"])
    op.create_index("ix_farm_tasks_type_status",     "farm_tasks", ["task_type", "status"])
    op.create_index("ix_farm_tasks_animal_status",   "farm_tasks", ["animal_id", "status"])
    op.create_index("ix_farm_tasks_assigned_status", "farm_tasks", ["assigned_to", "status"])


def downgrade() -> None:
    op.drop_index("ix_farm_tasks_assigned_status", table_name="farm_tasks")
    op.drop_index("ix_farm_tasks_animal_status",   table_name="farm_tasks")
    op.drop_index("ix_farm_tasks_type_status",     table_name="farm_tasks")
    op.drop_index("ix_farm_tasks_status_due",      table_name="farm_tasks")
    op.drop_index("ix_farm_tasks_assigned_to",     table_name="farm_tasks")
    op.drop_index("ix_farm_tasks_animal_id",       table_name="farm_tasks")
    op.drop_index("ix_farm_tasks_due_date",        table_name="farm_tasks")
    op.drop_index("ix_farm_tasks_priority",        table_name="farm_tasks")
    op.drop_index("ix_farm_tasks_task_type",       table_name="farm_tasks")
    op.drop_index("ix_farm_tasks_status",          table_name="farm_tasks")
    op.drop_table("farm_tasks")