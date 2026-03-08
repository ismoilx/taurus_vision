"""
Taurus Vision — In-App Notification Model

Foydalanuvchilarga tizim ichidagi bildirishnomalar.
Email emas — UI dagi qo'ng'iroq ikonasida ko'rinadigan xabarlar.

NOTIFICATION LIFECYCLE:
    UNREAD → READ → (arxivlangan)

TURLARI:
    INFO     — ma'lumotnoma (sensor o'qildi, hisobot yaratildi)
    SUCCESS  — muvaffaqiyat (jonivor qo'shildi, model deploy)
    WARNING  — ogohlantirish (ADI tushishi, sensor anomaliya)
    ALERT    — kritik holat (jonivor ko'rinmayapti, o'lim xavfi)
    SYSTEM   — tizim xabarlari (yangilanish, xato)

ENTITY LINK (ixtiyoriy):
    entity_type + entity_id → frontend da tegishli sahifaga o'tish uchun
    Masalan: entity_type="animal", entity_id=5 → /animals/5

INDEKSLAR:
    ix_notification_user_unread   — joriy foydalanuvchi o'qilmagan xabarlar
    ix_notification_user_created  — vaqt bo'yicha tartiblash
    ix_notification_broadcast     — barcha foydalanuvchilarga umumiy xabarlar
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, Boolean, Index, Integer,
    ForeignKey, Enum as SAEnum,
)
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class NotificationType(str, enum.Enum):
    """Notification turi — rang va ikonka uchun ishlatiladi."""
    INFO    = "info"     # Ko'k — oddiy ma'lumot
    SUCCESS = "success"  # Yashil — muvaffaqiyat
    WARNING = "warning"  # Sariq — ehtiyot bo'lish kerak
    ALERT   = "alert"    # Qizil — darhol e'tibor kerak
    SYSTEM  = "system"   # Kulrang — tizim xabari


class NotificationEntityType(str, enum.Enum):
    """Notification qaysi entity ga bog'liq."""
    ANIMAL   = "animal"
    CAMERA   = "camera"
    SENSOR   = "sensor"
    ALERT    = "alert"
    TASK     = "task"
    TRAINING = "training"
    REPORT   = "report"
    SYSTEM   = "system"
    USER     = "user"


class Notification(BaseModel):
    """
    In-app foydalanuvchi bildirishnomasi.

    NULL user_id = broadcast (barcha foydalanuvchilarga ko'rsatiladi).
    user_id bor = faqat o'sha foydalanuvchiga.

    Attributes:
        user_id:      Manzil foydalanuvchi (NULL = broadcast)
        n_type:       Notification turi (info/success/warning/alert/system)
        title:        Qisqa sarlavha (maks. 120 belgi)
        message:      To'liq xabar matni
        entity_type:  Qaysi entity haqida (animal, camera, ...)
        entity_id:    O'sha entity ning ID si
        action_url:   Frontend route (masalan: /animals/5)
        is_read:      O'qilib bo'linganligi
        read_at:      O'qilgan vaqt
        is_dismissed: Yashirib qo'yilganmi (arxiv)
        metadata:     Qo'shimcha ma'lumotlar (JSON)
    """

    __tablename__ = "notifications"

    # ── Kim uchun ─────────────────────────────────────────────────────────────
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="NULL = broadcast (barcha foydalanuvchilarga)",
    )

    # ── Kontent ───────────────────────────────────────────────────────────────
    n_type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notification_type_enum"),
        nullable=False,
        default=NotificationType.INFO,
        comment="Notification turi",
    )

    title: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        comment="Qisqa sarlavha",
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="To'liq xabar matni",
    )

    # ── Entity bog'liq ────────────────────────────────────────────────────────
    entity_type: Mapped[Optional[NotificationEntityType]] = mapped_column(
        SAEnum(NotificationEntityType, name="notification_entity_type_enum"),
        nullable=True,
        comment="Qaysi entity turi haqida",
    )

    entity_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Entity ID (animal_id, camera_id, ...)",
    )

    action_url: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Frontend route (masalan: /animals/5)",
    )

    # ── Holat ─────────────────────────────────────────────────────────────────
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="O'qilib bo'lindimi",
    )

    read_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="O'qilgan vaqt",
    )

    is_dismissed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Arxivlangan (yashirilgan)",
    )

    # ── Qo'shimcha ma'lumot ───────────────────────────────────────────────────
    extra_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Qo'shimcha kontekst ma'lumotlari (JSON)",
    )

    # ── Relationship ──────────────────────────────────────────────────────────
    user: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User",
        back_populates="notifications",
        lazy="noload",
    )

    # ── Indekslar ─────────────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_notification_user_unread",  "user_id",  "is_read",
              ),
        Index("ix_notification_user_created", "user_id",  "created_at"),
        Index("ix_notification_type_created", "n_type",   "created_at"),
        Index("ix_notification_broadcast",    "is_read",  "created_at",
              ),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification(id={self.id}, user_id={self.user_id}, "
            f"type={self.n_type.value}, read={self.is_read})>"
        )