"""
Taurus Vision — Go'sht Ishlab Chiqarish Sxemalari

REQUEST / RESPONSE sxemalari Pydantic v2 bilan.
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel, Field, model_validator, ConfigDict

from app.models.meat_production import SlaughterPurpose, MeatQualityGrade


# =============================================================================
# BASE
# =============================================================================

class SlaughterRecordBase(BaseModel):
    slaughter_date:    date             = Field(...,  description="So'yish sanasi")
    purpose:           SlaughterPurpose = Field(default=SlaughterPurpose.SALE, description="Maqsad")
    live_weight_kg:    Optional[float]  = Field(None, gt=0,  description="Tirik vazn (kg)")
    carcass_weight_kg: Optional[float]  = Field(None, gt=0,  description="Karkas vazni (kg)")
    dressing_percent:  Optional[float]  = Field(None, gt=0, le=100, description="So'yish foizi (%)")
    meat_kg:           float            = Field(...,  ge=0,  description="Sof go'sht (kg)")
    bone_kg:           Optional[float]  = Field(None, ge=0,  description="Suyak (kg)")
    fat_kg:            Optional[float]  = Field(None, ge=0,  description="Yog' (kg)")
    offal_kg:          Optional[float]  = Field(None, ge=0,  description="Ichki organlar (kg)")
    hide_kg:           Optional[float]  = Field(None, ge=0,  description="Teri (kg)")
    quality_grade:     Optional[MeatQualityGrade] = Field(None, description="Sifat darajasi")
    ph_value:          Optional[float]  = Field(None, ge=0, le=14, description="pH qiymati")
    color_score:       Optional[int]    = Field(None, ge=1, le=5,  description="Rang bahosi (1–5)")
    marbling_score:    Optional[int]    = Field(None, ge=1, le=5,  description="Marmar bahosi (1–5)")
    temperature_c:     Optional[float]  = Field(None, description="Saqlash harorati (°C)")
    price_per_kg:      Optional[float]  = Field(None, ge=0, description="1 kg narxi (so'm)")
    total_revenue:     Optional[float]  = Field(None, ge=0, description="Jami tushum (so'm)")
    veterinary_check:  bool             = Field(default=False, description="Vet tekshiruvi")
    slaughtered_by:    Optional[str]    = Field(None, max_length=200, description="Kim so'ydi")
    notes:             Optional[str]    = Field(None, description="Izoh")

    @model_validator(mode="after")
    def auto_calculate_fields(self) -> "SlaughterRecordBase":
        """So'yish foizi va tushum avtomatik hisoblash."""
        # So'yish foizini hisoblash (agar berilmasa)
        if (
            self.dressing_percent is None
            and self.carcass_weight_kg
            and self.live_weight_kg
            and self.live_weight_kg > 0
        ):
            self.dressing_percent = round(
                (self.carcass_weight_kg / self.live_weight_kg) * 100, 2
            )

        # Jami tushum hisoblash (agar berilmasa)
        if (
            self.total_revenue is None
            and self.price_per_kg
            and self.meat_kg
        ):
            self.total_revenue = round(self.price_per_kg * self.meat_kg, 2)

        return self


# =============================================================================
# CREATE / UPDATE
# =============================================================================

class SlaughterRecordCreate(SlaughterRecordBase):
    animal_id: int = Field(..., description="Jonivor ID si")


class SlaughterRecordUpdate(BaseModel):
    slaughter_date:    Optional[date]             = None
    purpose:           Optional[SlaughterPurpose] = None
    live_weight_kg:    Optional[float]            = Field(None, gt=0)
    carcass_weight_kg: Optional[float]            = Field(None, gt=0)
    dressing_percent:  Optional[float]            = Field(None, gt=0, le=100)
    meat_kg:           Optional[float]            = Field(None, ge=0)
    bone_kg:           Optional[float]            = Field(None, ge=0)
    fat_kg:            Optional[float]            = Field(None, ge=0)
    offal_kg:          Optional[float]            = Field(None, ge=0)
    hide_kg:           Optional[float]            = Field(None, ge=0)
    quality_grade:     Optional[MeatQualityGrade] = None
    ph_value:          Optional[float]            = Field(None, ge=0, le=14)
    color_score:       Optional[int]              = Field(None, ge=1, le=5)
    marbling_score:    Optional[int]              = Field(None, ge=1, le=5)
    temperature_c:     Optional[float]            = None
    price_per_kg:      Optional[float]            = Field(None, ge=0)
    total_revenue:     Optional[float]            = Field(None, ge=0)
    veterinary_check:  Optional[bool]             = None
    slaughtered_by:    Optional[str]              = Field(None, max_length=200)
    notes:             Optional[str]              = None


