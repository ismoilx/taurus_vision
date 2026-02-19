"""
Pydantic schemas for Animal API.
Production-ready version with robust datetime validation and normalization.
"""

from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models.animal import AnimalSpecies, AnimalGender, AnimalStatus


def ensure_naive_utc(v: Any) -> Any:
    """
    Vaqtni solishtirishda xatolik chiqmasligi uchun uni 'naive' holatga keltiradi.
    """
    if isinstance(v, datetime) and v.tzinfo is not None:
        return v.astimezone(timezone.utc).replace(tzinfo=None)
    return v


class AnimalBase(BaseModel):
    """Barcha hayvon sxemalari uchun asosiy model."""
    
    tag_id: str = Field(
        ..., min_length=3, max_length=50,
        description="Unique identifier (JNV-001)",
        examples=["JNV-001"]
    )
    species: AnimalSpecies = Field(..., description="Animal species type")
    breed: Optional[str] = Field(None, max_length=100)
    gender: AnimalGender = Field(default=AnimalGender.UNKNOWN)
    birth_date: Optional[datetime] = Field(None)
    acquisition_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    status: AnimalStatus = Field(default=AnimalStatus.ACTIVE)
    notes: Optional[str] = Field(None, max_length=1000)

    # REUSABLE VALIDATORS
    @field_validator("tag_id", mode="before")
    @classmethod
    def validate_tag_id(cls, v: Any) -> Any:
        """Tag IDni tozalash va formatini tekshirish."""
        if not isinstance(v, str):
            return v
        
        v = v.strip().upper()
        if not all(c.isalnum() or c == '-' for c in v):
            raise ValueError("Tag ID faqat harf, raqam va chiziqchadan iborat bo'lishi kerak")
        return v

    @field_validator("birth_date", "acquisition_date")
    @classmethod
    def validate_dates(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Kelajakdagi sanani kiritishni taqiqlash."""
        if v is not None:
            v_naive = ensure_naive_utc(v)
            now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            
            if v_naive > now_naive:
                raise ValueError("Sana kelajakda bo'lishi mumkin emas")
            return v_naive
        return v


class AnimalCreate(AnimalBase):
    """Hayvon yaratish uchun sxema."""
    pass


class AnimalUpdate(BaseModel):
    """Hayvonni yangilash uchun sxema (Hamma maydonlar optional)."""
    tag_id: Optional[str] = Field(None, min_length=3, max_length=50)
    species: Optional[AnimalSpecies] = None
    breed: Optional[str] = None
    gender: Optional[AnimalGender] = None
    birth_date: Optional[datetime] = None
    acquisition_date: Optional[datetime] = None
    status: Optional[AnimalStatus] = None
    notes: Optional[str] = None

    # Reusable validatorlarni V2 usulida bog'laymiz
    @field_validator("tag_id", mode="before")
    @classmethod
    def _validate_tag(cls, v: Any) -> Any:
        return AnimalBase.validate_tag_id(v)

    @field_validator("birth_date", "acquisition_date")
    @classmethod
    def _validate_dates(cls, v: Optional[datetime]) -> Optional[datetime]:
        return AnimalBase.validate_dates(v)


class AnimalResponse(AnimalBase):
    """API javobi uchun sxema (Bazadagi barcha maydonlar bilan)."""
    id: int
    first_detected_at: Optional[datetime] = None
    last_detected_at: Optional[datetime] = None
    total_detections: int = 0
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "birth_date", "acquisition_date", "created_at", "updated_at", 
        "first_detected_at", "last_detected_at", mode="before"
    )
    @classmethod
    def _normalize_dates(cls, v: Any) -> Any:
        return ensure_naive_utc(v)

    model_config = ConfigDict(from_attributes=True)


class AnimalListResponse(BaseModel):
    """Sahifalangan ro'yxat uchun javob sxemasi."""
    items: list[AnimalResponse]
    total: int
    skip: int
    limit: int