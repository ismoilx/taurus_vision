"""
Taurus Vision — Go'sht Ishlab Chiqarish Modeli

So'yish sessiyasi va go'sht ishlab chiqarish yozuvlarini saqlaydi.

JADVAL: slaughter_records

MUNOSABATLAR:
    Animal → SlaughterRecord (1:N)

GO'SHT PARAMETRLARI:
    live_weight_kg       — So'yishdan oldingi tirik vazn (kg)
    carcass_weight_kg    — Karkas (toza) vazni (kg)
    dressing_percent     — So'yish foizi (carcass/live * 100)
    meat_kg              — Sof go'sht miqdori (kg)
    bone_kg              — Suyak miqdori (kg)
    fat_kg               — Yog' miqdori (kg)
    offal_kg             — Ichki organlar (ko'krak, jigar va h.k.)
    hide_kg              — Teri vazni (kg)

SIFAT PARAMETRLARI:
    quality_grade        — Go'sht sifat darajasi
    ph_value             — Go'sht pH qiymati (5.4–6.0 normal)
    color_score          — Rang bahosi (1–5)
    marbling_score       — Marmar tuzilishi (1–5)
"""

from __future__ import annotations

import enum
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    String, Enum as SQLEnum, Integer, Float,
    ForeignKey, Date, Text, CheckConstraint, Index, Boolean, Numeric,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SlaughterPurpose(str, enum.Enum):
    """So'yish maqsadi."""
    SALE        = "sale"        # Sotish uchun
    OWN_USE     = "own_use"     # O'z iste'mol uchun
    EXPORT      = "export"      # Eksport uchun
    PROCESSING  = "processing"  # Qayta ishlash uchun


class MeatQualityGrade(str, enum.Enum):
    """Go'sht sifat darajasi."""
    PREMIUM   = "premium"   # Yuqori darajali (A+)
    CHOICE    = "choice"    # Tanlangan (A)
    SELECT    = "select"    # Tanlab olingan (B)
    STANDARD  = "standard"  # Standart (C)
    LOW       = "low"       # Past sifat


