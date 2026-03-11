"""
Taurus Vision — Sut Ishlab Chiqarish Sxemalari

REQUEST / RESPONSE sxemalari Pydantic v2 bilan.
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models.milk_production import MilkSession, MilkQualityGrade


# =============================================================================
# BASE
# =============================================================================

class MilkProductionBase(BaseModel):
    record_date: date = Field(..., description="Sog'ish sanasi")
    session: MilkSession = Field(default=MilkSession.DAILY, description="Sessiya vaqti")
    milk_kg: float = Field(..., gt=0, description="Sut miqdori (kg)")
    fat_percent: Optional[float] = Field(None, ge=0, le=15, description="Yog' %")
    protein_percent: Optional[float] = Field(None, ge=0, le=10, description="Oqsil %")
    somatic_cell_count: Optional[int] = Field(None, ge=0, description="SCC (ming/ml)")
    lactose_percent: Optional[float] = Field(None, ge=0, le=10, description="Laktoza %")
    lactation_number: Optional[int] = Field(None, ge=1, description="Nechimchi laktatsiya")
    days_in_milk: Optional[int] = Field(None, ge=0, description="DIM — laktatsiyada necha kun")
    quality_grade: Optional[MilkQualityGrade] = Field(None, description="Sifat darajasi")
    temperature_c: Optional[float] = Field(None, description="Sut harorati °C")
    milked_by: Optional[str] = Field(None, max_length=200, description="Kim sog'di")
    notes: Optional[str] = Field(None, description="Izoh")

    @field_validator("quality_grade", mode="before")
    @classmethod
    def normalize_quality_grade(cls, v):
        if v is None:
            return v
        # Map common aliases to valid enum values
        _alias_map = {
            "grade_a": "premium",
            "a": "premium",
            "grade_b": "standard",
            "b": "standard",
            "grade_c": "low",
            "c": "low",
        }
        if isinstance(v, str):
            v_lower = v.lower()
            return _alias_map.get(v_lower, v)
        return v


# =============================================================================
# CREATE / UPDATE
# =============================================================================

class MilkProductionCreate(MilkProductionBase):
    animal_id: int = Field(..., description="Jonivor ID si")


class MilkProductionUpdate(BaseModel):
    milk_kg: Optional[float] = Field(None, gt=0)
    fat_percent: Optional[float] = Field(None, ge=0, le=15)
    protein_percent: Optional[float] = Field(None, ge=0, le=10)
    somatic_cell_count: Optional[int] = Field(None, ge=0)
    lactose_percent: Optional[float] = Field(None, ge=0, le=10)
    lactation_number: Optional[int] = Field(None, ge=1)
    days_in_milk: Optional[int] = Field(None, ge=0)
    quality_grade: Optional[MilkQualityGrade] = None
    temperature_c: Optional[float] = None
    milked_by: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None


# =============================================================================
# RESPONSE
# =============================================================================

class MilkProductionResponse(MilkProductionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    animal_id: int
    created_at: datetime
    updated_at: datetime


class MilkProductionListResponse(BaseModel):
    items: List[MilkProductionResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# STATISTICS (Animal uchun sut statistikasi)
# =============================================================================

class MilkStatsPeriod(BaseModel):
    """Davr uchun sut statistikasi."""
    total_kg: float = Field(description="Jami sut (kg)")
    avg_daily_kg: float = Field(description="Kunlik o'rtacha (kg)")
    avg_fat_percent: Optional[float] = Field(None, description="O'rtacha yog' %")
    avg_protein_percent: Optional[float] = Field(None, description="O'rtacha oqsil %")
    avg_scc: Optional[float] = Field(None, description="O'rtacha SCC")
    days_recorded: int = Field(description="Yozuv kunlari soni")
    best_day_kg: Optional[float] = Field(None, description="Eng ko'p sut kuni (kg)")
    trend_percent: Optional[float] = Field(None, description="O'tgan davrga nisbatan o'zgarish %")


class AnimalMilkSummary(BaseModel):
    """Bitta jonivorning sut xulosasi."""
    animal_id: int
    animal_tag: str
    current_lactation: Optional[int]
    days_in_milk: Optional[int]
    last_7_days_kg: float
    last_30_days_kg: float
    today_kg: float
    stats_30d: MilkStatsPeriod
    recent_records: List[MilkProductionResponse]


class FarmMilkSummary(BaseModel):
    """Butun ferma bo'yicha sut xulosasi."""
    today_total_kg: float
    this_month_kg: float
    last_month_kg: float
    active_dairy_animals: int
    avg_per_animal_kg: float
    top_producers: List[dict]
    daily_trend: List[dict]  # [{date, total_kg, animal_count}]