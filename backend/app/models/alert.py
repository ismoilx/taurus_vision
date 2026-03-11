"""
Taurus Vision — Alert Model

Farm monitoring tizimidagi barcha ogohlantirishlar.
Alert lifecycle: OPEN → SEEN → RESOLVED | DISMISSED

SPRINT 17-18 O'ZGARISH:
    AlertType ga SENSOR_OFFLINE qo'shildi — offline qurilmalar uchun.
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, ForeignKey, Index, Boolean
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AlertType(str, enum.Enum):
    # Jonivor holati
    ANIMAL_MISSING         = "animal_missing"
    ANIMAL_MISSING_LONG    = "animal_missing_long"
    HEALTH_ANOMALY         = "health_anomaly"
    WEIGHT_LOSS            = "weight_loss"
    GROWTH_STAGNATION      = "growth_stagnation"

    # ADI asosida
    ADI_CRITICAL           = "adi_critical"
    ADI_RAPID_DECLINE      = "adi_rapid_decline"
    ADI_SHARP_DROP         = "adi_sharp_drop"
    ADI_WARNING            = "adi_warning"
    FEEDING_PROBLEM        = "feeding_problem"
    FEEDING_STOPPED        = "feeding_stopped"

    # Kamera / tizim
    CAMERA_OFFLINE         = "camera_offline"
    DETECTION_STOPPED      = "detection_stopped"

    # Sprint 17-18: IoT sensor
    SENSOR_OFFLINE         = "sensor_offline"
    SENSOR_ANOMALY         = "sensor_anomaly"
    HIGH_TEMPERATURE       = "high_temperature"
    LOW_HEART_RATE         = "low_heart_rate"
    HIGH_HEART_RATE        = "high_heart_rate"

    # Boshqa
    SYSTEM_ERROR           = "system_error"
    CUSTOM                 = "custom"


class AlertSeverity(str, enum.Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    OPEN      = "open"
    SEEN      = "seen"
    RESOLVED  = "resolved"
    DISMISSED = "dismissed"


class Alert(BaseModel):
    """
    Farm monitoring alert.

    Har bir alert bitta hodisani ifodalaydi.
    Bir xil turdagi alert deduplication bilan boshqariladi —
    AlertService._ensure_alert() qayta yaratmaydi.
    """

    __tablename__ = "alerts"

    # ------------------------------------------------------------------ #
    # Foreign Keys                                                         #
    # ------------------------------------------------------------------ #

    animal_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("animals.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    camera_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cameras.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ------------------------------------------------------------------ #
    # Alert Info                                                           #
    # ------------------------------------------------------------------ #

    alert_type: Mapped[AlertType] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    severity: Mapped[AlertSeverity] = mapped_column(
        String(20),
        nullable=False,
        default=AlertSeverity.MEDIUM,
        index=True,
    )

    status: Mapped[AlertStatus] = mapped_column(
        String(20),
        nullable=False,
        default=AlertStatus.OPEN,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # ------------------------------------------------------------------ #
    # Timestamps                                                           #
    # ------------------------------------------------------------------ #

    triggered_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Alert birinchi marta yaratilgan vaqt",
    )

    seen_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )

    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )

    # ------------------------------------------------------------------ #
    # Extra Data                                                           #
    # ------------------------------------------------------------------ #

    context: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Alert konteksti: device_id, scores, thresholds va boshqalar",
    )

    resolved_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Kim tomonidan hal qilindi",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Hal qiluvchi izohi",
    )

    auto_generated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="AI yoki tizim tomonidan avtomatik yaratilganmi",
    )

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #

    animal: Mapped[Optional["Animal"]] = relationship(  # type: ignore[name-defined]
        "Animal",
        back_populates="alerts",
        lazy="noload",
    )

    # ------------------------------------------------------------------ #
    # Table Constraints                                                    #
    # ------------------------------------------------------------------ #

    __table_args__ = (
        Index("ix_alerts_animal_type_status", "animal_id", "alert_type", "status"),
        Index("ix_alerts_triggered_severity", "triggered_at", "severity"),
    )

    def __repr__(self) -> str:
        return (
            f"<Alert("
            f"id={self.id}, "
            f"type={self.alert_type}, "
            f"severity={self.severity}, "
            f"status={self.status}"
            f")>"
        )

    @property
    def is_open(self) -> bool:
        return self.status in (AlertStatus.OPEN, AlertStatus.SEEN)

    @property
    def is_critical(self) -> bool:
        return self.severity == AlertSeverity.CRITICAL

    @property
    def resolution_note(self) -> Optional[str]:
        """Backward-compatibility alias for `notes` field."""
        return self.notes

    def resolve(
        self,
        resolved_by: Optional[str] = None,
        resolved_by_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> None:
        """Alertni RESOLVED holatiga o'tkazish helper metodi."""
        from datetime import datetime
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.utcnow()
        # Support both old (resolved_by_id: int) and new (resolved_by: str) callers
        if resolved_by_id is not None:
            self.resolved_by = resolved_by_id
        if note is not None:
            self.notes = note

    @property
    def duration_minutes(self) -> Optional[float]:
        """Alert yaratilganidan beri o'tgan daqiqalar soni."""
        if self.triggered_at is None:
            return None
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        # triggered_at timezone-naive bo'lsa, UTC deb qabul qilamiz
        triggered = self.triggered_at
        if triggered.tzinfo is None:
            triggered = triggered.replace(tzinfo=timezone.utc)
        delta = now - triggered
        return round(delta.total_seconds() / 60, 2)

# =============================================================================
# SEVERITY MAP — alert_service.py tomonidan ishlatiladi
# =============================================================================

ALERT_SEVERITY_MAP: dict[str, AlertSeverity] = {
    "low":      AlertSeverity.LOW,
    "medium":   AlertSeverity.MEDIUM,
    "high":     AlertSeverity.HIGH,
    "critical": AlertSeverity.CRITICAL,
}