"""
Taurus Vision — Integration Models (Q5)

Tashqi tizimlar bilan integratsiya uchun ikkita model:

  APIKey   — Tashqi tizimlar (IoT, ERP, Telegram bot) JWT siz kirishi uchun.
  Webhook  — Voqealar yuz berganda tashqi URL ga HTTP POST yuborish.

API KEY ARXITEKTURASI:
  Kalitlar 2 qismdan iborat:
    PREFIX  — DB da saqlangan, kalitni tezda topish uchun (indekslangan)
    SECRET  — SHA-256 hash da saqlangan, asl qiymati faqat yaratishda ko'rsatiladi
  Format: tv_live_<prefix8>_<secret32>
  Misol:  tv_live_ab12cd34_xYzAbC...

  Autentifikatsiya oqimi:
    1. Tashqi tizim X-API-Key: tv_live_ab12cd34_xYzAbC... headerini yuboradi
    2. prefix (ab12cd34) bo'yicha DB dan APIKey topiladi
    3. SHA-256(secret) == key_hash tekshiriladi
    4. Scope va muddati tekshiriladi
    5. last_used_at yangilanadi

SCOPE TIZIMI (eng kichik huquq printsipi):
  read:animals    — Jonivorlar ma'lumotini o'qish
  read:sensors    — Sensor ma'lumotlarini o'qish
  read:alerts     — Ogohlantirishlarni o'qish
  read:detections — Deteksiya tarixini o'qish
  read:finance    — Moliyaviy ma'lumotlarni o'qish
  write:sensors   — Sensor ma'lumot yuborish (IoT qurilmalar)
  write:detections— Tashqi kamera deteksiya natijasini yuborish
  admin           — Barcha huquqlar (faqat ADMIN yaratishi mumkin)

WEBHOOK ARXITEKTURASI:
  Voqea yuz berganda Celery task HTTPS POST so'rovi yuboradi.
  Imzolash: HMAC-SHA256(secret, f"{timestamp}.{body}")
  Headerlar:
    X-Taurus-Event:     "alert.created"
    X-Taurus-Signature: "sha256=<hex>"
    X-Taurus-Delivery:  "<uuid4>"
    X-Taurus-Timestamp: "<unix_ts>"

  Qayta urinish strategiyasi (Celery):
    1-urinish: darhol
    2-urinish: 60 soniya
    3-urinish: 5 daqiqa
    4-urinish: 30 daqiqa
    5-urinish → muvaffaqiyatsiz: failure_count += 1
    failure_count >= 5 → is_active = False (avtomatik o'chiriladi)

WEBHOOK VOQEALARI:
  alert.created       — Har qanday yangi alert
  alert.critical      — Faqat CRITICAL/HIGH severity alertlar
  detection.animal    — Jonivor aniqlandi (YOLO)
  weight.anomaly      — Vazn >5% tushdi
  sensor.anomaly      — Sensor normal diapazondan chiqdi
  adi.critical        — ADI < 30 (kritik faollik)
  animal.not_seen     — Jonivor >24 soat ko'rinmadi
"""

import enum
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, Integer, Boolean,
    ForeignKey, Index, DateTime,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


# =============================================================================
# ENUMS
# =============================================================================

class APIKeyScope(str, enum.Enum):
    """API kalit huquq darajasi."""
    READ_ANIMALS    = "read:animals"
    READ_SENSORS    = "read:sensors"
    READ_ALERTS     = "read:alerts"
    READ_DETECTIONS = "read:detections"
    READ_FINANCE    = "read:finance"
    WRITE_SENSORS   = "write:sensors"
    WRITE_DETECTIONS= "write:detections"
    ADMIN           = "admin"


class WebhookEvent(str, enum.Enum):
    """Webhook voqea turlari."""
    ALERT_CREATED    = "alert.created"
    ALERT_CRITICAL   = "alert.critical"
    DETECTION_ANIMAL = "detection.animal"
    WEIGHT_ANOMALY   = "weight.anomaly"
    SENSOR_ANOMALY   = "sensor.anomaly"
    ADI_CRITICAL     = "adi.critical"
    ANIMAL_NOT_SEEN  = "animal.not_seen"


