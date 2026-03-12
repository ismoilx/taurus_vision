"""
Alert Pydantic schemas.

Alert yaratish, yangilash va qaytarish uchun
validatsiya sxemalari.
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator

from app.models.alert import AlertType, AlertSeverity, AlertStatus


# ------------------------------------------------------------------ #
# Request Schemas                                                      #
# ------------------------------------------------------------------ #

class AlertCreateManual(BaseModel):
    """
    Qo'lda alert yaratish uchun request.
    Fermer o'zi muammo sezganda ishlatadi.
    """

    animal_id:   Optional[int] = Field(None,
        description="Jonivor ID. None = umumiy ferma muammosi")
    alert_type:  AlertType     = Field(...,
        description="Alert turi")

    @field_validator("alert_type", mode="before")
    @classmethod
    def normalize_alert_type(cls, v):
        """
        'manual' → AlertType.CUSTOM konvertatsiya.
        Test kompatibilligi uchun.
        """
        if v == "manual":
            return AlertType.CUSTOM
        return v
    # String o'rniga dinamik ravishda birinchi Enum qiymatini (odatda LOW/MEDIUM) biriktiramiz.
    # Bu '.value' chaqirilganda 'str' xatolik berishining oldini oladi.
    severity:    AlertSeverity = Field(
        default_factory=lambda: list(AlertSeverity)[0],
        description="Jiddiylik darajasi"
    )
    title:       str           = Field(..., min_length=3, max_length=200)
    description: str           = Field(..., min_length=10)
    context:     Optional[dict[str, Any]] = None


class AlertResolveRequest(BaseModel):
    """Alertni hal etish uchun request."""

    resolved_by:     str            = Field(..., min_length=1, max_length=100,
        description="Hal etgan foydalanuvchi nomi")
    resolution_note: Optional[str]  = Field(None, max_length=1000,
        description="Qanday harakat qilindi")


class AlertDismissRequest(BaseModel):
    """Alertni bekor qilish uchun request."""

    dismissed_by: str           = Field(..., min_length=1, max_length=100)
    reason:       Optional[str] = Field(None, max_length=500,
        description="Nima uchun bekor qilindi")


class AlertFilterParams(BaseModel):
    """
    Alert ro'yxatini filterlash parametrlari.
    Query params sifatida ishlatiladi.
    """

    animal_id:   Optional[int]          = None
    alert_type:  Optional[AlertType]    = None
    severity:    Optional[AlertSeverity]= None
    status:      Optional[AlertStatus]  = AlertStatus.OPEN
    from_date:   Optional[datetime]     = None
    to_date:     Optional[datetime]     = None
    limit:       int                    = Field(50, ge=1, le=200)
    offset:      int                    = Field(0,  ge=0)

    @field_validator("to_date")
    @classmethod
    def validate_date_range(
        cls,
        to_date: Optional[datetime],
        info: Any,
    ) -> Optional[datetime]:
        from_date = info.data.get("from_date")
        if from_date and to_date and to_date < from_date:
            raise ValueError("to_date from_date dan katta bo'lishi kerak")
        return to_date


# ------------------------------------------------------------------ #
# Response Schemas                                                     #
# ------------------------------------------------------------------ #

class AlertResponse(BaseModel):
    """Bitta alert response sxemasi."""

    id:              int
    animal_id:       Optional[int]
    animal_tag_id:   Optional[str] = None   # JOIN orqali olinadi
    camera_id:       Optional[str]
    alert_type:      str
    severity:        str
    status:          str
    title:           str
    description:     str
    auto_generated:  bool
    triggered_at:    datetime
    seen_at:         Optional[datetime]
    resolved_at:     Optional[datetime]
    resolved_by:     Optional[str]
    resolution_note: Optional[str]
    context:         Optional[dict[str, Any]]

    # Computed
    is_open:         bool
    is_critical:     bool
    duration_minutes: Optional[float]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_tag(
        cls,
        obj: Any,
        animal_tag_id: Optional[str] = None,
    ) -> "AlertResponse":
        """Alert ORM obyektidan Response yaratish."""
        
        # Helper: Enum bo'lsa qulay o'qish, bo'lmasa o'zini qaytarish
        def _get_val(val):
            return val.value if hasattr(val, "value") else val

        return cls(
            id=obj.id,
            animal_id=obj.animal_id,
            animal_tag_id=animal_tag_id,
            camera_id=obj.camera_id,
            alert_type=_get_val(obj.alert_type),
            severity=_get_val(obj.severity),
            status=_get_val(obj.status),
            title=obj.title,
            description=obj.description,
            auto_generated=obj.auto_generated,
            triggered_at=obj.triggered_at,
            seen_at=obj.seen_at,
            resolved_at=obj.resolved_at,
            resolved_by=obj.resolved_by,
            resolution_note=obj.resolution_note,
            context=obj.context,
            is_open=obj.is_open,
            is_critical=obj.is_critical,
            duration_minutes=obj.duration_minutes,
        )


class AlertListResponse(BaseModel):
    """Filterlangan alert ro'yxati."""

    total:   int
    limit:   int
    offset:  int
    items:   list[AlertResponse]


class AlertStatsResponse(BaseModel):
    """
    Alert statistikasi — dashboard widget uchun.
    """

    total_open:     int
    critical_open:  int
    high_open:      int
    medium_open:    int
    low_open:       int
    resolved_today: int
    avg_resolution_minutes: Optional[float]