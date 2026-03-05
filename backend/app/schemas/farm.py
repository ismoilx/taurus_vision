"""
Taurus Vision — Farm Pydantic Schemas

Request/Response uchun validatsiya va serializatsiya.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# BASE
# =============================================================================

class FarmBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, description="Ferma nomi")
    description: Optional[str] = Field(None, max_length=2000)
    location: Optional[str] = Field(None, max_length=300)
    owner_name: Optional[str] = Field(None, max_length=150)
    phone: Optional[str] = Field(None, max_length=30)
    timezone_offset: int = Field(5, ge=-12, le=14, description="UTC offset soatda")


# =============================================================================
# CREATE
# =============================================================================

class FarmCreate(FarmBase):
    pass


# =============================================================================
# UPDATE
# =============================================================================

class FarmUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    location: Optional[str] = Field(None, max_length=300)
    owner_name: Optional[str] = Field(None, max_length=150)
    phone: Optional[str] = Field(None, max_length=30)
    timezone_offset: Optional[int] = Field(None, ge=-12, le=14)
    is_active: Optional[bool] = None


# =============================================================================
# RESPONSE
# =============================================================================

class FarmResponse(FarmBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Statistika (servis tomonidan qo'shiladi)
    animal_count: Optional[int] = None
    active_animal_count: Optional[int] = None


# =============================================================================
# LIST RESPONSE
# =============================================================================

class FarmListResponse(BaseModel):
    items: list[FarmResponse]
    total: int


# =============================================================================
# SWITCH RESPONSE
# =============================================================================

class FarmSwitchResponse(BaseModel):
    message: str
    farm_id: int
    farm_name: str