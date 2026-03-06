"""
Taurus Vision — Breeding & Genealogy Models (Sprint 25-26)

JADVALLAR:
    breeding_records  — Juftlashish va homiladorlik yozuvlari
    offspring_records — Tug'ilgan nasllar (breeding_records ga bog'liq)

ARXITEKTURA:
    Animal → (mother_id/father_id) → BreedingRecord → OffspringRecord → Animal
    Bu circular FK emas: animal → breeding (ona/ota) → offspring → animal (yangi)
    SQLAlchemy relationship lari viewonly=True bilan muammosiz ishlaydi.

GESTATSIYA MUDDATLARI (kun):
    Qoramol (cattle):  283
    Qo'y (sheep):      150
    Echki (goat):      150
    Ot (horse):        340
    Boshqa (other):    280
"""

from __future__ import annotations

import enum
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    String, Enum as SQLEnum, Integer, Float,
    ForeignKey, Date, Text, CheckConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


# =============================================================================
# ENUMS
# =============================================================================

class MatingMethod(str, enum.Enum):
    """Juftlashish usuli."""
    NATURAL               = "natural"               # Tabiiy
    ARTIFICIAL_INSEMINATION = "artificial_insemination"  # Sun'iy urug'lantirish
    EMBRYO_TRANSFER       = "embryo_transfer"        # Embrion ko'chirish


class BreedingStatus(str, enum.Enum):
    """Nasl yozuvining joriy holati."""
    PLANNED             = "planned"              # Rejalashtirilgan
    CONFIRMED_PREGNANT  = "confirmed_pregnant"   # Homiladorlik tasdiqlangan
    BIRTHED             = "birthed"              # Tug'ildi
    FAILED              = "failed"               # Muvaffaqiyatsiz (homiladorlik bo'lmadi)
    ABORTED             = "aborted"              # Abort (o'z-o'zidan yoki majburiy)


class PregnancyCheckMethod(str, enum.Enum):
    """Homiladorlikni tekshirish usuli."""
    ULTRASOUND   = "ultrasound"    # Ultratovush
    BLOOD_TEST   = "blood_test"    # Qon tahlili
    VISUAL       = "visual"        # Vizual kuzatuv
    RECTAL_EXAM  = "rectal_exam"   # Rektal tekshiruv (qoramol uchun)


class OffspringOutcome(str, enum.Enum):
    """Tug'ilgan nasllning holati."""
    ALIVE          = "alive"           # Tirik
    STILLBORN      = "stillborn"       # O'lik tug'ilgan
    DIED_SHORTLY   = "died_shortly"    # Tug'ilgandan ko'p o'tmay o'ldi


# =============================================================================
# GESTATION PERIODS (kunlarda)
# =============================================================================

GESTATION_DAYS: dict[str, int] = {
    "cattle": 283,
    "sheep":  150,
    "goat":   150,
    "horse":  340,
    "other":  280,
}


# =============================================================================
# BREEDING RECORD MODEL
# =============================================================================

