"""
Sensor Reading model.

IoT qurilmalardan keluvchi real-time sensor ma'lumotlari.

QURILMALAR:
    - Harorat sensori (tana harorati)
    - Yurak urishi sensori
    - Faollik sensori (akselerometr)
    - Vazn platforma sensori

ARXITEKTURA:
    IoT Device → HTTP POST /api/v1/sensors/reading
    → SensorReading DB ga saqlash
    → Celery task → alert tekshirish
    → ADI _get_sensor_data() → real ma'lumot
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SensorReading(BaseModel):
    """
    Bitta IoT sensor o'lchovi.

    Har bir qurilma har N soniyada bir o'lchov yuboradi.
    ADI service bugungi o'rtacha qiymatlarni oladi.
    """

    __tablename__ = "sensor_readings"

    # ------------------------------------------------------------------ #
    # Foreign Keys                                                         #
    # ------------------------------------------------------------------ #

    animal_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("animals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Jonivor ID (agar aniq bog'langan bo'lsa)",
    )

    # ------------------------------------------------------------------ #
    # Device Info                                                          #
    # ------------------------------------------------------------------ #

    device_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Sensor qurilma ID (masalan: collar-001, scale-A)",
    )

    device_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Qurilma turi: collar | scale | camera | environment",
    )

    # ------------------------------------------------------------------ #
    # Sensor Values                                                        #
    # ------------------------------------------------------------------ #

    # Tana harorati (°C) — normal: 38.0–39.5
    temperature: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Tana harorati °C",
    )

    # Yurak urishi (bpm) — normal: 40–80
    heart_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Yurak urishi bpm",
    )

    # Faollik darajasi (0.0–1.0) — akselerometr
    activity_level: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Faollik 0.0-1.0",
    )

    # Vazn (kg) — platforma sensori
    weight_kg: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Vazn kg",
    )

    # ------------------------------------------------------------------ #
    # Timestamp                                                            #
    # ------------------------------------------------------------------ #

    recorded_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="O'lchov vaqti (UTC)",
    )

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #

    animal: Mapped[Optional["Animal"]] = relationship(  # type: ignore[name-defined]
        "Animal",
        lazy="noload",
    )

    # ------------------------------------------------------------------ #
    # Table Constraints                                                    #
    # ------------------------------------------------------------------ #

    __table_args__ = (
        Index("ix_sensor_animal_time", "animal_id", "recorded_at"),
        Index("ix_sensor_device_time", "device_id", "recorded_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<SensorReading("
            f"id={self.id}, "
            f"device={self.device_id}, "
            f"animal={self.animal_id}, "
            f"temp={self.temperature}, "
            f"hr={self.heart_rate}"
            f")>"
        )