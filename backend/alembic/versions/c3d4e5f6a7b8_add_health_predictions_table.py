"""add health_predictions table

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-02-28 10:00:00.000000

YANGI JADVAL: health_predictions
    - Jonivor sog'liq xavfini oldindan bashorat qilish natijalarini saqlaydi.
    - Har bir jonivor uchun har kunda bitta yozuv (UniqueConstraint).
    - Cascade delete: jonivor o'chirilsa bashoratlar ham o'chadi.
    - 3 ta indeks: performance uchun.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision:       str                               = "c3d4e5f6a7b8"
down_revision:  Union[str, None]                  = "b1c2d3e4f5a6"
branch_labels:  Union[str, Sequence[str], None]   = None
depends_on:     Union[str, Sequence[str], None]   = None


def upgrade() -> None:
    op.create_table(
        "health_predictions",
        # ── Primary Key ────────────────────────────────────────────────────
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Internal surrogate key",
        ),
        # ── Foreign Key ────────────────────────────────────────────────────
        sa.Column(
            "animal_id",
            sa.Integer(),
            sa.ForeignKey("animals.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
            comment="Reference to the animal",
        ),
        # ── Date ───────────────────────────────────────────────────────────
        sa.Column(
            "prediction_date",
            sa.String(10),
            nullable=False,
            comment="Bashorat sanasi ISO format YYYY-MM-DD",
        ),
        # ── Core Result ────────────────────────────────────────────────────
        sa.Column(
            "risk_level",
            sa.String(10),
            nullable=False,
            index=True,
            comment="low | medium | high | critical",
        ),
        sa.Column(
            "risk_score",
            sa.Float(),
            nullable=False,
            comment="Final ensemble risk score (0.0 — 100.0). Higher = more risk.",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default="0.5",
            comment="Model confidence (0.0 — 1.0). Low when insufficient data.",
        ),
        # ── Ensemble Components ────────────────────────────────────────────
        sa.Column(
            "rule_risk",
            sa.Float(),
            nullable=False,
            server_default="0.0",
            comment="Rule-based component risk (0 — 100)",
        ),
        sa.Column(
            "rf_risk",
            sa.Float(),
            nullable=False,
            server_default="0.0",
            comment="RandomForest component risk (0 — 100)",
        ),
        sa.Column(
            "isolation_score",
            sa.Float(),
            nullable=False,
            server_default="0.0",
            comment="IsolationForest anomaly score converted to risk (0 — 100)",
        ),
        # ── Feature Meta ───────────────────────────────────────────────────
        sa.Column(
            "adi_days_available",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
            comment="Number of ADI records used in computation",
        ),
        sa.Column(
            "features_used",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
            comment="Total feature count fed to the model",
        ),
        # ── Trend Prediction ───────────────────────────────────────────────
        sa.Column(
            "predicted_adi_7day",
            sa.Float(),
            nullable=True,
            comment="Predicted ADI score 7 days ahead (linear extrapolation + RF)",
        ),
        sa.Column(
            "trend_direction",
            sa.String(12),
            nullable=True,
            comment="improving | stable | declining",
        ),
        # ── Explainability ─────────────────────────────────────────────────
        sa.Column(
            "risk_factors",
            sa.JSON(),
            nullable=True,
            comment="Human-readable list of detected risk factors",
        ),
        sa.Column(
            "recommendations",
            sa.JSON(),
            nullable=True,
            comment="Actionable recommendations for the farmer",
        ),
        # ── Model Meta ─────────────────────────────────────────────────────
        sa.Column(
            "model_version",
            sa.String(20),
            nullable=False,
            server_default="v1.0-ensemble",
            comment="Model version that produced this prediction",
        ),
        sa.Column(
            "raw_features",
            sa.JSON(),
            nullable=True,
            comment="Raw feature vector for debugging and retraining",
        ),
        # ── Audit Timestamps ───────────────────────────────────────────────
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="Yozuv yaratilgan vaqt",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            onupdate=sa.text("NOW()"),
            comment="Yozuv yangilangan vaqt",
        ),
        # ── Constraints ────────────────────────────────────────────────────
        sa.UniqueConstraint(
            "animal_id",
            "prediction_date",
            name="uq_health_prediction_animal_date",
        ),
        sa.CheckConstraint(
            "risk_score >= 0.0 AND risk_score <= 100.0",
            name="ck_prediction_risk_score_range",
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_prediction_confidence_range",
        ),
        sa.CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_prediction_risk_level_valid",
        ),
    )

    # ── Qo'shimcha indekslar ──────────────────────────────────────────────────
    op.create_index(
        "ix_hp_animal_date",
        "health_predictions",
        ["animal_id", "prediction_date"],
    )
    op.create_index(
        "ix_hp_risk_date",
        "health_predictions",
        ["risk_level", "prediction_date"],
    )
    op.create_index(
        "ix_hp_score_date",
        "health_predictions",
        ["risk_score", "prediction_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_hp_score_date",  table_name="health_predictions")
    op.drop_index("ix_hp_risk_date",   table_name="health_predictions")
    op.drop_index("ix_hp_animal_date", table_name="health_predictions")
    op.drop_table("health_predictions")