"""
Taurus Vision — Breeding & Genealogy Pydantic Schemas (Sprint 25-26)

SXEMALAR:
    BreedingRecordCreate     — POST /breeding/records
    BreedingRecordUpdate     — PATCH /breeding/records/{id}
    BreedingRecordResponse   — GET javobi (to'liq)
    BreedingRecordList       — Sahifalangan ro'yxat

    BreedingConfirmPregnancy — Homiladorlikni tasdiqlash
    BreedingRecordBirth      — Tug'ilishni qayd etish

    OffspringCreate          — Har bir nasl uchun
    OffspringResponse        — Nasl javobi

    GenealogyNode            — Shajara daraxti uchi
    BreedingStats            — Statistika
    BreedingRecommendation   — AI juft tavsiyasi
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from app.models.breeding import (
    MatingMethod,
    BreedingStatus,
    PregnancyCheckMethod,
    OffspringOutcome,
    GESTATION_DAYS,
)


# =============================================================================
# OFFSPRING SCHEMAS
# =============================================================================

class OffspringCreate(BaseModel):
    """Yangi nasl ma'lumotlari."""
    birth_order:    int            = Field(1, ge=1, le=10)
    gender:         Optional[str]  = Field(None, pattern="^(male|female|unknown)$")
    birth_weight_kg: Optional[float] = Field(None, gt=0, le=200)
    outcome:        OffspringOutcome = OffspringOutcome.ALIVE
    notes:          Optional[str]  = Field(None, max_length=500)


class OffspringResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                 int
    breeding_record_id: int
    animal_id:          Optional[int]
    birth_order:        int
    gender:             Optional[str]
    birth_weight_kg:    Optional[float]
    outcome:            OffspringOutcome
    notes:              Optional[str]
    created_at:         datetime

    # Embedded animal info (agar ro'yxatdan o'tgan bo'lsa)
    animal_tag_id: Optional[str] = None


# =============================================================================
# BREEDING RECORD — CREATE
# =============================================================================

class BreedingRecordCreate(BaseModel):
    """
    POST /breeding/records — Yangi nasl yozuvi yaratish.

    VALIDATSIYA QOIDALARI:
        1. father_id/sire_id YOKI external_sire_tag ALBATTA kerak (AI metod uchun ixtiyoriy)
        2. Mating date kelajakda bo'lmasin
        3. Expected birth date avtomatik hisoblanadi (agar berilmasa)
    """

    farm_id: Optional[int] = Field(None, description="Ferma ID (null = default farm)")

    # Support both mother_id and dam_id (test alias)
    mother_id:  Optional[int] = Field(None, gt=0, description="Ona jonivor ID (female animal)")
    dam_id:     Optional[int] = Field(None, gt=0, description="Alias for mother_id")

    # Ota — ichki yoki tashqi; support sire_id alias
    father_id:           Optional[int] = Field(None, gt=0)
    sire_id:             Optional[int] = Field(None, gt=0, description="Alias for father_id")
    external_sire_tag:   Optional[str] = Field(None, max_length=100)
    external_sire_breed: Optional[str] = Field(None, max_length=100)
    external_sire_farm:  Optional[str] = Field(None, max_length=200)

    # Support both mating_date and breeding_date (test alias)
    mating_date:    Optional[date]  = Field(None, description="Juftlashish sanasi")
    breeding_date:  Optional[date]  = Field(None, description="Alias for mating_date")

    # Support both mating_method and method (test alias)
    mating_method:  Optional[MatingMethod] = Field(None)
    method:         Optional[str]          = Field(None, description="Alias for mating_method")

    # Gestatsiya (avtomatik hisoblanadi, lekin override mumkin)
    gestation_days: Optional[int] = Field(
        None, ge=100, le=400,
        description="Gestatsiya muddati (kun). Bo'sh qolsa species bo'yicha avtomatik",
    )

    expected_birth_date: Optional[date] = Field(
        None,
        description="Kutilgan tug'ilish. Bo'sh = mating_date + gestation_days",
    )

    veterinarian: Optional[str] = Field(None, max_length=200)
    notes:        Optional[str] = Field(None, max_length=2000)

    @model_validator(mode="after")
    def resolve_and_validate(self) -> "BreedingRecordCreate":
        # Resolve dam_id → mother_id
        if self.mother_id is None and self.dam_id is not None:
            self.mother_id = self.dam_id
        if self.mother_id is None:
            raise ValueError("'mother_id' yoki 'dam_id' maydoni talab qilinadi")
        # Resolve sire_id → father_id
        if self.father_id is None and self.sire_id is not None:
            self.father_id = self.sire_id
        # Resolve breeding_date → mating_date
        if self.mating_date is None and self.breeding_date is not None:
            self.mating_date = self.breeding_date
        if self.mating_date is None:
            raise ValueError("'mating_date' yoki 'breeding_date' maydoni talab qilinadi")
        if self.mating_date > date.today():
            raise ValueError("Juftlashish sanasi kelajakda bo'lishi mumkin emas")
        # Resolve method → mating_method
        if self.mating_method is None and self.method is not None:
            try:
                self.mating_method = MatingMethod(self.method)
            except ValueError:
                self.mating_method = MatingMethod.NATURAL
        if self.mating_method is None:
            self.mating_method = MatingMethod.NATURAL
        # AI metodda sire_id ixtiyoriy
        method_val = self.mating_method.value if self.mating_method else ""
        if "artificial" not in method_val:
            if not self.father_id and not self.external_sire_tag:
                raise ValueError(
                    "Ota jonivor ko'rsatilishi shart: "
                    "father_id/sire_id (ichki) yoki external_sire_tag (tashqi) dan biri."
                )
        if self.father_id and self.father_id == self.mother_id:
            raise ValueError("Ona va ota bir xil jonivor bo'lishi mumkin emas")
        return self


