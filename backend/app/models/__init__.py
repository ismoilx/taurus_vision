"""
Taurus Vision — Database Models Package

Barcha modellarni shu yerdan import qilish.
Bu circular import muammosini oldini oladi va
alembic auto-generation uchun barcha modellar
bir joyda ko'rinishini ta'minlaydi.
"""

from app.models.base             import BaseModel
from app.models.user             import User, UserRole
from app.models.camera           import Camera, CameraType
from app.models.animal           import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.detection        import Detection
from app.models.animal_embedding import AnimalEmbedding
from app.models.weight_measurement import WeightMeasurement
from app.models.health_record    import HealthRecord
from app.models.adi_log          import ADILog, ADICategory
from app.models.alert            import Alert, AlertType, AlertSeverity, AlertStatus
from app.models.health_prediction import HealthPrediction, RiskLevel
from app.models.audit_log        import AuditLog, AuditEventType, AuditSeverity

__all__ = [
    # Base
    "BaseModel",
    # Auth
    "User",
    "UserRole",
    # Cameras
    "Camera",
    "CameraType",
    # Animals
    "Animal",
    "AnimalSpecies",
    "AnimalGender",
    "AnimalStatus",
    # Monitoring
    "Detection",
    "AnimalEmbedding",
    "WeightMeasurement",
    "HealthRecord",
    # ADI
    "ADILog",
    "ADICategory",
    # Alerts
    "Alert",
    "AlertType",
    "AlertSeverity",
    "AlertStatus",
    # Health Predictions
    "HealthPrediction",
    "RiskLevel",
    # Security Audit
    "AuditLog",
    "AuditEventType",
    "AuditSeverity",
]