# =============================================================================
# API KEY
# =============================================================================

class APIKey(BaseModel):
    """
    Tashqi tizim autentifikatsiya kaliti.

    Yaratishda to'liq kalit FAQAT BIR MARTA ko'rsatiladi.
    DB da faqat prefix va SHA-256 hash saqlanadi.

    Example:
        key   = APIKey.generate_raw()    # "tv_live_ab12cd34_xYz..."
        model = APIKey(
            name       = "Telegram Bot",
            key_prefix = APIKey.extract_prefix(key),
            key_hash   = APIKey.hash_key(key),
            scopes     = ["read:alerts", "read:animals"],
            created_by = admin_user.id,
        )
    """

    __tablename__ = "api_keys"

    # ------------------------------------------------------------------
    # Identifikatsiya
    # ------------------------------------------------------------------

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Kalit nomi (masalan: Telegram Bot, 1C Integration)",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Kalit maqsadi haqida qo'shimcha ma'lumot",
    )

    # ------------------------------------------------------------------
    # Kriptografik qismlar
    # ------------------------------------------------------------------

    key_prefix: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        unique=True,
        index=True,
        comment="Kalitning birinchi 8 belgisi — tezda qidirish uchun",
    )

    key_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash — asl kalit HECH QACHON saqlanmaydi",
    )

    # ------------------------------------------------------------------
    # Huquqlar
    # ------------------------------------------------------------------

    scopes: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Ruxsat etilgan scope lar ro'yxati",
    )

    # ------------------------------------------------------------------
    # Holat
    # ------------------------------------------------------------------

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Faolmi? False = bloklangan",
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Muddati (None = cheksiz)",
    )

    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Oxirgi foydalanish vaqti",
    )

    request_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Jami so'rovlar soni (statistika uchun)",
    )

    # ------------------------------------------------------------------
    # Bog'liqlar
    # ------------------------------------------------------------------

    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Kim yaratdi",
    )

    creator: Mapped[Optional["User"]] = relationship(   # type: ignore[name-defined]
        "User",
        foreign_keys=[created_by],
        lazy="noload",
    )

    # ------------------------------------------------------------------
    # Indekslar
    # ------------------------------------------------------------------

    __table_args__ = (
        Index("ix_api_keys_prefix_active", "key_prefix", "is_active"),
        Index("ix_api_keys_created_by",    "created_by"),
    )

    def __repr__(self) -> str:
        return (
            f"<APIKey(id={self.id}, "
            f"name='{self.name}', "
            f"prefix={self.key_prefix}, "
            f"active={self.is_active})>"
        )

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_raw() -> str:
        """
        Yangi kalit generatsiyasi.

        Returns:
            "tv_live_<8hex>_<32hex>" formatidagi kalit string.
            Bu qiymat FAQAT BIR MARTA foydalanuvchiga ko'rsatiladi.
        """
        prefix = secrets.token_hex(4)     # 8 belgi
        secret = secrets.token_hex(16)    # 32 belgi
        return f"tv_live_{prefix}_{secret}"

    @staticmethod
    def extract_prefix(raw_key: str) -> str:
        """
        Kalit stringidan prefix ajratib olish.

        Args:
            raw_key: "tv_live_ab12cd34_xyz..." formatdagi kalit

        Returns:
            "ab12cd34" — 8 belgili prefix

        Raises:
            ValueError: noto'g'ri format
        """
        parts = raw_key.split("_")
        if len(parts) != 4 or parts[0] != "tv" or parts[1] != "live":
            raise ValueError(f"Noto'g'ri kalit format: {raw_key[:12]}...")
        return parts[2]

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """
        Kalit SHA-256 hash ini hisoblash.

        Args:
            raw_key: to'liq kalit string

        Returns:
            64 belgilik hex digest
        """
        import hashlib
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @staticmethod
    def parse_raw(raw_key: str) -> tuple[str, str]:
        """
        Kalit stringini prefix va hashga ajratish.

        Returns:
            (prefix, hash) tuple
        """
        prefix = APIKey.extract_prefix(raw_key)
        hashed = APIKey.hash_key(raw_key)
        return prefix, hashed

    def has_scope(self, scope: str) -> bool:
        """Kalit berilgan scopega ega ekanligini tekshirish."""
        return "admin" in self.scopes or scope in self.scopes

    @property
    def display_key(self) -> str:
        """Xavfsiz ko'rsatish uchun qisqartirilgan kalit."""
        return f"tv_live_{self.key_prefix}_{'*' * 16}"


