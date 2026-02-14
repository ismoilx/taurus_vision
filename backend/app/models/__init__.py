"""
Database models package.

Import all models from here so Alembic autogenerate picks them up.

Usage:
    from app.models import Animal, AnimalStatus
    from app.models import WeightMeasurement
    from app.models import Detection
"""

from app.models.base import Base, BaseModel, TimestampMixin, SoftDeleteMixin
from app.models.animal import (
    Animal,
    AnimalSpecies,
    AnimalGender,
    AnimalStatus,
)
from app.models.weight_measurement import WeightMeasurement
from app.models.detection import Detection

__all__ = [
    # Base
    "Base",
    "BaseModel",
    "TimestampMixin",
    "SoftDeleteMixin",
    # Animal
    "Animal",
    "AnimalSpecies",
    "AnimalGender",
    "AnimalStatus",
    # Measurements
    "WeightMeasurement",
    # Detections
    "Detection",
]