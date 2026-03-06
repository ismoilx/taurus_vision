"""
Taurus Vision — Scale (Tarozi) Pydantic Schemas

Q7 — Tarozi integratsiyasi: request/response schemalar.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
import re


# =============================================================================
# SCALE — CRUD schemalar
# =============================================================================

class ScaleBase(BaseModel):
    name:         str            = Field(..., min_length=2, max_length=100)
    scale_type:   str            = Field("manual", description="manual | serial | api")
    location:     Optional[str]  = Field(None, max_length=200)
    serial_port:  Optional[str]  = Field(None, max_length=50,  description="/dev/ttyUSB0 yoki COM3")
    baud_rate:    Optional[int]  = Field(9600, ge=300, le=921600)
    data_format:  Optional[str]  = Field("8N1", max_length=10)
    data_pattern: Optional[str]  = Field(None, max_length=200, description="Regex: r'(\\d+\\.?\\d*)\\s*kg'")
    notes:        Optional[str]  = Field(None, max_length=1000)


class ScaleCreate(ScaleBase):
    pass


class ScaleUpdate(BaseModel):
    name:         Optional[str]  = Field(None, min_length=2, max_length=100)
    location:     Optional[str]  = Field(None, max_length=200)
    scale_type:   Optional[str]  = None
    serial_port:  Optional[str]  = Field(None, max_length=50)
    baud_rate:    Optional[int]  = Field(None, ge=300, le=921600)
    data_format:  Optional[str]  = Field(None, max_length=10)
    data_pattern: Optional[str]  = Field(None, max_length=200)
    notes:        Optional[str]  = Field(None, max_length=1000)
    is_active:    Optional[bool] = None


class ScaleResponse(ScaleBase):
    model_config = ConfigDict(from_attributes=True)

    id:                       int
    status:                   str
    is_active:                bool
    calibration_factor:       float
    calibration_sample_count: int
    last_calibrated_at:       Optional[datetime]
    last_reading_at:          Optional[datetime]
    last_weight_kg:           Optional[float]
    is_calibrated:            bool
    api_token:                Optional[str]   = None
    created_at:               datetime
    updated_at:               datetime


class ScaleListResponse(BaseModel):
    items: list[ScaleResponse]
    total: int


# =============================================================================
# MANUAL WEIGHT — Foydalanuvchi qo'lda kiritadi
# =============================================================================

class ManualWeightCreate(BaseModel):
    """
    Foydalanuvchi tarozidan o'qib, qo'lda kiritadigan vazn.

    animal_id    — qaysi jonivor
    weight_kg    — tarozida ko'rsatilgan vazn (kg)
    scale_id     — qaysi tarozi ishlatildi (ixtiyoriy)
    measured_at  — o'lchov vaqti (bo'sh = hozir)
    notes        — qo'shimcha izoh
    """
    animal_id:   int            = Field(..., gt=0)
    weight_kg:   float          = Field(..., gt=0, le=2000, description="Haqiqiy tarozi vazni (kg)")
    scale_id:    Optional[int]  = Field(None, description="Tarozi qurilma ID si (ixtiyoriy)")
    measured_at: Optional[datetime] = Field(None, description="O'lchov vaqti (bo'sh = hozir)")
    notes:       Optional[str]  = Field(None, max_length=500)

    @field_validator("weight_kg")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Vazn musbat bo'lishi kerak")
        return round(v, 2)


# =============================================================================
# SCALE WEBHOOK — Tarozi o'zi yuboradi (serial/api)
# =============================================================================

class ScaleWebhookPayload(BaseModel):
    """
    Serial yoki API tarozi backend ga yuboradigan payload.

    api_token  — tarozining autentifikatsiya tokeni
    weight_kg  — o'lchangan vazn
    animal_id  — aniqlangan jonivor ID (ixtiyoriy, sensor aniqlasa)
    raw_data   — tarozidan kelgan xom matn (debug uchun)
    """
    api_token: str   = Field(..., min_length=8)
    weight_kg: float = Field(..., gt=0, le=2000)
    animal_id: Optional[int]  = Field(None, gt=0)
    raw_data:  Optional[str]  = Field(None, max_length=500)


# =============================================================================
# CALIBRATION
# =============================================================================

class CalibrationDataPoint(BaseModel):
    """Bitta kalibratsiya nuqtasi: AI taxmin va haqiqiy vazn."""
    measurement_id: int   = Field(..., gt=0, description="WeightMeasurement ID si")
    actual_weight_kg: float = Field(..., gt=0, le=2000, description="Tarozida ko'rsatilgan haqiqiy vazn")


class CalibrationResponse(BaseModel):
    """Kalibratsiya natijasi."""
    scale_id:              int
    scale_name:            str
    old_factor:            float
    new_factor:            float
    sample_count:          int
    mean_absolute_error:   float  # kg
    mean_relative_error:   float  # foiz
    message:               str


# =============================================================================
# WEIGHT COMPARISON — AI vs Haqiqiy
# =============================================================================

class WeightComparisonItem(BaseModel):
    """Bitta o'lchov uchun AI taxmin vs haqiqiy vazn taqqoslash."""
    measurement_id:      int
    animal_id:           int
    animal_tag_id:       str
    timestamp:           datetime
    ai_weight_kg:        float
    actual_weight_kg:    Optional[float]
    difference_kg:       Optional[float]
    difference_pct:      Optional[float]
    source:              str


class WeightComparisonResponse(BaseModel):
    """Kalibratsiya tahlili uchun AI vs haqiqiy taqqoslash."""
    items:               list[WeightComparisonItem]
    total:               int
    mean_error_kg:       Optional[float]
    mean_error_pct:      Optional[float]
    current_factor:      float
    recommended_factor:  Optional[float]


# =============================================================================
# WEIGHT MEASUREMENT — kengaytirilgan schema (source + actual qo'shildi)
# =============================================================================

class WeightMeasurementExtended(BaseModel):
    """Kengaytirilgan WeightMeasurement response (tarozi integratsiyasi bilan)."""
    model_config = ConfigDict(from_attributes=True)

    id:                  int
    animal_id:           int
    timestamp:           datetime
    estimated_weight_kg: float
    actual_weight_kg:    Optional[float]
    confidence_score:    float
    camera_id:           str
    source:              str
    scale_id:            Optional[int]
    notes:               Optional[str]
    image_path:          Optional[str]
    created_at:          datetime