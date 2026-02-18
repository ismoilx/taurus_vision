"""
Schemas for animal muzzle registration.

Defines request/response models for the registration API endpoint.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class RegistrationResponse(BaseModel):
    """Response after successful animal registration."""
    animal_id: int
    tag_id: str
    embedding_id: int
    embedding_count: int
    message: str
    quality_score: Optional[float] = None

    model_config = {"from_attributes": True}


class IdentificationResponse(BaseModel):
    """Response for identification attempt."""
    animal_id: Optional[int]
    tag_id: Optional[str]
    similarity_score: float
    is_identified: bool
    message: str

    model_config = {"from_attributes": True}


class EmbeddingInfo(BaseModel):
    """Info about a single stored embedding."""
    id: int
    animal_id: int
    is_reference: bool
    source: str
    quality_score: Optional[float]
    photo_path: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}