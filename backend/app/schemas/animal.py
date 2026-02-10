# """
# Pydantic schemas for Animal API.

# These schemas define the shape of data for:
# - Request validation (what users send)
# - Response serialization (what users receive)
# - Data transformation and validation rules
# """

# from datetime import datetime, timezone
# from typing import Optional
# from pydantic import BaseModel, Field, field_validator, ConfigDict

# from app.models.animal import AnimalSpecies, AnimalGender, AnimalStatus


# class AnimalBase(BaseModel):
#     """
#     Base schema with common animal fields.
    
#     Other schemas inherit from this to avoid repetition.
#     """
    
#     tag_id: str = Field(
#         ...,
#         min_length=3,
#         max_length=50,
#         description="Unique tag identifier (e.g., JNV-001)",
#         examples=["JNV-001", "CATTLE-042"],
#     )
    
#     species: AnimalSpecies = Field(
#         ...,
#         description="Animal species type",
#     )
    
#     breed: Optional[str] = Field(
#         None,
#         max_length=100,
#         description="Specific breed name",
#         examples=["Holstein", "Angus", "Merino"],
#     )
    
#     gender: AnimalGender = Field(
#         default=AnimalGender.UNKNOWN,
#         description="Gender classification",
#     )
    
#     birth_date: Optional[datetime] = Field(
#         None,
#         description="Date of birth (if known)",
#     )
    
#     acquisition_date: datetime = Field(
#         default_factory=datetime.utcnow,
#         description="Date when animal was acquired/added to farm",
#     )
    
#     status: AnimalStatus = Field(
#         default=AnimalStatus.ACTIVE,
#         description="Current lifecycle status",
#     )
    
#     notes: Optional[str] = Field(
#         None,
#         max_length=1000,
#         description="Additional notes or observations",
#     )
    
#     # VALIDATION RULES
    
#     @field_validator("tag_id")
#     @classmethod
#     def validate_tag_id(cls, v: str) -> str:
#         """
#         Validate and normalize tag_id.
        
#         BUSINESS RULE: Tag IDs are always stored in uppercase for consistency.
        
#         Args:
#             v: Raw tag_id value
            
#         Returns:
#             Uppercase tag_id
            
#         Raises:
#             ValueError: If tag_id contains invalid characters
#         """
#         # Convert to uppercase
#         v = v.strip().upper()
        
#         # Check for invalid characters (only alphanumeric and dash allowed)
#         if not all(c.isalnum() or c == '-' for c in v):
#             raise ValueError(
#                 "Tag ID can only contain letters, numbers, and dashes"
#             )
        
#         return v
    
#     @field_validator("birth_date")
#     @classmethod
#     def validate_birth_date(cls, v: Optional[datetime]) -> Optional[datetime]:
#         """
#         Validate birth date.
        
#         BUSINESS RULE: Birth date cannot be in the future.
        
#         Args:
#             v: Birth date value
            
#         Returns:
#             Validated birth date
            
#         Raises:
#             ValueError: If birth date is in the future
#         """
#         if v is not None and v > datetime.now(timezone.utc):
#             raise ValueError(
#                 "Birth date cannot be in the future"
#             )
        
#         return v
    
#     @field_validator("acquisition_date")
#     @classmethod
#     def validate_acquisition_date(cls, v: datetime) -> datetime:
#         """
#         Validate acquisition date.
        
#         BUSINESS RULE: Acquisition date cannot be in the future.
        
#         Args:
#             v: Acquisition date value
            
#         Returns:
#             Validated acquisition date
            
#         Raises:
#             ValueError: If acquisition date is in the future
#         """
#         if v > datetime.now(timezone.utc):
#             raise ValueError(
#                 "Acquisition date cannot be in the future"
#             )
        
#         return v


# class AnimalCreate(AnimalBase):
#     """
#     Schema for creating a new animal.
    
#     Inherits all fields from AnimalBase.
#     Used for POST /animals endpoint.
    
#     Example:
#         {
#             "tag_id": "jnv-001",  # Will be converted to "JNV-001"
#             "species": "cattle",
#             "breed": "Holstein",
#             "gender": "female",
#             "birth_date": "2023-01-15T00:00:00Z",
#             "acquisition_date": "2024-01-01T00:00:00Z"
#         }
#     """
#     pass


# class AnimalUpdate(BaseModel):
#     """
#     Schema for updating an existing animal.
    
#     All fields are optional (partial update).
#     Used for PATCH /animals/{id} endpoint.
    
#     BUSINESS RULE: Animals with status SOLD or DECEASED cannot be updated
#     (enforced in service layer).
    
#     Example:
#         {
#             "breed": "Updated breed",
#             "notes": "New observation"
#         }
#     """
    
#     tag_id: Optional[str] = Field(
#         None,
#         min_length=3,
#         max_length=50,
#     )
    
#     species: Optional[AnimalSpecies] = None
#     breed: Optional[str] = Field(None, max_length=100)
#     gender: Optional[AnimalGender] = None
#     birth_date: Optional[datetime] = None
#     acquisition_date: Optional[datetime] = None
#     status: Optional[AnimalStatus] = None
#     notes: Optional[str] = Field(None, max_length=1000)
    
#     # Same validators as AnimalBase
    
#     @field_validator("tag_id")
#     @classmethod
#     def validate_tag_id(cls, v: Optional[str]) -> Optional[str]:
#         """Uppercase normalization."""
#         if v is not None:
#             v = v.strip().upper()
#             if not all(c.isalnum() or c == '-' for c in v):
#                 raise ValueError(
#                     "Tag ID can only contain letters, numbers, and dashes"
#                 )
#         return v
    