# =============================================================================
# BREEDING RECORD — UPDATE
# =============================================================================

class BreedingRecordUpdate(BaseModel):
    """PATCH — faqat berilgan maydonlar yangilanadi."""
    mating_method:       Optional[MatingMethod]        = None
    expected_birth_date: Optional[date]                = None
    veterinarian:        Optional[str]                 = Field(None, max_length=200)
    notes:               Optional[str]                 = Field(None, max_length=2000)
    external_sire_tag:   Optional[str]                 = Field(None, max_length=100)
    external_sire_breed: Optional[str]                 = Field(None, max_length=100)
    external_sire_farm:  Optional[str]                 = Field(None, max_length=200)


# =============================================================================
# CONFIRM PREGNANCY
# =============================================================================

class BreedingConfirmPregnancy(BaseModel):
    """POST /breeding/records/{id}/confirm-pregnancy"""
    confirmed_at:    date                          = Field(default_factory=date.today)
    check_method:    PregnancyCheckMethod          = PregnancyCheckMethod.ULTRASOUND
    check_notes:     Optional[str]                 = Field(None, max_length=500)
    expected_birth_date: Optional[date]            = None  # Override if needed

    @field_validator("confirmed_at")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Tasdiqlash sanasi kelajakda bo'lishi mumkin emas")
        return v


# =============================================================================
# RECORD BIRTH
# =============================================================================

class BreedingRecordBirth(BaseModel):
    """POST /breeding/records/{id}/record-birth — Tug'ilishni qayd etish."""
    actual_birth_date:   date                  = Field(default_factory=date.today)
    offspring:           List[OffspringCreate] = Field(
        ..., min_length=1, max_length=10,
        description="Har bir tug'ilgan jonivor uchun alohida yozuv",
    )
    birth_complications: Optional[str]         = Field(None, max_length=500)
    notes:               Optional[str]         = Field(None, max_length=1000)

    @field_validator("actual_birth_date")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Tug'ilish sanasi kelajakda bo'lishi mumkin emas")
        return v

    @model_validator(mode="after")
    def validate_birth_orders_unique(self) -> "BreedingRecordBirth":
        orders = [o.birth_order for o in self.offspring]
        if len(orders) != len(set(orders)):
            raise ValueError("Tug'ilish tartibi (birth_order) takrorlanmasligi kerak")
        return self


# =============================================================================
# MARK FAILED / ABORTED
# =============================================================================

class BreedingMarkFailed(BaseModel):
    """POST /breeding/records/{id}/mark-failed"""
    reason: Optional[str] = Field(None, max_length=300)


class BreedingMarkAborted(BaseModel):
    """POST /breeding/records/{id}/mark-aborted"""
    abort_date:   date            = Field(default_factory=date.today)
    abort_reason: Optional[str]   = Field(None, max_length=300)

    @field_validator("abort_date")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Abort sanasi kelajakda bo'lishi mumkin emas")
        return v


# =============================================================================
# LINK OFFSPRING TO ANIMAL
# =============================================================================

class OffspringLinkAnimal(BaseModel):
    """POST /breeding/offspring/{id}/link-animal — Nashl ni ro'yxatdagi hayvonga bog'lash"""
    animal_id: int = Field(..., gt=0)


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class AnimalBrief(BaseModel):
    """Javoblarda jonivor haqida qisqa ma'lumot."""
    model_config = ConfigDict(from_attributes=True)

    id:      int
    tag_id:  str
    species: str
    breed:   Optional[str]
    gender:  str
    status:  str


