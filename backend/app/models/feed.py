"""
Taurus Vision — Feed Management Models (Sprint 20)

Ferma ozuqa boshqaruvi uchun ikkita model:
    FeedStock  — omborlagi ozuqa inventari
    FeedRecord — har bir oziqlantiruv hodisasi

ARXITEKTURA:
    FeedStock  (ombor)
        ↑ kamaytiradi
    FeedRecord (oziqlantiruv)
        ↓ bog'liq
    Animal (ixtiyoriy — None = butun podani)

FEED TURLARI (qoramol fermasi uchun standart):
    HAY           — pichan
    WHEAT_STRAW   — bug'doy somi
    CORN_SILAGE   — makkajo'xori silosi
    GRAIN_MIX     — don aralashmasi
    CONCENTRATE   — konsentrat yem
    MINERAL_BLOCK — mineral blok
    WATER         — suv
    OTHER         — boshqa

LOW STOCK ALERT:
    current_kg < min_threshold_kg → AlertType.CUSTOM (MEDIUM severity)
    Celery task har kecha 08:00 da tekshiradi.
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Float, Integer, ForeignKey, Index, DateTime, Boolean
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


# =============================================================================
# ENUMS
# =============================================================================

class FeedType(str, enum.Enum):
    """Ozuqa turi."""
    HAY           = "hay"
    WHEAT_STRAW   = "wheat_straw"
    CORN_SILAGE   = "corn_silage"
    GRAIN_MIX     = "grain_mix"
    CONCENTRATE   = "concentrate"
    MINERAL_BLOCK = "mineral_block"
    WATER         = "water"
    OTHER         = "other"


class FeedUnit(str, enum.Enum):
    """O'lchov birligi."""
    KG    = "kg"
    TON   = "ton"
    LITER = "liter"


# =============================================================================
# FEED STOCK — ombor
# =============================================================================

class FeedStock(BaseModel):
    """
    Omborlagi bitta ozuqa turi.

    Har bir ozuqa turi uchun bitta yozuv saqlanadi.
    FeedRecord yaratilganda current_kg avtomatik kamayadi.

    Example:
        stock = FeedStock(
            feed_type=FeedType.HAY,
            name="Yozgi pichan (1-kesim)",
            current_kg=5000.0,
            min_threshold_kg=500.0,
            unit_cost_uzs=800,
        )
    """

    __tablename__ = "feed_stocks"

    # ------------------------------------------------------------------ #
    # Asosiy ma'lumot                                                      #
    # ------------------------------------------------------------------ #

    feed_type: Mapped[FeedType] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="Ozuqa turi",
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Ozuqa nomi (masalan: Yozgi pichan, Konsentrat No.3)",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Qo'shimcha tavsif",
    )

    unit: Mapped[FeedUnit] = mapped_column(
        String(10),
        nullable=False,
        default=FeedUnit.KG,
        comment="O'lchov birligi",
    )

    # ------------------------------------------------------------------ #
    # Miqdor                                                               #
    # ------------------------------------------------------------------ #

    current_kg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Hozirgi miqdor (kg ekvivalentda)",
    )

    min_threshold_kg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=100.0,
        comment="Minimal chegara — bu dan past bo'lsa alert",
    )

    # ------------------------------------------------------------------ #
    # Iqtisodiy                                                            #
    # ------------------------------------------------------------------ #

    unit_cost_uzs: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="1 kg narxi (UZS)",
    )

    supplier: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Yetkazib beruvchi nomi",
    )

    # ------------------------------------------------------------------ #
    # Muddat                                                               #
    # ------------------------------------------------------------------ #

    purchase_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Sotib olingan sana",
    )

    expiry_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Yaroqlilik muddati (None = cheksiz)",
    )

    # ------------------------------------------------------------------ #
    # Boshqaruv                                                            #
    # ------------------------------------------------------------------ #

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Faolmi? False = arxivlangan",
    )

    low_stock_alerted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Low stock alert yuborilganmi (deduplication uchun)",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Qo'shimcha izohlar",
    )

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #

    records: Mapped[list["FeedRecord"]] = relationship(
        "FeedRecord",
        back_populates="stock",
        lazy="noload",
    )

    # ------------------------------------------------------------------ #
    # Indekslar                                                            #
    # ------------------------------------------------------------------ #

    __table_args__ = (
        Index("ix_feed_stocks_type_active", "feed_type", "is_active"),
    )

    def __init__(self, **kwargs):
        # Accept test-friendly aliases
        if "min_stock_kg" in kwargs and "min_threshold_kg" not in kwargs:
            kwargs["min_threshold_kg"] = kwargs.pop("min_stock_kg")
        elif "min_stock_kg" in kwargs:
            kwargs.pop("min_stock_kg")
        if "quantity_kg" in kwargs and "current_kg" not in kwargs:
            kwargs["current_kg"] = kwargs.pop("quantity_kg")
        elif "quantity_kg" in kwargs:
            kwargs.pop("quantity_kg")
        if "price_per_kg" in kwargs and "unit_cost_uzs" not in kwargs:
            kwargs["unit_cost_uzs"] = int(kwargs.pop("price_per_kg"))
        elif "price_per_kg" in kwargs:
            kwargs.pop("price_per_kg")
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<FeedStock(id={self.id}, "
            f"type={self.feed_type}, "
            f"current_kg={self.current_kg:.1f}, "
            f"threshold={self.min_threshold_kg:.1f})>"
        )

    @property
    def is_low(self) -> bool:
        """Miqdor minimal chegaradan pastmi?"""
        return self.current_kg < self.min_threshold_kg

    @property
    def min_stock_kg(self) -> float:
        """Backward-compatibility alias for `min_threshold_kg`."""
        return self.min_threshold_kg

    @min_stock_kg.setter
    def min_stock_kg(self, value: float) -> None:
        self.min_threshold_kg = value

    @property
    def quantity_kg(self) -> float:
        """Backward-compatibility alias for `current_kg`."""
        return self.current_kg

    @quantity_kg.setter
    def quantity_kg(self, value: float) -> None:
        self.current_kg = value

    @property
    def stock_percent(self) -> float:
        """Minimal chegaraga nisbatan foiz (100+ = yetarli, 0 = qurib bitdi)."""
        if self.min_threshold_kg <= 0:
            return 100.0
        return round(self.current_kg / self.min_threshold_kg * 100, 1)

    @property
    def total_value_uzs(self) -> Optional[int]:
        """Ombordagi ozuqaning umumiy qiymati (UZS)."""
        if self.unit_cost_uzs is None:
            return None
        return int(self.current_kg * self.unit_cost_uzs)

    @property
    def is_expired(self) -> bool:
        """Muddati o'tganmi?"""
        if self.expiry_date is None:
            return False
        from datetime import timezone
        return datetime.now(timezone.utc) > self.expiry_date


