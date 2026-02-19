"""
Alert Model — Avtomatik va qo'lda yaratilgan ogohlantirishlar.

Alert tizimi uch holatda ishga tushadi:
    1. ADI keskin pasayganda (kuniga >15 ball)
    2. Jonivor 24 soat ko'rinmaganda
    3. Sensor kritik qiymat ko'rsatganda

Design decisions:
    - alert_type enum: kengaytirish oson, tip xavfsizligi yuqori
    - severity 4 daraja: triage tizimi uchun
    - resolved_at + resolved_by: audit trail
    - auto_generated flag: qo'lda va avtomatik alertlarni ajratish
    - context JSON: har xil alert turi o'z ma'lumotlarini saqlaydi
"""

from datetime import datetime
from typing import Optional, Any
import enum

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    CheckConstraint,
    JSON,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AlertType(str, enum.Enum):
    """
    Alert turlari.

    Har bir tur o'zining context strukturasiga ega.
    Yangi tur qo'shish uchun faqat shu enum va
    AlertService._build_context() ni yangilash yetarli.
    """

    # ADI based
    ADI_CRITICAL        = "adi_critical"        # ADI < 25
    ADI_WARNING         = "adi_warning"         # ADI < 50
    ADI_SHARP_DROP      = "adi_sharp_drop"      # 1 kunda >15 ball pasayish

    # Presence based
    ANIMAL_MISSING      = "animal_missing"      # 24+ soat ko'rinmadi
    ANIMAL_MISSING_LONG = "animal_missing_long" # 48+ soat ko'rinmadi

    # Behavior based
    ABNORMAL_MOVEMENT   = "abnormal_movement"   # G'ayri-tabiiy harakat
    ISOLATION_DETECTED  = "isolation_detected"  # Ijtimoiy ajralib qolish
    FEEDING_STOPPED     = "feeding_stopped"     # Ovqatlanish to'xtadi

    # Sensor based
    HIGH_TEMPERATURE    = "high_temperature"    # Isitma belgisi
    LOW_HEART_RATE      = "low_heart_rate"      # Yurak urishi past
    HIGH_HEART_RATE     = "high_heart_rate"     # Yurak urishi yuqori

    # Growth based
    GROWTH_STAGNATION   = "growth_stagnation"   # 14 kun o'sish yo'q
    WEIGHT_LOSS         = "weight_loss"         # Bbox hajmi kamayish trendi

    # System based
    CAMERA_OFFLINE      = "camera_offline"      # Kamera ulanmadi
    LOW_DATA_QUALITY    = "low_data_quality"    # ADI ma'lumot sifati past


class AlertSeverity(str, enum.Enum):
    """
    Alert jiddiyligi darajalari.

    Triage tizimi — fermer e'tiborini yo'naltirish uchun.
    """
    LOW      = "low"       # Ma'lumot uchun, harakat shart emas
    MEDIUM   = "medium"    # Kuzatishni kuchaytirish kerak
    HIGH     = "high"      # Tez orada aralashuv kerak
    CRITICAL = "critical"  # Zudlik bilan harakat kerak


class AlertStatus(str, enum.Enum):
    """Alert holati."""
    OPEN       = "open"       # Yangi, ko'rilmagan
    SEEN       = "seen"       # Ko'rilgan, harakat qilinmagan
    RESOLVED   = "resolved"   # Hal etilgan
    DISMISSED  = "dismissed"  # Bekor qilindi (noto'g'ri alarm)


# AlertType → default severity mapping
ALERT_SEVERITY_MAP: dict[AlertType, AlertSeverity] = {
    AlertType.ADI_CRITICAL:        AlertSeverity.CRITICAL,
    AlertType.ADI_WARNING:         AlertSeverity.MEDIUM,
    AlertType.ADI_SHARP_DROP:      AlertSeverity.HIGH,
    AlertType.ANIMAL_MISSING:      AlertSeverity.HIGH,
    AlertType.ANIMAL_MISSING_LONG: AlertSeverity.CRITICAL,
    AlertType.ABNORMAL_MOVEMENT:   AlertSeverity.MEDIUM,
    AlertType.ISOLATION_DETECTED:  AlertSeverity.LOW,
    AlertType.FEEDING_STOPPED:     AlertSeverity.HIGH,
    AlertType.HIGH_TEMPERATURE:    AlertSeverity.CRITICAL,
    AlertType.LOW_HEART_RATE:      AlertSeverity.CRITICAL,
    AlertType.HIGH_HEART_RATE:     AlertSeverity.HIGH,
    AlertType.GROWTH_STAGNATION:   AlertSeverity.MEDIUM,
    AlertType.WEIGHT_LOSS:         AlertSeverity.MEDIUM,
    AlertType.CAMERA_OFFLINE:      AlertSeverity.HIGH,
    AlertType.LOW_DATA_QUALITY:    AlertSeverity.LOW,
}