#     @field_validator("birth_date")
#     @classmethod
#     def validate_birth_date(cls, v: Optional[datetime]) -> Optional[datetime]:
#         """Birth date cannot be in the future."""
#         if v is not None and v > datetime.now(timezone.utc):
#             raise ValueError("Birth date cannot be in the future")
#         return v
    
#     @field_validator("acquisition_date")
#     @classmethod
#     def validate_acquisition_date(cls, v: Optional[datetime]) -> Optional[datetime]:
#         """Acquisition date cannot be in the future."""
#         if v is not None and v > datetime.now(timezone.utc):
#             raise ValueError("Acquisition date cannot be in the future")
#         return v


# class AnimalResponse(AnimalBase):
#     """
#     Schema for animal API responses.
    
#     Includes all fields from database (including auto-generated ones).
#     Used for all GET endpoints and successful POST/PATCH responses.
    
#     Example:
#         {
#             "id": 1,
#             "tag_id": "JNV-001",
#             "species": "cattle",
#             "breed": "Holstein",
#             "gender": "female",
#             "birth_date": "2023-01-15T00:00:00Z",
#             "acquisition_date": "2024-01-01T00:00:00Z",
#             "status": "active",
#             "first_detected_at": null,
#             "last_detected_at": null,
#             "total_detections": 0,
#             "notes": null,
#             "created_at": "2026-02-10T10:00:00Z",
#             "updated_at": "2026-02-10T10:00:00Z"
#         }
#     """
    
#     # Database-generated fields
#     id: int = Field(..., description="Primary key")
    
#     first_detected_at: Optional[datetime] = Field(
#         None,
#         description="First time detected by camera system",
#     )
    
#     last_detected_at: Optional[datetime] = Field(
#         None,
#         description="Most recent detection timestamp",
#     )
    
#     total_detections: int = Field(
#         0,
#         description="Total number of times detected",
#     )
    
#     created_at: datetime = Field(
#         ...,
#         description="Timestamp when record was created",
#     )
    
#     updated_at: datetime = Field(
#         ...,
#         description="Timestamp when record was last updated",
#     )
    
#     # Pydantic v2 config
#     model_config = ConfigDict(
#         from_attributes=True,  # Allow creating from ORM models
#         json_schema_extra={
#             "example": {
#                 "id": 1,
#                 "tag_id": "JNV-001",
#                 "species": "cattle",
#                 "breed": "Holstein",
#                 "gender": "female",
#                 "birth_date": "2023-01-15T00:00:00Z",
#                 "acquisition_date": "2024-01-01T00:00:00Z",
#                 "status": "active",
#                 "first_detected_at": None,
#                 "last_detected_at": None,
#                 "total_detections": 0,
#                 "notes": None,
#                 "created_at": "2026-02-10T10:00:00Z",
#                 "updated_at": "2026-02-10T10:00:00Z",
#             }
#         },
#     )


# class AnimalListResponse(BaseModel):
#     """
#     Schema for paginated list of animals.
    
#     Used for GET /animals endpoint.
    
#     Example:
#         {
#             "items": [...],
#             "total": 42,
#             "skip": 0,
#             "limit": 10
#         }
#     """
    
#     items: list[AnimalResponse] = Field(
#         ...,
#         description="List of animals",
#     )
    
#     total: int = Field(
#         ...,
#         description="Total number of animals (ignoring pagination)",
#     )
    
#     skip: int = Field(
#         0,
#         description="Number of items skipped",
#     )
    
#     limit: int = Field(
#         10,
#         description="Maximum number of items returned",
#     )
    
#     model_config = ConfigDict(
#         json_schema_extra={
#             "example": {
#                 "items": [
#                     {
#                         "id": 1,
#                         "tag_id": "JNV-001",
#                         "species": "cattle",
#                         "status": "active",
#                     }
#                 ],
#                 "total": 42,
#                 "skip": 0,
#                 "limit": 10,
#             }
#         },
#     )

###########################################################
#Gemini tavfsiya qildi 10/02/2026
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
    Bu funksiya ham kiritilayotgan, ham bazadan olinayotgan ma'lumotlar uchun ishlaydi.
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
    @field_validator("tag_id")
    @classmethod
    def validate_tag_id(cls, v: str) -> str:
        v = v.strip().upper()
        if not all(c.isalnum() or c == '-' for c in v):
            raise ValueError("Tag ID faqat harf, raqam va chiziqchadan iborat bo'lishi kerak")
        return v

    @field_validator("birth_date", "acquisition_date")
    @classmethod
    def validate_dates(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Kelajakdagi sanani kiritishni taqiqlash (Naive-safe comparison)."""
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

    # Base modeldagi validatorlarni bu yerga ham bog'laymiz
    _validate_tag = field_validator("tag_id")(AnimalBase.validate_tag_id)
    _validate_dates = field_validator("birth_date", "acquisition_date")(AnimalBase.validate_dates)


class AnimalResponse(AnimalBase):
    """API javobi uchun sxema (Bazadagi barcha maydonlar bilan)."""
    id: int
    first_detected_at: Optional[datetime] = None
    last_detected_at: Optional[datetime] = None
    total_detections: int = 0
    created_at: datetime
    updated_at: datetime

    # Bazadan o'qiyotganda ham vaqtni normallashtiramiz
    _normalize_dates = field_validator(
        "birth_date", "acquisition_date", "created_at", "updated_at", 
        "first_detected_at", "last_detected_at", mode="before"
    )(ensure_naive_utc)

    model_config = ConfigDict(from_attributes=True)


class AnimalListResponse(BaseModel):
    """Sahifalangan ro'yxat uchun javob sxemasi."""
    items: list[AnimalResponse]
    total: int
    skip: int
    limit: int