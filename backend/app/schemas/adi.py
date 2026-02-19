"""
ADI Pydantic schemas.

Request/Response sxemalari — API va servis qatlami orasidagi
ma'lumot validatsiyasi va serializatsiyasi uchun.
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator


# ------------------------------------------------------------------ #
# Component Scores Schema                                              #
# ------------------------------------------------------------------ #

class ADIComponentScores(BaseModel):
    """
    ADI komponent ballari.

    Har bir komponent 0.0 — 100.0 oralig'ida.
    None = ma'lumot mavjud emas (sensor yo'q, kamera ko'rmadi).
    """

    activity_score:   Optional[float] = Field(None, ge=0.0, le=100.0,
        description="Faollik: kamera deteksiyalari asosida (og'irlik: 0.20)")
    feeding_score:    Optional[float] = Field(None, ge=0.0, le=100.0,
        description="Ovqatlanish: ozuqa zonasiga tashrif (og'irlik: 0.20)")
    drinking_score:   Optional[float] = Field(None, ge=0.0, le=100.0,
        description="Suv ichish: suv zonasiga tashrif (og'irlik: 0.10)")
    movement_score:   Optional[float] = Field(None, ge=0.0, le=100.0,
        description="Harakat sifati: bbox dinamikasi (og'irlik: 0.15)")
    growth_score:     Optional[float] = Field(None, ge=0.0, le=100.0,
        description="O'sish dinamikasi: 30 kunlik bbox trendi (og'irlik: 0.20)")
    social_score:     Optional[float] = Field(None, ge=0.0, le=100.0,
        description="Ijtimoiy indeks: birgalikda deteksiya (og'irlik: 0.10)")
    sensor_score:     Optional[float] = Field(None, ge=0.0, le=100.0,
        description="Sensor: harorat, yurak urishi (og'irlik: 0.05)")
    veterinary_score: Optional[float] = Field(None, ge=0.0, le=100.0,
        description="Veterinar holati: tekshiruv natijalari (og'irlik: 0.05)")


# ------------------------------------------------------------------ #
# Response Schemas                                                     #
# ------------------------------------------------------------------ #

class ADILogResponse(BaseModel):
    """
    Bitta ADI yozuvini qaytarish uchun schema.
    API response da ishlatiladi.
    """

    id:               int
    animal_id:        int
    calculated_at:    datetime
    calculation_date: str

    # Result
    adi_score:        float = Field(..., ge=0.0, le=100.0)
    category:         str

    # Components
    scores:           ADIComponentScores

    # Meta
    data_quality:     float = Field(..., ge=0.0, le=1.0)
    notes:            Optional[str] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_flat(cls, obj: Any) -> "ADILogResponse":
        """
        SQLAlchemy ADILog obyektidan Response yaratish.

        ADILog da komponentlar flat (yassi) saqlanadi,
        bu yerda ularni ADIComponentScores ga joylashtiramiz.
        """
        return cls(
            id=obj.id,
            animal_id=obj.animal_id,
            calculated_at=obj.calculated_at,
            calculation_date=obj.calculation_date,
            adi_score=obj.adi_score,
            category=obj.category,
            scores=ADIComponentScores(
                activity_score=obj.activity_score,
                feeding_score=obj.feeding_score,
                drinking_score=obj.drinking_score,
                movement_score=obj.movement_score,
                growth_score=obj.growth_score,
                social_score=obj.social_score,
                sensor_score=obj.sensor_score,
                veterinary_score=obj.veterinary_score,
            ),
            data_quality=obj.data_quality,
            notes=obj.notes,
        )


class ADITrendPoint(BaseModel):
    """Trend grafigi uchun bitta nuqta."""

    date:     str   = Field(..., description="YYYY-MM-DD")
    score:    float = Field(..., ge=0.0, le=100.0)
    category: str


class ADITrendResponse(BaseModel):
    """
    Jonivorning ADI trend tarixi.
    Grafik chizish uchun ishlatiladi.
    """

    animal_id:    int
    animal_tag:   str
    period_days:  int
    trend:        list[ADITrendPoint]
    avg_score:    float
    min_score:    float
    max_score:    float
    current:      Optional[ADILogResponse] = None


class ADIFarmSummaryItem(BaseModel):
    """Ferma darajasidagi bitta jonivor ADI xulosasi."""

    animal_id:   int
    tag_id:      str
    species:     str
    adi_score:   float
    category:    str
    trend:       str  # "up" | "down" | "stable" | "unknown"
    last_updated: Optional[str] = None  # YYYY-MM-DD


class ADIFarmSummary(BaseModel):
    """
    Butun ferma bo'yicha ADI xulosasi.
    Dashboard uchun asosiy widget.
    """

    date:          str
    total_animals: int

    # Kategoriya bo'yicha taqsimot
    healthy_count:  int
    average_count:  int
    warning_count:  int
    critical_count: int

    # Foiz
    healthy_pct:  float
    average_pct:  float
    warning_pct:  float
    critical_pct: float

    # Umumiy ko'rsatkichlar
    farm_adi_score: float   # Barcha jonivvorlar o'rtacha ADI
    needs_attention: list[ADIFarmSummaryItem]   # warning + critical

    model_config = {"from_attributes": True}


class ADICalculationRequest(BaseModel):
    """
    Qo'lda ADI hisoblashni ishga tushirish uchun request.
    Asosan testing va debug uchun.
    """

    animal_id:        Optional[int]  = Field(None,
        description="Bitta jonivor uchun. None = barcha aktiv jonivorlar")
    target_date:      Optional[str]  = Field(None,
        description="YYYY-MM-DD. None = bugun")
    force_recalculate: bool          = Field(False,
        description="True = mavjud yozuvni qayta hisoblash")

    @field_validator("target_date")
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("target_date format: YYYY-MM-DD bo'lishi kerak")
        return v


class ADICalculationResult(BaseModel):
    """ADI hisoblash natijasi."""

    success:          bool
    animal_id:        int
    calculation_date: str
    adi_score:        Optional[float]  = None
    category:         Optional[str]   = None
    data_quality:     Optional[float] = None
    error:            Optional[str]   = None
    skipped:          bool            = False
    skip_reason:      Optional[str]   = None


class ADIBatchCalculationResponse(BaseModel):
    """Ommaviy ADI hisoblash natijasi."""

    total:      int
    success:    int
    failed:     int
    skipped:    int
    results:    list[ADICalculationResult]
    duration_ms: float
