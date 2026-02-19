"""
Database models package.

Barcha modellarni shu yerdan import qilish —
circular import muammosini oldini oladi.
"""

from app.models.base             import BaseModel
from app.models.animal           import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.detection        import Detection
from app.models.animal_embedding import AnimalEmbedding
from app.models.weight_measurement import WeightMeasurement
from app.models.health_record    import HealthRecord
from app.models.adi_log          import ADILog, ADICategory          # YANGI
from app.models.alert            import Alert, AlertType, AlertSeverity, AlertStatus  # YANGI

__all__ = [
    "BaseModel",
    "Animal",
    "AnimalSpecies",
    "AnimalGender",
    "AnimalStatus",
    "Detection",
    "AnimalEmbedding",
    "WeightMeasurement",
    "HealthRecord",
    "ADILog",
    "ADICategory",
    "Alert",
    "AlertType",
    "AlertSeverity",
    "AlertStatus",
]
