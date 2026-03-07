"""
Taurus Vision — Dori-Darmon Ombori Modeli

JADVALLAR:
    medicine_inventory  — Dori-darmonlar ombori (nomi, qoldig'i, muddati)
    medicine_usages     — Har bir jonivorga berilgan dori yozuvi

ARXITEKTURA:
    MedicineInventory ← MedicineUsage → Animal → HealthRecord (optional)

OGOHLANTIRISH TIZIMLARI:
    - Kam qoldi: quantity <= min_stock_quantity
    - Muddat yaqinlashdi: expiry_date <= bugun + 30 kun
    - Muddat o'tdi: expiry_date < bugun
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


# =============================================================================
# ENUMS
# =============================================================================

class MedicineType(str, enum.Enum):
    """Dori turi."""
    VACCINE       = "vaccine"        # Vaksina / Emlash
    ANTIBIOTIC    = "antibiotic"     # Antibiotik
    ANTIPARASITIC = "antiparasitic"  # Parazitga qarshi
    VITAMIN       = "vitamin"        # Vitamin / Mineral
    HORMONE       = "hormone"        # Gormonal preparat
    ANALGESIC     = "analgesic"      # Og'riq qoldiruvchi
    ANTIFUNGAL    = "antifungal"     # Zamburug'ga qarshi
    DISINFECTANT  = "disinfectant"   # Dezinfektsiya
    SUPPLEMENT    = "supplement"     # Oziq-ovqat qo'shimchasi
    OTHER         = "other"          # Boshqa


class MedicineUnit(str, enum.Enum):
    """O'lchov birligi."""
    ML     = "ml"      # Millilitr
    L      = "l"       # Litr
    MG     = "mg"      # Milligram
    G      = "g"       # Gram
    TABLET = "tablet"  # Tabletkа
    DOSE   = "dose"    # Doza
    VIAL   = "vial"    # Flakon
    PACK   = "pack"    # Paket / Quti


class MedicineAdminRoute(str, enum.Enum):
    """Berish yo'li."""
    INJECTION_IM = "injection_im"  # Mushak ichiga in'yeksiya
    INJECTION_IV = "injection_iv"  # Vena ichiga in'yeksiya
    INJECTION_SC = "injection_sc"  # Teri ostiga in'yeksiya
    ORAL         = "oral"          # Og'iz orqali
    TOPICAL      = "topical"       # Tashqi (teri)
    INTRANASAL   = "intranasal"    # Burun orqali
    OTHER        = "other"         # Boshqa


# =============================================================================
# MODELS
# =============================================================================

