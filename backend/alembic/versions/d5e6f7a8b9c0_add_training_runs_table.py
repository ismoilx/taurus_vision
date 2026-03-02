"""add training_runs table

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-03-01 00:00:00.000000

YANGI JADVAL: training_runs
    - Custom YOLO fine-tuning sessiyalarini kuzatish.
    - Har bir training run — bitta yozuv.
    - is_deployed flag — hozir ishlatilayotgan modelni belgilaydi.
    - 3 ta indeks: status, is_deployed, created_at.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision:      str                              = "d5e6f7a8b9c0"
down_revision: Union[str, None]                 = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None]  = None
depends_on:    Union[str, Sequence[str], None]  = None


def upgrade() -> None:
    op.create_table(
        "training_runs",

        # ── Primary Key ──────────────────────────────────────────────────
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Internal surrogate key",
        ),

        # ── Timestamps (BaseModel) ────────────────────────────────────────
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Record creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
            comment="Record last update timestamp",
        ),

        # ── Identification ────────────────────────────────────────────────
        sa.Column(
            "run_name",
            sa.String(100),
            nullable=False,
            server_default="",
            comment="Human-readable run name",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="pending|collecting|building|training|evaluating|completed|failed|deployed",
        ),

        # ── Model Configuration ───────────────────────────────────────────
        sa.Column(
            "base_model_name",
            sa.String(100),
            nullable=False,
            server_default="yolo11n.pt",
            comment="Base model filename",
        ),
        sa.Column(
            "epochs",
            sa.Integer(),
            nullable=False,
            server_default="50",
            comment="Training epochs",
        ),
        sa.Column(
            "batch_size",
            sa.Integer(),
            nullable=False,
            server_default="8",
            comment="Batch size",
        ),
        sa.Column(
            "img_size",
            sa.Integer(),
            nullable=False,
            server_default="640",
            comment="Input image size",
        ),
        sa.Column(
            "freeze_layers",
            sa.Integer(),
            nullable=False,
            server_default="10",
            comment="Number of frozen backbone layers",
        ),

        # ── Dataset ───────────────────────────────────────────────────────
        sa.Column(
            "dataset_info",
            sa.JSON(),
            nullable=True,
            comment="Dataset statistics JSON",
        ),

        # ── Timing ────────────────────────────────────────────────────────
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Training start time",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Training completion time",
        ),

        # ── Results ───────────────────────────────────────────────────────
        sa.Column(
            "metrics",
            sa.JSON(),
            nullable=True,
            comment="Training metrics JSON",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="Error message if failed",
        ),

        # ── Deploy ────────────────────────────────────────────────────────
        sa.Column(
            "model_path",
            sa.String(500),
            nullable=True,
            comment="Saved model file path",
        ),
        sa.Column(
            "is_deployed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="True if this run's model is currently active",
        ),
        sa.Column(
            "deployed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Deployment timestamp",
        ),

        # ── Notes ─────────────────────────────────────────────────────────
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="User notes",
        ),
    )

    # ── Indexlar ──────────────────────────────────────────────────────────
    op.create_index("ix_training_runs_status",      "training_runs", ["status"])
    op.create_index("ix_training_runs_is_deployed", "training_runs", ["is_deployed"])
    op.create_index("ix_training_runs_created_at",  "training_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_training_runs_created_at",  table_name="training_runs")
    op.drop_index("ix_training_runs_is_deployed", table_name="training_runs")
    op.drop_index("ix_training_runs_status",      table_name="training_runs")
    op.drop_table("training_runs")