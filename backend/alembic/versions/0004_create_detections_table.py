"""Create detections table

Revision ID: a1b2c3d4e5f6
Revises: 18d7c3a397a0
Create Date: 2026-02-14 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "18d7c3a397a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "detections",
        sa.Column("id",               sa.Integer(),                        nullable=False),
        sa.Column("created_at",       sa.DateTime(timezone=True),          nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",       sa.DateTime(timezone=True),          nullable=False, server_default=sa.text("now()")),
        sa.Column("animal_id",        sa.Integer(),                        nullable=True),
        sa.Column("camera_id",        sa.String(50),                       nullable=False),
        sa.Column("timestamp",        sa.DateTime(timezone=True),          nullable=False),
        sa.Column("confidence",       sa.Float(),                          nullable=False),
        sa.Column("class_id",         sa.Integer(),                        nullable=False),
        sa.Column("class_name",       sa.String(50),                       nullable=False),
        sa.Column("bbox",             sa.JSON(),                           nullable=False),
        sa.Column("estimated_weight", sa.Float(),                          nullable=True),
        sa.Column("frame_number",     sa.Integer(),                        nullable=True),
        sa.Column("inference_time_ms",sa.Float(),                          nullable=True),

        sa.ForeignKeyConstraint(
            ["animal_id"], ["animals.id"],
            ondelete="SET NULL",
            name="fk_detections_animal_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_detections"),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_detection_confidence_range",
        ),
        sa.CheckConstraint(
            "estimated_weight IS NULL OR estimated_weight > 0",
            name="ck_detection_weight_positive",
        ),
    )

    # Indexes for time-series queries
    op.create_index("ix_detections_animal_id",    "detections", ["animal_id"])
    op.create_index("ix_detections_camera_id",    "detections", ["camera_id"])
    op.create_index("ix_detections_timestamp",    "detections", ["timestamp"])
    op.create_index("ix_detections_confidence",   "detections", ["confidence"])
    op.create_index("ix_detections_animal_time",  "detections", ["animal_id",  "timestamp"])
    op.create_index("ix_detections_camera_time",  "detections", ["camera_id",  "timestamp"])
    op.create_index("ix_detections_class_time",   "detections", ["class_id",   "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_detections_class_time",   table_name="detections")
    op.drop_index("ix_detections_camera_time",  table_name="detections")
    op.drop_index("ix_detections_animal_time",  table_name="detections")
    op.drop_index("ix_detections_confidence",   table_name="detections")
    op.drop_index("ix_detections_timestamp",    table_name="detections")
    op.drop_index("ix_detections_camera_id",    table_name="detections")
    op.drop_index("ix_detections_animal_id",    table_name="detections")
    op.drop_table("detections")
