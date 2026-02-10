# """
# Database models package.

# This module exports all database models and related types.
# Import models from here: from app.models import Animal, AnimalStatus, etc.
# """

# from app.models.base import Base, BaseModel, TimestampMixin, SoftDeleteMixin
# from app.models.animal import (
#     Animal,
#     AnimalSpecies,
#     AnimalGender,
#     AnimalStatus,
# )

# # Export all models for Alembic autogenerate
# __all__ = [
#     # Base classes
#     "Base",
#     "BaseModel",
#     "TimestampMixin",
#     "SoftDeleteMixin",
#     # Animal
#     "Animal",
#     "AnimalSpecies",
#     "AnimalGender",
#     "AnimalStatus",
# ]
########################################################################################
# Claude yangiladi
"""
Database models package.

This module exports all database models and related types.
Import models from here: from app.models import Animal, AnimalStatus, etc.
"""

from app.models.base import Base, BaseModel, TimestampMixin, SoftDeleteMixin
from app.models.animal import (
    Animal,
    AnimalSpecies,
    AnimalGender,
    AnimalStatus,
)
from app.models.weight_measurement import WeightMeasurement

# Export all models for Alembic autogenerate
__all__ = [
    # Base classes
    "Base",
    "BaseModel",
    "TimestampMixin",
    "SoftDeleteMixin",
    # Animal
    "Animal",
    "AnimalSpecies",
    "AnimalGender",
    "AnimalStatus",
    # Weight Measurement
    "WeightMeasurement",
]