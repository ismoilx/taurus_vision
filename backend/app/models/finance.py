"""
Taurus Vision — Finance Module Models

Ferma moliyaviy operatsiyalarini kuzatish uchun yagona model.

ARXITEKTURA:
    FinanceTransaction — barcha kirim va chiqimlar uchun yagona jadval.
    type=INCOME  → daromad (sotish, sut, go'sht, subsidiya)
    type=EXPENSE → xarajat (yem, dori, uskuna, ish haqi)

IQTISODIY MANTIQ:
    Foyda  = INCOME.sum  - EXPENSE.sum  (davr bo'yicha)
    ROI %  = (Foyda / EXPENSE.sum) × 100
    Jonivor ROI = (jonivor daromadi - jonivor xarajati) / jonivor xarajati × 100

VALYUTA:
    Asosiy saqlash: UZS (so'm).
    amount_usd ixtiyoriy — kurs taxminan, hisobot uchun.

KATEGORIYALAR:
    EXPENSE:
        FEED       — yem va ozuqa
        VETERINARY — dori, veterinar xizmati, emlash
        EQUIPMENT  — asbob-uskuna, ta'mirlash
        LABOR      — ish haqi, qo'shimcha ish
        UTILITIES  — suv, elektr, gaz, issiqlik
        TRANSPORT  — tashish, yetkazib berish
        OTHER      — boshqa xarajatlar

    INCOME:
        ANIMAL_SALE — tirik jonivor sotish
        MILK_SALE   — sut sotish
        MEAT_SALE   — go'sht sotish
        WOOL_SALE   — jun sotish (qo'y)
        SUBSIDY     — davlat subsidiyasi
        OTHER       — boshqa daromadlar

INDEKSLAR:
    ix_finance_type_date         — daromad/xarajat vaqt bo'yicha
    ix_finance_category_date     — kategoriya + vaqt (chart uchun)
    ix_finance_animal_date       — jonivor ROI hisobi uchun
    ix_finance_created_by        — foydalanuvchi tarixi
"""

import enum
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    String, Text, Float, Integer, ForeignKey,
    Index, DateTime, Date, Enum as SAEnum,
)
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


# =============================================================================
# ENUMS
# =============================================================================

class TransactionType(str, enum.Enum):
    """Operatsiya turi."""
    INCOME  = "income"   # Daromad
    EXPENSE = "expense"  # Xarajat


class ExpenseCategory(str, enum.Enum):
    """Xarajat kategoriyasi."""
    FEED        = "feed"        # Yem va ozuqa
    VETERINARY  = "veterinary"  # Dori, veterinar
    EQUIPMENT   = "equipment"   # Asbob-uskuna
    LABOR       = "labor"       # Ish haqi
    UTILITIES   = "utilities"   # Kommunal
    TRANSPORT   = "transport"   # Tashish
    OTHER       = "other"       # Boshqa


class IncomeCategory(str, enum.Enum):
    """Daromad kategoriyasi."""
    ANIMAL_SALE = "animal_sale"  # Jonivor sotish
    MILK_SALE   = "milk_sale"    # Sut
    MEAT_SALE   = "meat_sale"    # Go'sht
    WOOL_SALE   = "wool_sale"    # Jun
    SUBSIDY     = "subsidy"      # Subsidiya
    OTHER       = "other"        # Boshqa


class PaymentMethod(str, enum.Enum):
    """To'lov usuli."""
    CASH     = "cash"      # Naqd
    TRANSFER = "transfer"  # Bank o'tkazmasi
    CREDIT   = "credit"    # Kredit


# =============================================================================
# FINANCE TRANSACTION
# =============================================================================

