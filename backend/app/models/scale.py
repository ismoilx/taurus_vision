"""
Taurus Vision — Scale (Tarozi) Database Model

Fizik tarozi qurilmalarni ro'yxatga olish va ularga
kelgan o'lchovlarni saqlash uchun model.

Tarozi turlari:
  MANUAL   — foydalanuvchi natijani qo'lda kiritadi
  SERIAL   — USB/RS-232 orqali ulangan tarozi (webhook)
  API      — Ethernet/Wi-Fi tarozi (to'g'ridan HTTP POST)
"""

import enum
from typing import Optional
from datetime import datetime

from sqlalchemy import String, Boolean, Enum as SQLEnum, Float, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ScaleType(str, enum.Enum):
    MANUAL = "manual"    # Foydalanuvchi qo'lda kiritadi
    SERIAL = "serial"    # USB/RS-232 serial port
    API    = "api"       # Tarozi o'zi HTTP yuboradi
    FLOOR  = "floor"     # Pol tarozisi (katta hayvonlar uchun)


class ScaleStatus(str, enum.Enum):
    ACTIVE   = "active"
    INACTIVE = "inactive"
    ERROR    = "error"


class Scale(BaseModel):
    """
    Fizik tarozi qurilma modeli.

    Har bir ferma bir nechta taroziga ega bo'lishi mumkin.
    Har tarozi o'zining turi, joylashuvi va kalibrlash
    ma'lumotlariga ega.
    """

    __tablename__ = "scales"

    # ------------------------------------------------------------------ #
    # Identifikatsiya                                                       #
    # ------------------------------------------------------------------ #

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Tarozi nomi (masalan: Asosiy tarozi, G'alla ombori #2)",
    )

    scale_type: Mapped[ScaleType] = mapped_column(
        SQLEnum(ScaleType, name="scale_type"),
        nullable=False,
        default=ScaleType.MANUAL,
        comment="Tarozi turi: manual | serial | api",
    )

    location: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Tarozi joylashuvi (masalan: Asosiy molxona kirishi)",
    )

    # ------------------------------------------------------------------ #
    # Holat                                                                 #
    # ------------------------------------------------------------------ #

    status: Mapped[ScaleStatus] = mapped_column(
        SQLEnum(ScaleStatus, name="scale_status"),
        nullable=False,
        default=ScaleStatus.ACTIVE,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="False = tarozi o'chirilgan",
    )

    # ------------------------------------------------------------------ #
    # Serial port konfiguratsiyasi (scale_type=SERIAL uchun)               #
    # ------------------------------------------------------------------ #

    serial_port: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Serial port manzili (masalan: /dev/ttyUSB0, COM3)",
    )

    baud_rate: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=9600,
        comment="Serial port baud rate (9600, 19200, 38400, 115200)",
    )

    data_format: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="8N1",
        comment="Serial data format (8N1, 7E1, ...)",
    )

    # Tarozi ma'lumot formati uchun regex pattern
    # Masalan: r"(\d+\.?\d*)\s*kg" — "245.3 kg" ni parse qilish uchun
    data_pattern: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Tarozi output formatini parse qiluvchi regex pattern",
    )

    # ------------------------------------------------------------------ #
    # Kalibrlash                                                            #
    # ------------------------------------------------------------------ #

    # AI taxmin xatosini tuzatish koeffitsiyenti
    # calibration_factor = real_weight / ai_estimated_weight
    # 1.0 = perfekt, 0.9 = AI 10% oshirib aytmoqda, 1.1 = 10% kamaytirib
    calibration_factor: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment="AI kalibratsiya koeffitsiyenti (real/AI taxmin nisbati)",
    )

    calibration_sample_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Kalibratsiya uchun ishlatilgan o'lchovlar soni",
    )

    last_calibrated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="So'nggi kalibratsiya vaqti",
    )

    # ------------------------------------------------------------------ #
    # So'nggi o'lchov                                                       #
    # ------------------------------------------------------------------ #

    last_reading_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Oxirgi o'lchov vaqti",
    )

    last_weight_kg: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Oxirgi o'lchov qiymati (kg)",
    )

    # ------------------------------------------------------------------ #
    # Qo'shimcha                                                            #
    # ------------------------------------------------------------------ #

    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    api_token: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="API autentifikatsiya tokeni (IoT qurilma uchun)",
    )

    # ------------------------------------------------------------------
    # Capacity & Precision (added for test compatibility)
    # ------------------------------------------------------------------

    capacity_kg: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Maksimal o'lchov qobiliyati (kg)",
    )

    precision_kg: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="O'lchov aniqligi (kg)",
    )

    # ------------------------------------------------------------------ #
    # Relationships                                                         #
    # ------------------------------------------------------------------ #

    readings: Mapped[list["WeightMeasurement"]] = relationship(  # type: ignore[name-defined]
        "WeightMeasurement",
        back_populates="scale",
        lazy="noload",
        foreign_keys="WeightMeasurement.scale_id",
    )

    # ------------------------------------------------------------------ #
    # Helpers                                                               #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"<Scale("
            f"id={self.id}, "
            f"name='{self.name}', "
            f"type={self.scale_type.value}, "
            f"status={self.status.value}"
            f")>"
        )

    @property
    def is_serial(self) -> bool:
        return self.scale_type == ScaleType.SERIAL

    @property
    def is_calibrated(self) -> bool:
        """Kamida 5 ta haqiqiy o'lchov asosida kalibratlangan."""
        return self.calibration_sample_count >= 5