class BreedingRecord(BaseModel):
    """
    Juftlashish va homiladorlik yozuvi.

    Har bir yozuv bitta ona jonivor + bitta ota (ichki yoki tashqi) ni
    bog'laydi va homiladorlikning butun jarayonini kuzatadi.

    ICHKI OTA (farm_id bor):
        father_id = Animal.id (farm ichidagi erkak jonivor)
        external_sire_tag = NULL

    TASHQI OTA (boshqa fermadan):
        father_id = NULL
        external_sire_tag = "EXT-001"
        external_sire_breed = "Aberdeen Angus"
    """

    __tablename__ = "breeding_records"

    # ------------------------------------------------------------------ #
    # Farm & Core Links                                                    #
    # ------------------------------------------------------------------ #

    farm_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("farms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Qaysi fermaga tegishli",
    )

    mother_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("animals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Ona jonivor (female)",
    )

    father_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("animals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Ota jonivor (farm ichidagi erkak, nullable)",
    )

    # ------------------------------------------------------------------ #
    # External Sire (Tashqi ota)                                          #
    # ------------------------------------------------------------------ #

    external_sire_tag: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Tashqi ota tag ID si (boshqa fermadan)",
    )

    external_sire_breed: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Tashqi ota zoti",
    )

    external_sire_farm: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Tashqi ota ferma nomi",
    )

    # ------------------------------------------------------------------ #
    # Mating Event                                                         #
    # ------------------------------------------------------------------ #

    mating_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Juftlashish sanasi",
    )

    mating_method: Mapped[MatingMethod] = mapped_column(
        SQLEnum(MatingMethod, name="mating_method"),
        default=MatingMethod.NATURAL,
        nullable=False,
        comment="Juftlashish usuli",
    )

    # ------------------------------------------------------------------ #
    # Pregnancy Tracking                                                   #
    # ------------------------------------------------------------------ #

    status: Mapped[BreedingStatus] = mapped_column(
        SQLEnum(BreedingStatus, name="breeding_status"),
        default=BreedingStatus.PLANNED,
        nullable=False,
        index=True,
    )

    gestation_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=283,
        comment="Gestatsiya muddati (kun) — species bo'yicha avtomatik",
    )

    expected_birth_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Kutilgan tug'ilish sanasi (mating_date + gestation_days)",
    )

    pregnancy_confirmed_at: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Homiladorlik tasdiqlangan sana",
    )

    pregnancy_check_method: Mapped[Optional[PregnancyCheckMethod]] = mapped_column(
        SQLEnum(PregnancyCheckMethod, name="pregnancy_check_method"),
        nullable=True,
        comment="Homiladorlikni tekshirish usuli",
    )

    pregnancy_check_notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Tekshiruv natijalari / ultratovush xulosasi",
    )

    # ------------------------------------------------------------------ #
    # Birth Event                                                          #
    # ------------------------------------------------------------------ #

    actual_birth_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Haqiqiy tug'ilish sanasi",
    )

    live_offspring_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Tirik tug'ilgan nasllar soni",
    )

    stillborn_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="O'lik tug'ilgan nasllar soni",
    )

    birth_complications: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Tug'ilish paytidagi asoratlar",
    )

    # ------------------------------------------------------------------ #
    # Abort / Failure                                                      #
    # ------------------------------------------------------------------ #

    abort_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Abort sanasi",
    )

    abort_reason: Mapped[Optional[str]] = mapped_column(
        String(300),
        nullable=True,
        comment="Abort sababi",
    )

    # ------------------------------------------------------------------ #
    # Meta                                                                 #
    # ------------------------------------------------------------------ #

    veterinarian: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Nazorat qilgan veterinar ismi",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Kim yaratdi",
    )

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #

    mother: Mapped["Animal"] = relationship(  # type: ignore[name-defined]
        "Animal",
        foreign_keys=[mother_id],
        lazy="noload",
    )

    father: Mapped[Optional["Animal"]] = relationship(  # type: ignore[name-defined]
        "Animal",
        foreign_keys=[father_id],
        lazy="noload",
    )

    offspring: Mapped[list["OffspringRecord"]] = relationship(
        "OffspringRecord",
        back_populates="breeding_record",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="OffspringRecord.birth_order",
    )

    farm: Mapped[Optional["Farm"]] = relationship(  # type: ignore[name-defined]
        "Farm",
        foreign_keys=[farm_id],
        lazy="noload",
    )

    # ------------------------------------------------------------------ #
    # Table Constraints                                                    #
    # ------------------------------------------------------------------ #

    __table_args__ = (
        CheckConstraint(
            "(father_id IS NOT NULL) OR (external_sire_tag IS NOT NULL)",
            name="ck_breeding_sire_required",
        ),
        CheckConstraint(
            "live_offspring_count >= 0",
            name="ck_breeding_live_non_negative",
        ),
        CheckConstraint(
            "stillborn_count >= 0",
            name="ck_breeding_stillborn_non_negative",
        ),
        CheckConstraint(
            "gestation_days BETWEEN 100 AND 400",
            name="ck_breeding_gestation_range",
        ),
        Index("ix_breeding_mother_date",  "mother_id",  "mating_date"),
        Index("ix_breeding_status_date",  "status",     "expected_birth_date"),
        Index("ix_breeding_farm_status",  "farm_id",    "status"),
    )

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def pregnancy_progress_pct(self) -> Optional[float]:
        """Homiladorlik davomida o'tgan foiz (0-100)."""
        if self.status not in (BreedingStatus.CONFIRMED_PREGNANT, BreedingStatus.PLANNED):
            return None
        days_passed = (date.today() - self.mating_date).days
        return min(round(days_passed / self.gestation_days * 100, 1), 100.0)

    @property
    def days_until_birth(self) -> Optional[int]:
        """Tug'ilishgacha qolgan kunlar."""
        if not self.expected_birth_date:
            return None
        if self.status == BreedingStatus.BIRTHED:
            return 0
        return (self.expected_birth_date - date.today()).days

    @property
    def is_overdue(self) -> bool:
        """Kutilgan sanadan o'tib ketdimi."""
        if not self.expected_birth_date:
            return False
        return (
            date.today() > self.expected_birth_date
            and self.status == BreedingStatus.CONFIRMED_PREGNANT
        )

    @property
    def total_offspring(self) -> int:
        return self.live_offspring_count + self.stillborn_count

    @property
    def sire_label(self) -> str:
        """Ota uchun ko'rsatiladigan matn."""
        if self.father_id:
            return f"Ichki ota (ID: {self.father_id})"
        tag = self.external_sire_tag or "Noma'lum"
        breed = self.external_sire_breed or ""
        return f"Tashqi: {tag}" + (f" ({breed})" if breed else "")

    def __repr__(self) -> str:
        return (
            f"<BreedingRecord("
            f"id={self.id}, "
            f"mother_id={self.mother_id}, "
            f"status={self.status.value}, "
            f"mating_date={self.mating_date}"
            f")>"
        )


