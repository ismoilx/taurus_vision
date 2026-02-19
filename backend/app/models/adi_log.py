"""
Animal Development Index (ADI) Log Model.

Har bir jonivor uchun kunlik ADI hisoblash natijalarini saqlaydi.
Bu jadval time-series ma'lumot bo'lib, trend tahlili va
historik monitoring uchun ishlatiladi.

Design decisions:
    - Immutable records: bir kunda bir yozuv, o'zgartirib bo'lmaydi
    - Komponentlar alohida saqlanadi: debug va kalibratsiya uchun
    - raw_data JSON: kelajakda yangi komponentlar qo'shish uchun
    - Partial scores support: ba'zi ma'lumotlar mavjud bo'lmaganda
      tizim ishdan chiqmasin (sensor yo'q bo'lsa ham ishlaydi)
"""

from datetime import datetime
from typing import Optional, Any
from sqlalchemy import (
    Float,
    DateTime,
    ForeignKey,
    Index,
    CheckConstraint,
    JSON,
    UniqueConstraint,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ADICategory(str):
    """
    ADI kategoriya konstantalari.

    Thresholdlar agronomiya va chorvachilik
    ilmiy adabiyotiga asoslangan.
    """
    HEALTHY  = "healthy"    # 75 — 100
    AVERAGE  = "average"    # 50 — 74
    WARNING  = "warning"    # 25 — 49
    CRITICAL = "critical"   #  0 — 24

    @classmethod
    def from_score(cls, score: float) -> str:
        """
        Score asosida kategoriya aniqlash.

        Args:
            score: ADI score (0.0 — 100.0)

        Returns:
            Kategoriya string qiymati
        """
        if score >= 75.0:
            return cls.HEALTHY
        elif score >= 50.0:
            return cls.AVERAGE
        elif score >= 25.0:
            return cls.WARNING
        else:
            return cls.CRITICAL


class ADILog(BaseModel):
    """
    Kunlik ADI hisoblash natijasi.

    Har bir jonivor uchun kuniga bir marta yaratiladi.
    UniqueConstraint (animal_id, date) orqali ta'minlanadi.

    Columns:
        animal_id:              FK → Animal
        calculated_at:          Hisoblash vaqti (UTC)
        calculation_date:       Qaysi kun uchun hisoblangan (YYYY-MM-DD)
        adi_score:              Yakuniy ADI ball (0.0 — 100.0)
        category:               healthy / average / warning / critical

        -- Komponentlar (har biri 0.0 — 100.0) --
        activity_score:         Faollik (kamera deteksiyalari)
        feeding_score:          Ovqatlanish (ozuqa idishiga tashrif)
        drinking_score:         Suv ichish (suv hovuziga tashrif)
        movement_score:         Harakat sifati (bbox dinamikasi)
        growth_score:           O'sish dinamikasi (bbox o'lchami trendi)
        social_score:           Ijtimoiy indeks (birgalikda ko'rinish)
        sensor_score:           Sensor ma'lumotlari (harorat, yurak urishi)
        veterinary_score:       Veterinar holati

        -- Meta --
        data_quality:           Ma'lumot sifati 0.0—1.0
                                (kamroq ma'lumot = past sifat)
        raw_data:               Hisoblash tafsilotlari (JSON)
        notes:                  Avtomatik yoki qo'lda izoh
    """

    __tablename__ = "adi_logs"

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
    # Timing                                                               #
    # ------------------------------------------------------------------ #

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="UTC timestamp when ADI was computed",
    )

    calculation_date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Date this ADI covers, ISO format YYYY-MM-DD",
    )

    # ------------------------------------------------------------------ #
    # ADI Result                                                           #
    # ------------------------------------------------------------------ #

    adi_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Final weighted ADI score (0.0 — 100.0)",
    )

    category: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="healthy | average | warning | critical",
    )

    # ------------------------------------------------------------------ #
    # Component Scores (each 0.0 — 100.0, nullable = data not available) #
    # ------------------------------------------------------------------ #

    activity_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Activity level from camera detections (weight: 0.20)",
    )

    feeding_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Feeding behavior — visits to food area (weight: 0.20)",
    )

    drinking_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Drinking behavior — visits to water area (weight: 0.10)",
    )

    movement_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Movement quality — bbox velocity and pattern (weight: 0.15)",
    )

    growth_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Growth dynamics — bbox size trend over 30 days (weight: 0.20)",
    )

    social_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Social index — co-detections with other animals (weight: 0.10)",
    )

    sensor_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="IoT sensor data — temp, heart rate (weight: 0.05)",
    )

    veterinary_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Veterinary status — checkups, vaccinations (weight: 0.05) — manual input",
    )

    # ------------------------------------------------------------------ #
    # Data Quality                                                         #
    # ------------------------------------------------------------------ #

    data_quality: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment=(
            "Fraction of components with real data (0.0—1.0). "
            "Low quality = fewer cameras / missing sensors."
        ),
    )

    # ------------------------------------------------------------------ #
    # Raw Data & Notes                                                     #
    # ------------------------------------------------------------------ #

    raw_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment=(
            "Full calculation detail for debugging and retraining. "
            "Contains per-component breakdowns, detection counts, "
            "bbox series, sensor readings, etc."
        ),
    )

    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Auto-generated or manual observation note",
    )

    # ------------------------------------------------------------------ #
    # Relationship                                                          #
    # ------------------------------------------------------------------ #

    animal: Mapped["Animal"] = relationship(  # type: ignore[name-defined]
        "Animal",
        back_populates="adi_logs",
        lazy="selectin",
    )

    # ------------------------------------------------------------------ #
    # Constraints & Indexes                                                #
    # ------------------------------------------------------------------ #

    __table_args__ = (
        # Bir jonivor uchun bir kunda faqat bitta ADI yozuvi
        UniqueConstraint(
            "animal_id",
            "calculation_date",
            name="uq_adi_log_animal_date",
        ),
        CheckConstraint(
            "adi_score >= 0.0 AND adi_score <= 100.0",
            name="ck_adi_score_range",
        ),
        CheckConstraint(
            "data_quality >= 0.0 AND data_quality <= 1.0",
            name="ck_adi_data_quality_range",
        ),
        CheckConstraint(
            "category IN ('healthy', 'average', 'warning', 'critical')",
            name="ck_adi_category_valid",
        ),
        # Time-series queries uchun
        Index("ix_adi_logs_animal_date", "animal_id", "calculation_date"),
        # Farm-wide queries: barcha warning/critical jonivorlar
        Index("ix_adi_logs_category_date", "category", "calculation_date"),
        # Trend tahlili
        Index("ix_adi_logs_score_date", "adi_score", "calculation_date"),
    )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"<ADILog("
            f"animal_id={self.animal_id}, "
            f"date={self.calculation_date}, "
            f"score={self.adi_score:.1f}, "
            f"category={self.category}"
            f")>"
        )

    @property
    def is_concerning(self) -> bool:
        """True if animal needs attention (warning or critical)."""
        return self.category in (ADICategory.WARNING, ADICategory.CRITICAL)

    @property
    def component_scores(self) -> dict[str, Optional[float]]:
        """
        Barcha komponent scorelarni dict shaklida qaytaradi.

        Returns:
            Komponent nomi → score (None = ma'lumot yo'q)
        """
        return {
            "activity":    self.activity_score,
            "feeding":     self.feeding_score,
            "drinking":    self.drinking_score,
            "movement":    self.movement_score,
            "growth":      self.growth_score,
            "social":      self.social_score,
            "sensor":      self.sensor_score,
            "veterinary":  self.veterinary_score,
        }

    @property
    def available_components(self) -> list[str]:
        """Ma'lumoti mavjud komponentlar ro'yxati."""
        return [k for k, v in self.component_scores.items() if v is not None]
