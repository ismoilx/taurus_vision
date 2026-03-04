"""
Taurus Vision — Sensor Schemas (Sprint 17-18)

IoT sensor ma'lumotlari uchun Pydantic v2 schemalar.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class SensorReadingCreate(BaseModel):
    """IoT qurilmadan keluvchi o'lchov. POST /sensors/reading"""

    device_id: str = Field(..., min_length=1, max_length=100,
                           description="Qurilma ID: collar-001, scale-A")
    device_type: str = Field(..., description="collar | scale | environment")
    animal_id: Optional[int] = Field(None, description="Bog'liq jonivor ID")

    temperature:    Optional[float] = Field(None, ge=30.0, le=45.0,
                                            description="Tana harorati °C")
    heart_rate:     Optional[float] = Field(None, ge=10.0, le=200.0,
                                            description="Yurak urishi bpm")
    activity_level: Optional[float] = Field(None, ge=0.0, le=1.0,
                                            description="Faollik 0.0-1.0")
    weight_kg:      Optional[float] = Field(None, ge=0.0, le=2000.0,
                                            description="Vazn kg")
    recorded_at:    Optional[datetime] = Field(None,
                                               description="O'lchov vaqti UTC (None=hozir)")

    @field_validator("device_type")
    @classmethod
    def validate_device_type(cls, v: str) -> str:
        allowed = {"collar", "scale", "environment", "camera"}
        if v not in allowed:
            raise ValueError(f"device_type must be one of: {allowed}")
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (30.0 <= v <= 45.0):
            raise ValueError("Harorat 30–45°C oralig'ida bo'lishi kerak")
        return v


class SensorReadingBulkCreate(BaseModel):
    """Bir nechta o'lchovni bir vaqtda yuborish (batch)."""
    readings: list[SensorReadingCreate] = Field(..., min_length=1, max_length=100)


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class SensorReadingResponse(BaseModel):
    """Bitta sensor o'lchovi response."""
    id:             int
    device_id:      str
    device_type:    str
    animal_id:      Optional[int]
    temperature:    Optional[float]
    heart_rate:     Optional[float]
    activity_level: Optional[float]
    weight_kg:      Optional[float]
    recorded_at:    datetime
    created_at:     datetime

    model_config = {"from_attributes": True}


class SensorLatestResponse(BaseModel):
    """Jonivorning eng so'nggi sensor ko'rsatkichlari."""
    animal_id:          int
    tag_id:             str
    last_temperature:   Optional[float]
    last_heart_rate:    Optional[float]
    last_activity:      Optional[float]
    last_weight_kg:     Optional[float]
    last_reading_at:    Optional[datetime]
    readings_today:     int
    health_status:      str  # normal | warning | critical | unknown
    alerts:             list[str]


class SensorDailySummary(BaseModel):
    """Kunlik sensor xulosasi — ADI uchun."""
    animal_id:          int
    date:               str
    avg_temperature:    Optional[float]
    avg_heart_rate:     Optional[float]
    avg_activity:       Optional[float]
    avg_weight_kg:      Optional[float]
    reading_count:      int
    anomaly_count:      int


class SensorDeviceListResponse(BaseModel):
    """Ro'yxatdagi barcha qurilmalar."""
    total:   int
    devices: list[dict]


class SensorStatsResponse(BaseModel):
    """Ferma bo'yicha sensor statistikasi."""
    total_devices:         int
    active_devices_24h:    int
    total_readings_today:  int
    animals_with_sensors:  int
    critical_alerts:       int
    warning_alerts:        int