# =============================================================================
# OFFSPRING RECORD MODEL
# =============================================================================

class OffspringRecord(BaseModel):
    """
    Tug'ilgan nasl yozuvi.

    Har bir tug'ilgan jonivor uchun alohida yozuv.
    Ikki egizak = ikki OffspringRecord.

    ANIMALS GA BOG'LANISH:
        animal_id = NULL   → jonivor hali ro'yxatdan o'tmagan
        animal_id = X      → animals jadvalida tegishli yozuv bor
    """

    __tablename__ = "offspring_records"

    # ------------------------------------------------------------------ #
    # Core Links                                                           #
    # ------------------------------------------------------------------ #

    breeding_record_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("breeding_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    animal_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("animals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Ro'yxatdan o'tgandan keyin link qilinadi",
    )

    # ------------------------------------------------------------------ #
    # Birth Details                                                        #
    # ------------------------------------------------------------------ #

    birth_order: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Tug'ilish tartibi (1=birinchi, 2=ikkinchi/egizak...)",
    )

    gender: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="male / female / unknown",
    )

    birth_weight_kg: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Tug'ilgandagi vazn (kg)",
    )

    outcome: Mapped[OffspringOutcome] = mapped_column(
        SQLEnum(OffspringOutcome, name="offspring_outcome"),
        default=OffspringOutcome.ALIVE,
        nullable=False,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #

    breeding_record: Mapped["BreedingRecord"] = relationship(
        "BreedingRecord",
        back_populates="offspring",
        lazy="noload",
    )

    animal: Mapped[Optional["Animal"]] = relationship(  # type: ignore[name-defined]
        "Animal",
        foreign_keys=[animal_id],
        lazy="noload",
    )

    # ------------------------------------------------------------------ #
    # Constraints                                                          #
    # ------------------------------------------------------------------ #

    __table_args__ = (
        CheckConstraint("birth_order >= 1", name="ck_offspring_order_positive"),
        CheckConstraint(
            "birth_weight_kg IS NULL OR birth_weight_kg > 0",
            name="ck_offspring_weight_positive",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<OffspringRecord("
            f"id={self.id}, "
            f"breeding_id={self.breeding_record_id}, "
            f"order={self.birth_order}, "
            f"outcome={self.outcome.value}"
            f")>"
        )