class FinanceTransaction(BaseModel):
    """
    Bitta moliyaviy operatsiya (kirim yoki chiqim).

    Barcha daromad va xarajatlar ushbu yagona jadvalda saqlanadi.
    type va category maydonlari birga mantiqiy to'liqlikni ta'minlaydi:
        type=INCOME  → category IncomeCategory qiymati bo'lishi kerak
        type=EXPENSE → category ExpenseCategory qiymati bo'lishi kerak

    Example:
        # Yem xarajati
        tx = FinanceTransaction(
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.FEED.value,
            amount_uzs=2_500_000,
            description="Iyun uchun pichan — 500 kg",
            transaction_date=date.today(),
            created_by=user.id,
        )

        # Buzoq sotish
        tx = FinanceTransaction(
            type=TransactionType.INCOME,
            category=IncomeCategory.ANIMAL_SALE.value,
            amount_uzs=8_500_000,
            amount_usd=650.0,
            description="JNV-042 — 6 oylik buzoq",
            animal_id=42,
            transaction_date=date.today(),
            created_by=user.id,
        )
    """

    __tablename__ = "finance_transactions"

    # ------------------------------------------------------------------
    # Asosiy maydonlar
    # ------------------------------------------------------------------

    type: Mapped[TransactionType] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="income | expense",
    )

    # category string sifatida saqlanadi — ExpenseCategory yoki IncomeCategory
    category: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="Kategoriya (feed | veterinary | animal_sale | ...)",
    )

    amount_uzs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Miqdor (UZS, so'm)",
    )

    amount_usd: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="USD ekvivalenti (ixtiyoriy, hisob uchun)",
    )

    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Qisqa tavsif",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Qo'shimcha izoh",
    )

    # ------------------------------------------------------------------
    # Sana
    # ------------------------------------------------------------------

    transaction_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Operatsiya sanasi (foydalanuvchi tomonidan kiritilgan)",
    )

    # ------------------------------------------------------------------
    # To'lov
    # ------------------------------------------------------------------

    payment_method: Mapped[PaymentMethod] = mapped_column(
        String(15),
        nullable=False,
        default=PaymentMethod.CASH,
        comment="To'lov usuli",
    )

    receipt_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Chek/hujjat raqami",
    )

    # ------------------------------------------------------------------
    # Bog'liqlar (ixtiyoriy)
    # ------------------------------------------------------------------

    animal_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("animals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Bog'liq jonivor (None = ferma umumiy)",
    )

    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Kim qo'shdi",
    )

    # ------------------------------------------------------------------
    # Qo'shimcha ma'lumot
    # ------------------------------------------------------------------

    meta: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Qo'shimcha: supplier, invoice_id, task_id va h.k.",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    animal: Mapped[Optional["Animal"]] = relationship(   # type: ignore[name-defined]
        "Animal",
        foreign_keys=[animal_id],
        lazy="noload",
    )

    creator: Mapped[Optional["User"]] = relationship(    # type: ignore[name-defined]
        "User",
        foreign_keys=[created_by],
        lazy="noload",
    )

    # ------------------------------------------------------------------
    # Indekslar
    # ------------------------------------------------------------------

    __table_args__ = (
        Index("ix_finance_type_date",     "type",     "transaction_date"),
        Index("ix_finance_category_date", "category", "transaction_date"),
        Index("ix_finance_animal_date",   "animal_id","transaction_date"),
        Index("ix_finance_created_by",    "created_by"),
    )

    def __repr__(self) -> str:
        sign = "+" if self.type == TransactionType.INCOME else "-"
        return (
            f"<FinanceTransaction(id={self.id}, "
            f"{sign}{self.amount_uzs:,} UZS, "
            f"cat={self.category}, "
            f"date={self.transaction_date})>"
        )

    @property
    def is_income(self) -> bool:
        return self.type == TransactionType.INCOME

    @property
    def is_expense(self) -> bool:
        return self.type == TransactionType.EXPENSE

    @property
    def signed_amount(self) -> int:
        """Belgili miqdor: daromad musbat, xarajat manfiy."""
        return self.amount_uzs if self.is_income else -self.amount_uzs