class BreedingRecordResponse(BaseModel):
    """To'liq breeding record javobi."""
    model_config = ConfigDict(from_attributes=True)

    id:         int
    farm_id:    Optional[int]
    mother_id:  int
    father_id:  Optional[int]

    external_sire_tag:   Optional[str]
    external_sire_breed: Optional[str]
    external_sire_farm:  Optional[str]

    mating_date:   date
    mating_method: MatingMethod
    status:        BreedingStatus
    gestation_days: int

    expected_birth_date:    Optional[date]
    pregnancy_confirmed_at: Optional[date]
    pregnancy_check_method: Optional[PregnancyCheckMethod]
    pregnancy_check_notes:  Optional[str]

    actual_birth_date:   Optional[date]
    live_offspring_count: int
    stillborn_count:      int
    birth_complications:  Optional[str]

    abort_date:   Optional[date]
    abort_reason: Optional[str]

    veterinarian: Optional[str]
    notes:        Optional[str]
    created_by_id: Optional[int]

    created_at: datetime
    updated_at: datetime

    # Computed
    pregnancy_progress_pct: Optional[float] = None
    days_until_birth:       Optional[int]   = None
    is_overdue:             bool            = False
    total_offspring:        int             = 0
    sire_label:             str             = ""

    # Embedded objects
    mother: Optional[AnimalBrief]         = None
    father: Optional[AnimalBrief]         = None
    offspring: List[OffspringResponse]    = []


class BreedingRecordList(BaseModel):
    """Sahifalangan ro'yxat."""
    total:   int
    page:    int
    size:    int
    pages:   int
    items:   List[BreedingRecordResponse]


# =============================================================================
# GENEALOGY (SHAJARA)
# =============================================================================

class GenealogyNode(BaseModel):
    """
    Shajara daraxti uchi — rekursiv tuzilma.

    MISOL (3 avlod):
        animal
        ├── mother
        │   ├── mother.mother (ona-buvi)
        │   └── mother.father (ona-bobo)
        └── father
            ├── father.mother
            └── father.father
    """
    animal_id:  Optional[int]
    tag_id:     Optional[str]
    species:    Optional[str]
    breed:      Optional[str]
    gender:     Optional[str]
    birth_date: Optional[date]
    is_external: bool = False        # Tashqi ota (farm ichida yo'q)
    external_label: Optional[str] = None

    mother: Optional["GenealogyNode"] = None
    father: Optional["GenealogyNode"] = None

    # Computed: necha avlod chuqur
    generation: int = 0

    model_config = ConfigDict(from_attributes=True)


GenealogyNode.model_rebuild()  # Rekursiv model uchun


# =============================================================================
# STATS
# =============================================================================

class BreedingStats(BaseModel):
    """GET /breeding/stats — Nasl statistikasi."""
    total_records:          int
    active_pregnancies:     int      # CONFIRMED_PREGNANT holati
    planned:                int
    birthed_this_year:      int
    failed_this_year:       int
    aborted_this_year:      int

    total_live_offspring:   int
    total_stillborn:        int
    avg_litter_size:        float    # O'rtacha nasl soni
    stillbirth_rate_pct:    float    # Foizda

    overdue_count:          int      # Kutilgan sanadan o'tib ketganlar
    due_next_7_days:        int      # Kelgusi 7 kunda
    due_next_30_days:       int      # Kelgusi 30 kunda

    most_active_mother_tag: Optional[str]
    most_used_sire_tag:     Optional[str]

    by_mating_method: dict[str, int]   # {"natural": 10, "ai": 5}
    by_species:       dict[str, int]   # {"cattle": 8, "sheep": 3}
    monthly_births:   List[dict]       # [{"month": "2026-01", "count": 3}]


# =============================================================================
# BREEDING RECOMMENDATION
# =============================================================================

class BreedingRecommendation(BaseModel):
    """
    AI tomonidan tavsiya etilgan juft.

    BALL HISOBLASH (100 dan):
        genetic_diversity_score  — Yaqin qarindosh emaslik (40 ball)
        adi_compatibility_score  — ADI ko'rsatkichlari mos kelishi (30 ball)
        weight_compatibility_score — Vazn farqi optimal (20 ball)
        breed_compatibility_score  — Zot uyg'unligi (10 ball)
    """
    mother:                  AnimalBrief
    sire_animal:             Optional[AnimalBrief]  # Farm ichidagi ota
    sire_external_label:     Optional[str]          # Agar tashqi

    total_score:             float   # 0-100
    genetic_diversity_score: float   # 0-40
    adi_compatibility_score: float   # 0-30
    weight_compatibility_score: float  # 0-20
    breed_compatibility_score:  float  # 0-10

    recommendation_reason: str    # Inson tili bilan izoh
    warnings:              List[str]  # Ogohlantirishlar (agar COI yuqori bo'lsa)

    estimated_gestation_days: int
    expected_birth_range_start: date
    expected_birth_range_end:   date   # ±7 kun

    class Config:
        from_attributes = True


class BreedingRecommendationList(BaseModel):
    total_females_eligible: int
    total_sires_available:  int
    recommendations:        List[BreedingRecommendation]
    generated_at:           datetime