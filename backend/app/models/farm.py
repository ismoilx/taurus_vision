"""
Taurus Vision — Farm Database Model

Har bir ferma mustaqil sub'ekt:
  - O'zining joylashuvi, nomi, tavsifi bor
  - Foydalanuvchilar bir yoki ko'p fermaga tegishli bo'lishi mumkin
  - Jonivorlar, kameralar va boshqa resurslar fermaga bog'langan
"""

from typing import Optional
from sqlalchemy import String, Text, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Farm(BaseModel):
    """
    Ferma entity modeli.

    Har bir ferma mustaqil kuzatuv birligidir.
    Bir foydalanuvchi bir nechta fermani boshqarishi,
    bir fermada bir nechta foydalanuvchi ishlashi mumkin.
    """

    __tablename__ = "farms"

    # ------------------------------------------------------------------ #
    # Asosiy ma'lumotlar                                                   #
    # ------------------------------------------------------------------ #

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
        comment="Ferma nomi (masalan: Toshkent Ferma #1)",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Ferma haqida qo'shimcha ma'lumot",
    )

    location: Mapped[Optional[str]] = mapped_column(
        String(300),
        nullable=True,
        comment="Manzil: shahar, tuman, ko'cha",
    )

    # ------------------------------------------------------------------ #
    # Kontakt va mas'ul shaxs                                              #
    # ------------------------------------------------------------------ #

    owner_name: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
        comment="Ferma egasining ismi",
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        comment="Bog'lanish telefon raqami",
    )

    # ------------------------------------------------------------------ #
    # Sozlamalar                                                            #
    # ------------------------------------------------------------------ #

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="False = ferma arxivlangan (o'chirilmaydi)",
    )

    # Ferma uchun ADI hisoblashda ishlatadigan timezone offset (soatda)
    # 0 = UTC, 5 = Toshkent (UTC+5)
    timezone_offset: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
        comment="UTC dan farq soatda (Toshkent = 5)",
    )

    # ------------------------------------------------------------------ #
    # Relationships                                                         #
    # ------------------------------------------------------------------ #

    animals: Mapped[list["Animal"]] = relationship(  # type: ignore[name-defined]
        "Animal",
        back_populates="farm",
        lazy="noload",
    )

    # ------------------------------------------------------------------ #
    # Helpers                                                               #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return f"<Farm(id={self.id}, name='{self.name}', active={self.is_active})>"