class MedicineInventory(BaseModel):
    """
    Dori-darmon ombori.

    Fermada mavjud barcha dori-darmonlar ro'yxati, qoldig'i va muddati.

    Attributes:
        name             — Dori nomi
        generic_name     — Umumiy nomi (aktiv modda)
        medicine_type    — Turi (vaksina, antibiotik...)
        manufacturer     — Ishlab chiqaruvchi
        batch_number     — Partiya raqami
        quantity         — Joriy miqdor
        unit             — O'lchov birligi
        min_stock_quantity — Minimal qoldiq (bu miqdordan pastga tushsa ogohlantirish)
        purchase_price   — Xarid narxi (1 birlik)
        expiry_date      — Yaroqlilik muddati
        storage_temp_min/max — Saqlash harorati
        notes            — Izoh
        is_active        — Faol (arxivlanmagan)
        species_applicable — Qaysi turlar uchun (JSON string: "cattle,sheep")
    """

    __tablename__ = "medicine_inventory"

    # ─── Asosiy ma'lumotlar ───────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        index=True,
        comment="Dori nomi (masalan: Biomycin, Ivermectin)",
    )

    generic_name: Mapped[Optional[str]] = mapped_column(
        String(300),
        nullable=True,
        comment="Umumiy nomi / aktiv modda",
    )

    medicine_type: Mapped[MedicineType] = mapped_column(
        SQLEnum(MedicineType, name="medicine_type"),
        nullable=False,
        index=True,
        comment="Dori turi",
    )

    manufacturer: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Ishlab chiqaruvchi kompaniya",
    )

    batch_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Partiya / lot raqami",
    )

    # ─── Miqdor ──────────────────────────────────────────────────────
    quantity: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Joriy qoldiq miqdor",
    )

    unit: Mapped[MedicineUnit] = mapped_column(
        SQLEnum(MedicineUnit, name="medicine_unit"),
        nullable=False,
        default=MedicineUnit.ML,
        comment="O'lchov birligi",
    )

    min_stock_quantity: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=10.0,
        comment="Minimal qoldiq — kam qoldi ogohlantirishiga chegara",
    )

    # ─── Moliyaviy ───────────────────────────────────────────────────
    purchase_price: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Xarid narxi (1 birlik uchun, so'm)",
    )

    # ─── Muddat va saqlash ────────────────────────────────────────────
    expiry_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="Yaroqlilik muddati",
    )

    storage_temp_min: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Saqlash harorati minimum (°C)",
    )

    storage_temp_max: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Saqlash harorati maksimum (°C)",
    )

    # ─── Qo'shimcha ──────────────────────────────────────────────────
    dosage_instructions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Berish ko'rsatmasi",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Qo'shimcha izoh",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Faol (False — arxivlangan)",
    )

    # Qaysi turlar uchun (vergul bilan ajratilgan: "cattle,sheep,goat")
    species_applicable: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Qo'llanma turlar (cattle,sheep,goat,horse,other)",
    )

    # ─── Relationships ────────────────────────────────────────────────
    usages: Mapped[list["MedicineUsage"]] = relationship(
        "MedicineUsage",
        back_populates="medicine",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # ─── Constraints ─────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="check_medicine_qty_positive"),
        CheckConstraint("min_stock_quantity >= 0", name="check_min_stock_positive"),
        Index("ix_medicine_type_active", "medicine_type", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<MedicineInventory("
            f"id={self.id}, "
            f"name='{self.name}', "
            f"qty={self.quantity}{self.unit.value}"
            f")>"
        )

    @property
    def is_low_stock(self) -> bool:
        """Qoldiq minimal darajadan past."""
        return self.quantity <= self.min_stock_quantity

    @property
    def is_expired(self) -> bool:
        """Muddati o'tgan."""
        if not self.expiry_date:
            return False
        return self.expiry_date < date.today()

    @property
    def days_until_expiry(self) -> Optional[int]:
        """Muddat tugashiga necha kun qoldi."""
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days


class MedicineUsage(BaseModel):
    """
    Jonivorga berilgan dori yozuvi.

    Har safar dori berilganda shu yerda qayd etiladi.
    HealthRecord ga ixtiyoriy bog'lanadi.

    Attributes:
        medicine_id      — Qaysi doridan
        animal_id        — Qaysi jonivorga
        health_record_id — Qaysi davolash yozuviga (optional)
        given_date       — Qachon berildi
        quantity_given   — Qancha berildi
        admin_route      — Berish yo'li
        given_by         — Kim berdi
        next_dose_date   — Keyingi doza sanasi
        withdrawal_date  — Sut / go'sht uchun qarzdorlik muddati tugash sanasi
        notes            — Izoh
    """

    __tablename__ = "medicine_usages"

    # ─── Foreign Keys ─────────────────────────────────────────────────
    medicine_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("medicine_inventory.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Dori ID si",
    )

    animal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("animals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Jonivor ID si",
    )

    health_record_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("health_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Bog'liq davolash yozuvi (ixtiyoriy)",
    )

    # ─── Ma'lumotlar ──────────────────────────────────────────────────
    given_date: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Berilgan vaqt",
    )

    quantity_given: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Berilgan miqdor",
    )

    admin_route: Mapped[Optional[MedicineAdminRoute]] = mapped_column(
        SQLEnum(MedicineAdminRoute, name="medicine_admin_route"),
        nullable=True,
        comment="Berish yo'li",
    )

    given_by: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Kim berdi (veterinar / xodim)",
    )

    next_dose_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Keyingi doza sanasi",
    )

    withdrawal_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Sut/go'sht karantin tugash sanasi",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Qo'shimcha izoh",
    )

    # ─── Relationships ─────────────────────────────────────────────────
    medicine: Mapped["MedicineInventory"] = relationship(
        "MedicineInventory",
        back_populates="usages",
        lazy="joined",
    )

    animal: Mapped["Animal"] = relationship(  # type: ignore[name-defined]
        "Animal",
        back_populates="medicine_usages",
        lazy="noload",
    )

    # ─── Constraints ──────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint("quantity_given > 0", name="check_usage_qty_positive"),
        Index("ix_medicine_usage_animal_date", "animal_id", "given_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<MedicineUsage("
            f"id={self.id}, "
            f"animal_id={self.animal_id}, "
            f"medicine_id={self.medicine_id}, "
            f"qty={self.quantity_given}"
            f")>"
        )

    @property
    def is_in_withdrawal(self) -> bool:
        """Sut/go'sht karantin davrida."""
        if not self.withdrawal_date:
            return False
        return self.withdrawal_date >= date.today()