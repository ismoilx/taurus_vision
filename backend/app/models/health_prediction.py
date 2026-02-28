"""
Health Prediction Model — Sprint 13-14

Jonivor sog'liq xavfini oldindan bashorat qilish natijalarini saqlaydi.

ARXITEKTURA:
    PredictionService → HealthPrediction (DB) → API → Frontend

XAVF DARAJALARI:
    low      → ADI yaxshi, hech qanday xavf signali yo'q
    medium   → Ba'zi og'ishlar bor, monitoring tavsiya etiladi
    high     → Aniq pasayish trendi, veterinar kerak
    critical → 2-5 kun ichida inqiroz ehtimoli yuqori

MODEL VERSIYASI:
    model_version maydoni ensembleni kelajakda yangilashda
    qaysi modelda yaratilganini kuzatish imkonini beradi.
"""

import enum
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import (
    Float, DateTime, ForeignKey, Index,
    CheckConstraint, JSON, UniqueConstraint,
    String, Integer, SmallInteger,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class RiskLevel(str, enum.Enum):
    """
    Sog'liq xavfi darajasi.

    Foydalanuvchiga ko'rsatiladigan qiymat.
    Ichki hisoblash risk_score (0-100) bilan amalga oshiriladi.
    """
    LOW      = "low"       # risk_score  0 — 29
    MEDIUM   = "medium"    # risk_score 30 — 59
    HIGH     = "high"      # risk_score 60 — 79
    CRITICAL = "critical"  # risk_score 80 — 100


def risk_level_from_score(score: float) -> str:
    """Risk scoreni darajaga aylantiradi."""
    if score >= 80.0:
        return RiskLevel.CRITICAL
    if score >= 60.0:
        return RiskLevel.HIGH
    if score >= 30.0:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


class HealthPrediction(BaseModel):
    """
    Jonivor sog'liq bashorati — kunlik yozuv.

    Har kuni barcha aktiv jonivorlar uchun bashorat yaratiladi.
    Bir jonivor uchun bir kunda faqat bitta yozuv bo'ladi
    (UniqueConstraint orqali kafolatlangan).

    Columns:
        animal_id           FK → Animal
        prediction_date     Bashorat sanasi (YYYY-MM-DD)
        risk_level          low / medium / high / critical
        risk_score          Umumiy xavf bali 0.0 — 100.0
        confidence          Model ishonchlilik darajasi 0.0 — 1.0

        -- Ensemble komponentlari --
        rule_risk           Rule-based xavf (0 — 100)
        rf_risk             RandomForest xavf (0 — 100)
        isolation_score     IsolationForest anomaly score (0 — 100)

        -- Feature counts --
        adi_days_available  Necha kunlik ADI ma'lumoti ishlatildi
        features_used       Jami nechta feature ishlatildi

        -- Trendlar --
        predicted_adi_7day  7 kundan keyin kutilayotgan ADI
        trend_direction     improving / stable / declining

        -- Tushuntirish --
        risk_factors        Aniqlanigan xavf omillari (JSON list)
        recommendations     Tavsiyalar (JSON list)

        -- Meta --
        model_version       Qaysi model versiyasi ishlatildi
    """

    __tablename__ = "health_predictions"

    # ------------------------------------------------------------------ #
    # Foreign Key                                                          #
    # ------------------------------------------------------------------ #

    animal_id: Mapped[int] = mapped_column(
        ForeignKey("animals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the animal",
    )

    # ------------------------------------------------------------------ #
    # Date                                                                 #
    # ------------------------------------------------------------------ #

    prediction_date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Date of prediction, ISO format YYYY-MM-DD",
    )

    # ------------------------------------------------------------------ #
    # Core Result                                                          #
    # ------------------------------------------------------------------ #

    risk_level: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="low | medium | high | critical",
    )

    risk_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Final ensemble risk score (0.0 — 100.0). Higher = more risk.",
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        comment="Model confidence (0.0 — 1.0). Low when insufficient data.",
    )

    # ------------------------------------------------------------------ #
    # Ensemble Components                                                  #
    # ------------------------------------------------------------------ #

    rule_risk: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Rule-based component risk (0 — 100)",
    )

    rf_risk: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="RandomForest component risk (0 — 100)",
    )

    isolation_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="IsolationForest anomaly score converted to risk (0 — 100)",
    )

    # ------------------------------------------------------------------ #
    # Feature Meta                                                         #
    # ------------------------------------------------------------------ #

    adi_days_available: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        comment="Number of ADI records used in computation",
    )

    features_used: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        comment="Total feature count fed to the model",
    )

    # ------------------------------------------------------------------ #
    # Trend Prediction                                                     #
    # ------------------------------------------------------------------ #

    predicted_adi_7day: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Predicted ADI score 7 days ahead (linear extrapolation + RF)",
    )

    trend_direction: Mapped[Optional[str]] = mapped_column(
        String(12),
        nullable=True,
        comment="improving | stable | declining",
    )

    # ------------------------------------------------------------------ #
    # Explainability                                                        #
    # ------------------------------------------------------------------ #

    risk_factors: Mapped[Optional[list[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Human-readable list of detected risk factors",
    )

    recommendations: Mapped[Optional[list[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Actionable recommendations for the farmer",
    )

    # ------------------------------------------------------------------ #
    # Model Meta                                                           #
    # ------------------------------------------------------------------ #

    model_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="v1.0-ensemble",
        comment="Model version that produced this prediction",
    )

    raw_features: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Raw feature vector used for debugging and retraining",
    )

    # ------------------------------------------------------------------ #
    # Relationship                                                          #
    # ------------------------------------------------------------------ #

    animal: Mapped["Animal"] = relationship(  # type: ignore[name-defined]
        "Animal",
        back_populates="health_predictions",
        lazy="selectin",
    )

    # ------------------------------------------------------------------ #
    # Constraints & Indexes                                                #
    # ------------------------------------------------------------------ #

    __table_args__ = (
        UniqueConstraint(
            "animal_id",
            "prediction_date",
            name="uq_health_prediction_animal_date",
        ),
        CheckConstraint(
            "risk_score >= 0.0 AND risk_score <= 100.0",
            name="ck_prediction_risk_score_range",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_prediction_confidence_range",
        ),
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_prediction_risk_level_valid",
        ),
        Index("ix_hp_animal_date",   "animal_id", "prediction_date"),
        Index("ix_hp_risk_date",     "risk_level", "prediction_date"),
        Index("ix_hp_score_date",    "risk_score", "prediction_date"),
    )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"<HealthPrediction("
            f"animal_id={self.animal_id}, "
            f"date={self.prediction_date}, "
            f"risk={self.risk_level}, "
            f"score={self.risk_score:.1f}"
            f")>"
        )

    @property
    def needs_attention(self) -> bool:
        """True if farmer should take action today."""
        return self.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    @property
    def ensemble_breakdown(self) -> dict[str, float]:
        """Ensemble komponentlari dict shaklida."""
        return {
            "rule_based":    round(self.rule_risk, 1),
            "random_forest": round(self.rf_risk, 1),
            "isolation":     round(self.isolation_score, 1),
            "final":         round(self.risk_score, 1),
        }