# =============================================================================
# FEED RECORD — oziqlantiruv hodisasi
# =============================================================================

class FeedRecord(BaseModel):
    """
    Bitta oziqlantiruv hodisasi.

    Yaratilganda FeedService avtomatik FeedStock.current_kg ni kamaytiradi.
    animal_id=None → butun poda uchun umumiy yozuv.

    Example:
        record = FeedRecord(
            stock_id=1,
            quantity_kg=150.0,
            fed_at=datetime.now(timezone.utc),
            fed_by=3,
            animal_id=None,    # butun poda
            notes="Ertalabki oziqlantiruv",
        )
    """

    __tablename__ = "feed_records"

    # ------------------------------------------------------------------ #
    # Foreign Keys                                                         #
    # ------------------------------------------------------------------ #

    stock_id: Mapped[int] = mapped_column(
        ForeignKey("feed_stocks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Qaysi ombor zaxirasidan",
    )

    animal_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("animals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Qaysi jonivorga (None = butun poda)",
    )

    fed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Kim oziqlantirishni amalga oshirdi",
    )

    # ------------------------------------------------------------------ #
    # Oziqlantiruv ma'lumoti                                               #
    # ------------------------------------------------------------------ #

    quantity_kg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Berilgan miqdor (kg)",
    )

    fed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Oziqlantiruv vaqti",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Izoh: ishtaha, maxsus holat va h.k.",
    )

    meta: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Qo'shimcha: task_id, batch_id va h.k.",
    )

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #

    stock: Mapped["FeedStock"] = relationship(
        "FeedStock",
        back_populates="records",
        lazy="noload",
    )

    animal: Mapped[Optional["Animal"]] = relationship(  # type: ignore[name-defined]
        "Animal",
        foreign_keys=[animal_id],
        lazy="noload",
    )

    feeder: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User",
        foreign_keys=[fed_by],
        lazy="noload",
    )

    # ------------------------------------------------------------------ #
    # Indekslar                                                            #
    # ------------------------------------------------------------------ #

    __table_args__ = (
        Index("ix_feed_records_stock_date", "stock_id", "fed_at"),
        Index("ix_feed_records_animal_date", "animal_id", "fed_at"),
        Index("ix_feed_records_fed_by",      "fed_by"),
    )

    def __repr__(self) -> str:
        return (
            f"<FeedRecord(id={self.id}, "
            f"stock_id={self.stock_id}, "
            f"qty={self.quantity_kg:.1f}kg, "
            f"animal={self.animal_id or 'herd'})>"
        )