# =============================================================================
# RESPONSE
# =============================================================================

class SlaughterRecordResponse(SlaughterRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id:         int
    animal_id:  int
    created_at: datetime
    updated_at: datetime

    # Computed fields (optional enrichment from service layer)
    animal_tag:     Optional[str] = None
    animal_name:    Optional[str] = None
    animal_species: Optional[str] = None
    animal_breed:   Optional[str] = None
    animal_age_months: Optional[int] = None


class SlaughterRecordListResponse(BaseModel):
    items:     List[SlaughterRecordResponse]
    total:     int
    page:      int
    page_size: int


# =============================================================================
# STATISTICS
# =============================================================================

class MeatStatsPeriod(BaseModel):
    """Davr uchun go'sht statistikasi."""
    total_meat_kg:           float            = Field(description="Jami go'sht (kg)")
    total_animals_slaughtered: int            = Field(description="So'yilgan jonivorlar soni")
    avg_meat_per_animal_kg:  float            = Field(description="Jonivor boshiga o'rtacha go'sht (kg)")
    avg_dressing_percent:    Optional[float]  = Field(None, description="O'rtacha so'yish foizi (%)")
    avg_live_weight_kg:      Optional[float]  = Field(None, description="O'rtacha tirik vazn (kg)")
    total_revenue:           Optional[float]  = Field(None, description="Jami tushum (so'm)")
    avg_price_per_kg:        Optional[float]  = Field(None, description="O'rtacha narx (so'm/kg)")
    best_animal_meat_kg:     Optional[float]  = Field(None, description="Eng ko'p go'sht bergan jonivor (kg)")
    total_bone_kg:           float            = Field(default=0, description="Jami suyak (kg)")
    total_fat_kg:            float            = Field(default=0, description="Jami yog' (kg)")
    total_offal_kg:          float            = Field(default=0, description="Jami ichki organlar (kg)")
    total_hide_kg:           float            = Field(default=0, description="Jami teri (kg)")


class AnimalMeatSummary(BaseModel):
    """Bitta jonivorning go'sht xulosa (agar bir necha marta so'yilgan bo'lsa)."""
    animal_id:      int
    animal_tag:     str
    animal_name:    Optional[str]
    animal_species: str
    total_records:  int
    total_meat_kg:  float
    last_slaughter_date: Optional[str]
    avg_meat_kg:    float
    total_revenue:  Optional[float]
    recent_records: List[SlaughterRecordResponse]


class FarmMeatSummary(BaseModel):
    """Butun ferma bo'yicha go'sht xulosasi."""
    # Bugungi
    today_animals_count:  int
    today_meat_kg:        float
    today_revenue:        Optional[float]

    # Bu oylik
    this_month_animals:   int
    this_month_kg:        float
    this_month_revenue:   Optional[float]

    # O'tgan oylik (taqqoslash uchun)
    last_month_animals:   int
    last_month_kg:        float
    last_month_revenue:   Optional[float]

    # Jami statistika
    all_time_animals:     int
    all_time_kg:          float

    # Trenlar
    daily_trend:          List[dict]   # [{date, meat_kg, animals_count, revenue}]
    purpose_breakdown:    List[dict]   # [{purpose, count, meat_kg, revenue}]
    quality_breakdown:    List[dict]   # [{grade, count, meat_kg, percent}]

    # Top jonivorlar (eng ko'p go'sht)
    top_animals:          List[dict]


class MeatDailyRecord(BaseModel):
    """Kunlik go'sht statistikasi (trend uchun)."""
    date:           str
    meat_kg:        float
    animals_count:  int
    revenue:        Optional[float]
    avg_dressing:   Optional[float]