class Alert(BaseModel):
    """
    Ogohlantirish yozuvi.

    Avtomatik trigger yoki qo'lda yaratilishi mumkin.
    Bir jonivor uchun bir xil turdagi ochiq alert
    faqat bitta bo'lishi mumkin (deduplikatsiya).

    Columns:
        animal_id:        FK → Animal (NULL = tizim darajasidagi alert)
        camera_id:        Qaysi kamera trigger qildi (agar mavjud)
        alert_type:       Alert turi (AlertType enum)
        severity:         Jiddiylik darajasi (AlertSeverity enum)
        status:           Holat (open/seen/resolved/dismissed)
        title:            Qisqa sarlavha (UI uchun)
        description:      To'liq tavsif
        auto_generated:   True = tizim, False = qo'lda
        triggered_at:     Alert yaratilgan vaqt
        seen_at:          Ko'rilgan vaqt
        resolved_at:      Hal etilgan vaqt
        resolved_by:      Kim hal etdi
        resolution_note:  Qanday hal etildi
        context:          Alert spetsifik ma'lumotlar (JSON)
                          Masalan ADI_SHARP_DROP uchun:
                          {"prev_score": 68.0, "curr_score": 45.0, "drop": 23.0}
    """

    __tablename__ = "alerts"

    # ------------------------------------------------------------------ #
    # References                                                           #
    # ------------------------------------------------------------------ #

    animal_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("animals.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Target animal. NULL for system-level alerts (e.g. camera offline)",
    )

    camera_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Camera that triggered the alert, if applicable",
    )

    # ------------------------------------------------------------------ #
    # Alert Classification                                                 #
    # ------------------------------------------------------------------ #

    alert_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Alert type identifier (AlertType enum value)",
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="low | medium | high | critical",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AlertStatus.OPEN,
        index=True,
        comment="open | seen | resolved | dismissed",
    )

    # ------------------------------------------------------------------ #
    # Content                                                              #
    # ------------------------------------------------------------------ #

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Short human-readable title for UI display",
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full description with context and recommended action",
    )

    auto_generated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="True = system generated, False = manually created",
    )

    # ------------------------------------------------------------------ #
    # Timing                                                               #
    # ------------------------------------------------------------------ #

    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When the alert condition was detected",
    )

    seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When a user first viewed this alert",
    )

    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the alert was resolved or dismissed",
    )

    # ------------------------------------------------------------------ #
    # Resolution                                                           #
    # ------------------------------------------------------------------ #

    resolved_by: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="User/system that resolved the alert",
    )

    resolution_note: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="What action was taken to resolve",
    )

    # ------------------------------------------------------------------ #
    # Context Data                                                         #
    # ------------------------------------------------------------------ #

    context: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment=(
            "Alert-specific structured data. Schema varies by alert_type. "
            "Examples: "
            "ADI_SHARP_DROP → {prev_score, curr_score, drop_amount} "
            "ANIMAL_MISSING → {last_seen_at, hours_missing} "
            "HIGH_TEMPERATURE → {temperature, threshold, camera_id}"
        ),
    )

    # ------------------------------------------------------------------ #
    # Relationship                                                          #
    # ------------------------------------------------------------------ #

    animal: Mapped[Optional["Animal"]] = relationship(  # type: ignore[name-defined]
        "Animal",
        back_populates="alerts",
        lazy="selectin",
    )

    # ------------------------------------------------------------------ #
    # Constraints & Indexes                                                #
    # ------------------------------------------------------------------ #

    __table_args__ = (
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_alert_severity_valid",
        ),
        CheckConstraint(
            "status IN ('open', 'seen', 'resolved', 'dismissed')",
            name="ck_alert_status_valid",
        ),
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= triggered_at",
            name="ck_alert_resolved_after_triggered",
        ),
        # Ochiq alertlar bo'yicha tezkor query
        Index("ix_alerts_status_severity",   "status", "severity"),
        Index("ix_alerts_animal_status",     "animal_id", "status"),
        Index("ix_alerts_type_status",       "alert_type", "status"),
        Index("ix_alerts_triggered_at",      "triggered_at"),
    )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"<Alert("
            f"id={self.id}, "
            f"type={self.alert_type}, "
            f"severity={self.severity}, "
            f"status={self.status}, "
            f"animal_id={self.animal_id}"
            f")>"
        )

    @property
    def is_open(self) -> bool:
        """Alert hali hal etilmaganmi."""
        return self.status in (AlertStatus.OPEN, AlertStatus.SEEN)

    @property
    def is_critical(self) -> bool:
        """Zudlik bilan aralashuv talab etiladimi."""
        return self.severity == AlertSeverity.CRITICAL

    @property
    def duration_minutes(self) -> Optional[float]:
        """
        Alert necha daqiqa ochiq turdi.

        Returns:
            Daqiqa soni, yoki None (hali ochiq bo'lsa)
        """
        if not self.resolved_at:
            return None
        delta = self.resolved_at - self.triggered_at
        return delta.total_seconds() / 60

    def mark_seen(self, seen_at: Optional[datetime] = None) -> None:
        """Alertni ko'rilgan deb belgilash."""
        if self.status == AlertStatus.OPEN:
            self.status = AlertStatus.SEEN
            self.seen_at = seen_at or datetime.utcnow()

    def resolve(
        self,
        resolved_by: str,
        note: Optional[str] = None,
        resolved_at: Optional[datetime] = None,
    ) -> None:
        """
        Alertni hal etilgan deb belgilash.

        Args:
            resolved_by: Hal etgan foydalanuvchi nomi
            note:        Qanday harakat qilindi
            resolved_at: Vaqt (default: hozir)
        """
        self.status      = AlertStatus.RESOLVED
        self.resolved_by = resolved_by
        self.resolution_note = note
        self.resolved_at = resolved_at or datetime.utcnow()

    def dismiss(
        self,
        dismissed_by: str,
        reason: Optional[str] = None,
    ) -> None:
        """
        Alertni bekor qilish (noto'g'ri alarm).

        Args:
            dismissed_by: Kim bekor qildi
            reason:       Sabab
        """
        self.status      = AlertStatus.DISMISSED
        self.resolved_by = dismissed_by
        self.resolution_note = reason or "False alarm"
        self.resolved_at = datetime.utcnow()

