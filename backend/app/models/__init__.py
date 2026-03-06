"""
Taurus Vision — Database Models Package

Barcha modellarni shu yerdan import qilish.
Bu circular import muammosini oldini oladi va
alembic auto-generation uchun barcha modellar
bir joyda ko'rinishini ta'minlaydi.
"""

from app.models.base             import BaseModel
from app.models.farm             import Farm
from app.models.user             import User, UserRole
from app.models.camera           import Camera, CameraType
from app.models.animal           import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.animal_photo     import AnimalPhoto
from app.models.detection        import Detection
from app.models.animal_embedding import AnimalEmbedding
from app.models.scale            import Scale, ScaleType, ScaleStatus
from app.models.weight_measurement import WeightMeasurement, WeightSource
from app.models.health_record    import HealthRecord
from app.models.adi_log          import ADILog, ADICategory
from app.models.alert            import Alert, AlertType, AlertSeverity, AlertStatus
from app.models.health_prediction import HealthPrediction, RiskLevel
from app.models.audit_log        import AuditLog, AuditEventType, AuditSeverity
from app.models.sensor_reading   import SensorReading
from app.models.farm_task        import FarmTask, TaskType, TaskPriority, TaskStatus
from app.models.feed             import FeedStock, FeedRecord, FeedType, FeedUnit
from app.models.training_run     import TrainingRun, TrainingStatus  # ✅ TUZATILDI
from app.models.integration      import (                             # Q5 Integration Module
    APIKey,
    Webhook,
    APIKeyScope,
    WebhookEvent,
)
from app.models.finance          import (                             # Q4 Finance Module
    FinanceTransaction,
    TransactionType,
    ExpenseCategory,
    IncomeCategory,
    PaymentMethod,
)
from app.models.breeding         import (                             # Sprint 25-26 — Nasl va Zotchilik
    BreedingRecord,
    OffspringRecord,
    MatingMethod,
    BreedingStatus,
    PregnancyCheckMethod,
    OffspringOutcome,
    GESTATION_DAYS,
)

__all__ = [
    # Base
    "BaseModel",
    # Farms
    "Farm",
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
    "AnimalPhoto",
    # Scales (Q7)
    "Scale",
    "ScaleType",
    "ScaleStatus",
    "WeightSource",
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
    # IoT Sensors
    "SensorReading",
    # Farm Tasks
    "FarmTask",
    "TaskType",
    "TaskPriority",
    "TaskStatus",
    # Feed Management
    "FeedStock",
    "FeedRecord",
    "FeedType",
    "FeedUnit",
    # AI Training
    "TrainingRun",
    "TrainingStatus",
    # Finance Module (Q4)
    "FinanceTransaction",
    "TransactionType",
    "ExpenseCategory",
    "IncomeCategory",
    "PaymentMethod",
    # Integration Module (Q5)
    "APIKey",
    "Webhook",
    "APIKeyScope",
    "WebhookEvent",
    # Nasl va Zotchilik (Sprint 25-26)
    "BreedingRecord",
    "OffspringRecord",
    "MatingMethod",
    "BreedingStatus",
    "PregnancyCheckMethod",
    "OffspringOutcome",
    "GESTATION_DAYS",
]