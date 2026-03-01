"""
Taurus Vision — Behavior Analysis Schemas (Sprint 11-12)

Jonivor xatti-harakat tahlili uchun Pydantic v2 schema'lari.
Bu schemalar API request/response va BehaviorService o'rtasida
ma'lumot almashinuvi uchun ishlatiladi.
"""

from typing import Optional
from pydantic import BaseModel, Field


class BehaviorScore(BaseModel):
    """Bitta xatti-harakat o'lchovi uchun ball va talqin."""

    value: float = Field(..., description="Hisoblangan qiymat (masalan: detection soni)")
    max_value: float = Field(..., description="Maksimal kutilgan qiymat")
    percentage: float = Field(..., ge=0, le=100, description="Foiz (0–100)")
    status: str = Field(
        ...,
        description="Holat: excellent / good / fair / poor / critical",
    )
    description: str = Field(..., description="Inson o'qiy oladigan tavsif")


class BehaviorAnalysis(BaseModel):
    """Jonivor xatti-harakat tahlili natijasi."""

    animal_id: int
    animal_tag: Optional[str]
    period_start: str = Field(..., description="Tahlil davri boshlanishi (ISO 8601)")
    period_end: str = Field(..., description="Tahlil davri tugashi (ISO 8601)")
    detection_count: int = Field(..., ge=0, description="Davr ichidagi detection soni")

    # To'rtta asosiy komponent
    activity: BehaviorScore
    feeding: BehaviorScore
    movement: BehaviorScore
    social: BehaviorScore

    # Umumiy natija
    overall_score: float = Field(..., ge=0, le=100, description="Umumiy ball (0–100)")
    overall_status: str = Field(
        ..., description="Umumiy holat: excellent/good/fair/poor/critical"
    )

    # Anomaliyalar va tavsiyalar
    anomalies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    # ADI trend ma'lumotlari
    adi_trend: Optional[str] = Field(
        None, description="ADI yo'nalishi: improving / stable / declining"
    )
    adi_7day: list[float] = Field(
        default_factory=list, description="So'nggi 7 kunlik ADI ballari"
    )

    analyzed_at: str = Field(..., description="Tahlil amalga oshirilgan vaqt (ISO 8601)")


class HerdBehaviorSummary(BaseModel):
    """Butun podaning umumiy xatti-harakat holati."""

    total_animals: int = Field(..., ge=0)
    analyzed_count: int = Field(..., ge=0)
    period: str = Field(..., description="Tahlil davri tavsifi")

    # Holat bo'yicha taqsimot
    excellent_count: int = Field(..., ge=0)
    good_count: int = Field(..., ge=0)
    fair_count: int = Field(..., ge=0)
    poor_count: int = Field(..., ge=0)
    critical_count: int = Field(..., ge=0)
    no_data_count: int = Field(..., ge=0)

    # O'rtacha ko'rsatkichlar (foizda)
    avg_activity: float = Field(..., ge=0, le=100)
    avg_feeding: float = Field(..., ge=0, le=100)
    avg_movement: float = Field(..., ge=0, le=100)
    avg_social: float = Field(..., ge=0, le=100)
    avg_overall: float = Field(..., ge=0, le=100)

    # Diqqat talab qiladiganlar
    attention_needed: list[dict] = Field(
        default_factory=list,
        description="Muammoli jonivorlar: {animal_id, tag, overall_score, status, anomalies, adi_trend}",
    )

    generated_at: str = Field(..., description="Xulosa yaratilgan vaqt (ISO 8601)")


class BehaviorTimelineEntry(BaseModel):
    """Bitta soatlik xatti-harakat ma'lumoti (grafik uchun)."""

    hour: str = Field(..., description="Soat boshlanishi (ISO 8601)")
    detections: int = Field(..., ge=0)
    feeding_visits: int = Field(..., ge=0)
    movement_score: float = Field(..., ge=0, description="bbox cx standart og'ishi")
    camera_id: Optional[str] = Field(None, description="Kamera identifikatori")


class AnomalyEntry(BaseModel):
    """Bitta aniqlangan anomaliya."""

    type: str = Field(
        ...,
        description="Tur: feeding_gap / inactivity / low_movement / social_isolation / other",
    )
    severity: str = Field(..., description="Darajasi: warning / critical")
    description: str = Field(..., description="Anomaliya tavsifi")
    detected_at: str = Field(..., description="Aniqlanish vaqti (ISO 8601)")
    value: Optional[float] = Field(None, description="Qayd etilgan qiymat")
    threshold: Optional[float] = Field(None, description="Chegaraviy qiymat")