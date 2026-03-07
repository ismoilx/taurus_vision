"""
Taurus Vision — Sut Ishlab Chiqarish Modeli

Har bir sog'ish sessiyasi yoki kunlik sut yozuvini saqlaydi.

JADVAL: milk_productions

MUNOSABATLAR:
    Animal → MilkProduction (1:N)

SUT SIFATI PARAMETRLARI:
    fat_percent       — Yog' foizi (%)
    protein_percent   — Oqsil foizi (%)
    somatic_cell_count — Somatik hujayralar soni (ming/ml) — sut sifati ko'rsatkichi
    lactose_percent   — Laktoza foizi (%)

LAKTATSIYA SIKLI:
    lactation_number  — Nechi-nechimchi laktatsiya (1, 2, 3...)
    days_in_milk      — Laktatsiya boshlanganidan necha kun o'tdi (DIM)
"""

from __future__ import annotations

import enum
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    String, Enum as SQLEnum, Integer, Float,
    ForeignKey, Date, Text, CheckConstraint, Index, Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class MilkSession(str, enum.Enum):
    """Sog'ish sessiyasi vaqti."""
    MORNING   = "morning"    # Ertalab
    MIDDAY    = "midday"     # Tushda
    EVENING   = "evening"    # Kechqurun
    DAILY     = "daily"      # Kunlik (yig'ma)


class MilkQualityGrade(str, enum.Enum):
    """Sut sifat darajasi."""
    PREMIUM  = "premium"   # Yuqori sifat
    STANDARD = "standard"  # Standart
    LOW      = "low"       # Past sifat (somatic cells yuqori)
    REJECTED = "rejected"  # Rad etilgan


class MilkProduction(BaseModel):
    """
    Sut ishlab chiqarish yozuvi.

    Har bir sog'ish sessiyasida yoki kunlik sut hajmi va sifatini saqlaydi.

    Attributes:
        animal_id        — Qaysi jonivordan
        record_date      — Sog'ish sanasi
        session          — Sessiya (ertalab / kechqurun / kunlik)
        milk_kg          — Sog'ilgan sut miqdori (kg)
        fat_percent      — Yog' foizi
        protein_percent  — Oqsil foizi
        somatic_cell_count — SCC (sifat ko'rsatkichi)
        lactose_percent  — Laktoza foizi
        lactation_number — Nechimchi laktatsiya
        days_in_milk     — Laktatsiya boshidan necha kun
        quality_grade    — Sifat darajasi
        temperature_c    — Sut harorati (sog'ish vaqtida)
        notes            — Qo'shimcha izoh
        milked_by        — Kim sog'di (xodim ismi)
    """

    __tablename__ = "milk_productions"

    # ─── Foreign Key ─────────────────────────────────────────────────
    animal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("animals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Jonivor ID si",
    )

    # ─── Sana va sessiya ─────────────────────────────────────────────
    record_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Sog'ish sanasi",
    )

    session: Mapped[MilkSession] = mapped_column(
        SQLEnum(MilkSession, name="milk_session"),
        nullable=False,
        default=MilkSession.DAILY,
        comment="Sog'ish sessiyasi",
    )

    # ─── Miqdor ──────────────────────────────────────────────────────
    milk_kg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Sog'ilgan sut miqdori (kg)",
    )

    # ─── Sifat parametrlari ───────────────────────────────────────────
    fat_percent: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Yog' foizi (%)",
    )

    protein_percent: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Oqsil foizi (%)",
    )

    somatic_cell_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Somatik hujayralar soni (ming/ml) — < 200 yaxshi",
    )

    lactose_percent: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Laktoza foizi (%)",
    )

    # ─── Laktatsiya ma'lumotlari ──────────────────────────────────────
    lactation_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Nechimchi laktatsiya (1, 2, 3...)",
    )

    days_in_milk: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Laktatsiya boshlanganidan necha kun o'tdi (DIM)",
    )

    # ─── Sifat darajasi ───────────────────────────────────────────────
    quality_grade: Mapped[Optional[MilkQualityGrade]] = mapped_column(
        SQLEnum(MilkQualityGrade, name="milk_quality_grade"),
        nullable=True,
        comment="Sifat darajasi",
    )

    # ─── Qo'shimcha ──────────────────────────────────────────────────
    temperature_c: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Sut harorati sog'ish vaqtida (°C)",
    )

    milked_by: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Kim sog'di",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Qo'shimcha izoh",
    )

    # ─── Relationship ─────────────────────────────────────────────────
    animal: Mapped["Animal"] = relationship(  # type: ignore[name-defined]
        "Animal",
        back_populates="milk_productions",
        lazy="noload",
    )

    # ─── Constraints ─────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint("milk_kg >= 0", name="check_milk_kg_positive"),
        CheckConstraint(
            "fat_percent IS NULL OR (fat_percent >= 0 AND fat_percent <= 15)",
            name="check_fat_range",
        ),
        CheckConstraint(
            "protein_percent IS NULL OR (protein_percent >= 0 AND protein_percent <= 10)",
            name="check_protein_range",
        ),
        CheckConstraint(
            "lactation_number IS NULL OR lactation_number >= 1",
            name="check_lactation_number",
        ),
        CheckConstraint(
            "days_in_milk IS NULL OR days_in_milk >= 0",
            name="check_dim_positive",
        ),
        Index("ix_milk_animal_date", "animal_id", "record_date"),
        Index("ix_milk_date", "record_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<MilkProduction("
            f"id={self.id}, "
            f"animal_id={self.animal_id}, "
            f"date={self.record_date}, "
            f"milk_kg={self.milk_kg}"
            f")>"
        )

    @property
    def quality_grade_auto(self) -> MilkQualityGrade:
        """Somatik hujayralar soniga qarab avtomatik sifat darajasi."""
        if self.somatic_cell_count is None:
            return MilkQualityGrade.STANDARD
        if self.somatic_cell_count < 200:
            return MilkQualityGrade.PREMIUM
        if self.somatic_cell_count < 400:
            return MilkQualityGrade.STANDARD
        if self.somatic_cell_count < 800:
            return MilkQualityGrade.LOW
        return MilkQualityGrade.REJECTED