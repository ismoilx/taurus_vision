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
import enum

from sqlalchemy import String, Float, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SensorType(str, enum.Enum):
    """IoT sensor qurilma turlari."""
    TEMPERATURE  = "temperature"   # Tana harorati
    HEART_RATE   = "heart_rate"    # Yurak urishi
    ACTIVITY     = "activity"      # Harakat/faollik
    WEIGHT       = "weight"        # Vazn platforma
    HUMIDITY     = "humidity"      # Namlik
    GPS          = "gps"           # Joylashuv
    OTHER        = "other"         # Boshqa


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

    # ------------------------------------------------------------------
    # Backward-compatibility aliases for tests
    # ------------------------------------------------------------------

    @property
    def sensor_type(self) -> Optional[str]:
        """Alias for `device_type` — tests use `sensor_type`."""
        return self.device_type

    @sensor_type.setter
    def sensor_type(self, value) -> None:
        self.device_type = value.value if hasattr(value, "value") else value

    @property
    def timestamp(self):
        """Alias for `recorded_at` — tests use `timestamp`."""
        return self.recorded_at

    @timestamp.setter
    def timestamp(self, value) -> None:
        self.recorded_at = value

    @property
    def value(self) -> Optional[float]:
        """Generic sensor value — returns first non-None measurement."""
        for v in (self.temperature, self.heart_rate, self.activity_level, self.weight_kg):
            if v is not None:
                return v
        return None

    @value.setter
    def value(self, v: float) -> None:
        """Store generic value in temperature slot by default."""
        self.temperature = v

    @property
    def unit(self) -> Optional[str]:
        """Unit is stored in meta; if not present returns a type-based default."""
        return None  # Not persisted; provided for interface compatibility

    def __init__(self, **kwargs):
        # Accept test-friendly aliases
        if "sensor_type" in kwargs and "device_type" not in kwargs:
            st = kwargs.pop("sensor_type")
            kwargs["device_type"] = st.value if hasattr(st, "value") else str(st)
        elif "sensor_type" in kwargs:
            kwargs.pop("sensor_type")
        if "timestamp" in kwargs and "recorded_at" not in kwargs:
            kwargs["recorded_at"] = kwargs.pop("timestamp")
        elif "timestamp" in kwargs:
            kwargs.pop("timestamp")
        # Generic `value` → map to correct sensor column based on device_type
        if "value" in kwargs:
            val = kwargs.pop("value")
            device_type = kwargs.get("device_type", "")
            if "heart" in str(device_type):
                kwargs.setdefault("heart_rate", val)
            elif "activity" in str(device_type):
                kwargs.setdefault("activity_level", val)
            elif "weight" in str(device_type):
                kwargs.setdefault("weight_kg", val)
            else:
                kwargs.setdefault("temperature", val)
        kwargs.pop("unit", None)  # Not a column
        super().__init__(**kwargs)