# =============================================================================
# WEBHOOK
# =============================================================================

class Webhook(BaseModel):
    """
    Tashqi URL ga voqea xabarlari yuborish konfiguratsiyasi.

    Voqea yuz berganda Celery task HTTPS POST so'rovi yuboradi.
    HMAC-SHA256 imzo tashqi tizimga xabar haqiqiyligini tekshirish imkonini beradi.

    Example:
        wh = Webhook(
            name       = "Telegram Alert",
            url        = "https://api.telegram.org/bot<token>/sendMessage",
            secret     = secrets.token_hex(32),
            events     = ["alert.critical", "adi.critical"],
            created_by = admin_user.id,
        )
    """

    __tablename__ = "webhooks"

    # ------------------------------------------------------------------
    # Identifikatsiya
    # ------------------------------------------------------------------

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Webhook nomi (masalan: Telegram Alert Bot)",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Maqsad va qo'shimcha ma'lumot",
    )

    # ------------------------------------------------------------------
    # Endpoint
    # ------------------------------------------------------------------

    url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="POST so'rov yuborilishi kerak bo'lgan HTTPS URL",
    )

    secret: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="HMAC-SHA256 imzolash uchun maxfiy kalit (text da saqlanadi)",
    )

    # ------------------------------------------------------------------
    # Voqealar
    # ------------------------------------------------------------------

    events: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Kuzatiladigan voqealar ro'yxati (WebhookEvent enumdan)",
    )

    # ------------------------------------------------------------------
    # Holat
    # ------------------------------------------------------------------

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Faolmi? failure_count >= 5 bo'lsa avtomatik o'chiriladi",
    )

    failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Ketma-ket muvaffaqiyatsiz urinishlar soni",
    )

    success_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Jami muvaffaqiyatli yuborishlar soni",
    )

    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Oxirgi ishga tushirish vaqti",
    )

    last_status_code: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Oxirgi HTTP javob kodi (200, 404, 500...)",
    )

    last_error: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Oxirgi xato xabari",
    )

    # ------------------------------------------------------------------
    # Bog'liqlar
    # ------------------------------------------------------------------

    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Kim yaratdi",
    )

    creator: Mapped[Optional["User"]] = relationship(   # type: ignore[name-defined]
        "User",
        foreign_keys=[created_by],
        lazy="noload",
    )

    # ------------------------------------------------------------------
    # Indekslar
    # ------------------------------------------------------------------

    __table_args__ = (
        Index("ix_webhooks_active",     "is_active"),
        Index("ix_webhooks_created_by", "created_by"),
    )

    def __repr__(self) -> str:
        return (
            f"<Webhook(id={self.id}, "
            f"name='{self.name}', "
            f"url='{self.url[:40]}...', "
            f"active={self.is_active}, "
            f"failures={self.failure_count})>"
        )

    def listens_to(self, event: str) -> bool:
        """Bu webhook berilgan voqeani kuzatadimi?"""
        return event in self.events

    @property
    def health_status(self) -> str:
        """Webhook sog'liq holati."""
        if not self.is_active:
            return "inactive"
        if self.failure_count >= 3:
            return "degraded"
        if self.failure_count == 0 and self.success_count > 0:
            return "healthy"
        return "unknown"