class SlaughterRecord(BaseModel):
    """
    So'yish yozuvi.

    Har bir jonivorning so'yish va go'sht ishlab chiqarish ma'lumotlari.

    Attributes:
        animal_id           — Qaysi jonivor so'yildi
        slaughter_date      — So'yish sanasi
        purpose             — So'yish maqsadi
        live_weight_kg      — Tirik vazn (so'yishdan oldin)
        carcass_weight_kg   — Karkas vazni
        dressing_percent    — So'yish foizi (%)
        meat_kg             — Sof go'sht
        bone_kg             — Suyaklar
        fat_kg              — Yog'
        offal_kg            — Ichki organlar
        hide_kg             — Teri
        quality_grade       — Sifat darajasi
        ph_value            — pH qiymati
        color_score         — Rang bahosi (1–5)
        marbling_score      — Marmar bahosi (1–5)
        temperature_c       — Saqlash harorati (°C)
        price_per_kg        — 1 kg narxi (so'm)
        total_revenue       — Jami tushum (so'm)
        slaughtered_by      — Kim so'ydi (xodim ismi)
        veterinary_check    — Veterinariya tekshiruvi o'tganmi
        notes               — Qo'shimcha izoh
    """

    __tablename__ = "slaughter_records"

    # ─── Foreign Key ─────────────────────────────────────────────────
    animal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("animals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Jonivor ID si",
    )

    # ─── Sana va maqsad ──────────────────────────────────────────────
    slaughter_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="So'yish sanasi",
    )

    purpose: Mapped[SlaughterPurpose] = mapped_column(
        SQLEnum(SlaughterPurpose, name="slaughter_purpose"),
        nullable=False,
        default=SlaughterPurpose.SALE,
        comment="So'yish maqsadi",
    )

    # ─── Vazn ma'lumotlari ────────────────────────────────────────────
    live_weight_kg: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Tirik vazn (kg) — so'yishdan oldin",
    )

    carcass_weight_kg: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Karkas vazni (kg) — toza go'sht + suyak",
    )

    dressing_percent: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="So'yish foizi (%) — carcass/live*100",
    )

    meat_kg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Sof go'sht miqdori (kg)",
    )

    bone_kg: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Suyak miqdori (kg)",
    )

    fat_kg: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Yog' miqdori (kg)",
    )

    offal_kg: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Ichki organlar (jigar, buyrak, yurak va h.k.) kg",
    )

    hide_kg: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Teri vazni (kg)",
    )

    # ─── Sifat parametrlari ───────────────────────────────────────────
    quality_grade: Mapped[Optional[MeatQualityGrade]] = mapped_column(
        SQLEnum(MeatQualityGrade, name="meat_quality_grade"),
        nullable=True,
        comment="Go'sht sifat darajasi",
    )

    ph_value: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Go'sht pH qiymati (5.4–6.0 normal)",
    )

    color_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Rang bahosi 1–5 (5 eng yaxshi)",
    )

    marbling_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Marmar tuzilishi 1–5 (5 eng yaxshi)",
    )

    temperature_c: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Saqlash harorati (°C)",
    )

    # ─── Moliyaviy ma'lumotlar ────────────────────────────────────────
    price_per_kg: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="1 kg go'sht narxi (so'm)",
    )

    total_revenue: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Jami tushum (so'm)",
    )

    # ─── Qo'shimcha ma'lumotlar ───────────────────────────────────────
    veterinary_check: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Veterinariya tekshiruvi o'tganmi",
    )

    slaughtered_by: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Kim so'ydi (xodim ismi/ID si)",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Qo'shimcha izoh",
    )

    # ─── Relationship ─────────────────────────────────────────────────
    animal: Mapped["Animal"] = relationship(  # type: ignore[name-defined]
        "Animal",
        back_populates="slaughter_records",
        lazy="noload",
    )

    # ─── Constraints ─────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint("meat_kg >= 0", name="check_meat_kg_positive"),
        CheckConstraint(
            "live_weight_kg IS NULL OR live_weight_kg > 0",
            name="check_live_weight_positive",
        ),
        CheckConstraint(
            "carcass_weight_kg IS NULL OR carcass_weight_kg > 0",
            name="check_carcass_weight_positive",
        ),
        CheckConstraint(
            "dressing_percent IS NULL OR (dressing_percent > 0 AND dressing_percent <= 100)",
            name="check_dressing_percent_range",
        ),
        CheckConstraint(
            "ph_value IS NULL OR (ph_value >= 0 AND ph_value <= 14)",
            name="check_ph_range",
        ),
        CheckConstraint(
            "color_score IS NULL OR (color_score >= 1 AND color_score <= 5)",
            name="check_color_score_range",
        ),
        CheckConstraint(
            "marbling_score IS NULL OR (marbling_score >= 1 AND marbling_score <= 5)",
            name="check_marbling_score_range",
        ),
        Index("ix_slaughter_animal_date", "animal_id", "slaughter_date"),
        Index("ix_slaughter_date", "slaughter_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<SlaughterRecord("
            f"id={self.id}, "
            f"animal_id={self.animal_id}, "
            f"date={self.slaughter_date}, "
            f"meat_kg={self.meat_kg}"
            f")>"
        )

    @property
    def dressing_percent_calculated(self) -> Optional[float]:
        """Karkas va tirik vazndan avtomatik so'yish foizini hisoblash."""
        if self.carcass_weight_kg and self.live_weight_kg and self.live_weight_kg > 0:
            return round((self.carcass_weight_kg / self.live_weight_kg) * 100, 2)
        return None

    @property
    def total_byproducts_kg(self) -> float:
        """Jami qo'shimcha mahsulotlar (suyak + yog' + ichki + teri)."""
        return round(
            (self.bone_kg or 0) +
            (self.fat_kg or 0) +
            (self.offal_kg or 0) +
            (self.hide_kg or 0),
            2
        )

    @property
    def revenue_calculated(self) -> Optional[float]:
        """Narx va go'sht miqdoridan avtomatik tushum hisoblash."""
        if self.price_per_kg and self.meat_kg:
            return round(self.price_per_kg * self.meat_kg, 2)
        return None