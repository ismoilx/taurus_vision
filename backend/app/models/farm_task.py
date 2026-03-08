"""
Taurus Vision — Farm Task Model (Sprint 19-20)

Ferma vazifalarini boshqarish uchun asosiy model.

VAZIFA TURLARI:
    Veterinar:   vaccination, health_check, medication, quarantine
    Parvarishlash: cleaning, grooming, hoof_trim
    Oziqlanish:  feeding, watering, supplement
    Ma'muriy:    weighing, tagging, transfer, other

LIFECYCLE:
    pending → in_progress → completed
                          → overdue   (due_date o'tib ketsa)
              → cancelled             (istalgan vaqtda)

MUNOSABATLAR:
    - Animal bilan ixtiyoriy (animal_id=None → ferma bo'yicha umumiy vazifa)
    - User bilan ixtiyoriy (assigned_to=None → tayinlanmagan)
    - created_by → kim yaratdi (audit uchun)
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, ForeignKey, Index, DateTime
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


# =============================================================================
# ENUMS
# =============================================================================

class TaskType(str, enum.Enum):
    """Vazifa turi."""
    # Veterinar
    VACCINATION   = "vaccination"
    HEALTH_CHECK  = "health_check"
    MEDICATION    = "medication"
    QUARANTINE    = "quarantine"

    # Parvarishlash
    CLEANING      = "cleaning"
    GROOMING      = "grooming"
    HOOF_TRIM     = "hoof_trim"

    # Oziqlanish
    FEEDING       = "feeding"
    WATERING      = "watering"
    SUPPLEMENT    = "supplement"

    # Ma'muriy
    WEIGHING      = "weighing"
    TAGGING       = "tagging"
    TRANSFER      = "transfer"
    OTHER         = "other"


class TaskPriority(str, enum.Enum):
    """Vazifa muhimligi."""
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class TaskStatus(str, enum.Enum):
    """Vazifa holati."""
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    OVERDUE     = "overdue"
    CANCELLED   = "cancelled"


# =============================================================================
# MODEL
# =============================================================================

class FarmTask(BaseModel):
    """
    Ferma vazifasi.

    Har bir vazifa ixtiyoriy ravishda bitta jonivir yoki
    umumiy ferma bilan bog'liq bo'lishi mumkin.

    Example:
        task = FarmTask(
            title="Emlash — JNV-042",
            task_type=TaskType.VACCINATION,
            priority=TaskPriority.HIGH,
            due_date=datetime(2026, 3, 10, 9, 0),
            animal_id=42,
            assigned_to=3,
        )
    """

    __tablename__ = "farm_tasks"

    # ------------------------------------------------------------------ #
    # Asosiy maydonlar                                                      #
    # ------------------------------------------------------------------ #

    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="Vazifa sarlavhasi",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Batafsil tavsif",
    )

    task_type: Mapped[TaskType] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="Vazifa turi",
    )

    priority: Mapped[TaskPriority] = mapped_column(
        String(20),
        nullable=False,
        default=TaskPriority.MEDIUM,
        index=True,
        comment="Muhimlik darajasi",
    )

    status: Mapped[TaskStatus] = mapped_column(
        String(20),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
        comment="Vazifa holati",
    )

    # ------------------------------------------------------------------ #
    # Muddatlar                                                             #
    # ------------------------------------------------------------------ #

    due_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Bajarish muddati (TZ-aware)",
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Bajarishga kirishilgan vaqt",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Bajarilgan vaqt",
    )

    # ------------------------------------------------------------------ #
    # Foreign Keys                                                         #
    # ------------------------------------------------------------------ #

    animal_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("animals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Qaysi jonivorga tegishli (None = ferma bo'yicha umumiy)",
    )

    assigned_to: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Kim bajaradi",
    )

    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Kim yaratdi",
    )

    # ------------------------------------------------------------------ #
    # Qo'shimcha ma'lumot                                                  #
    # ------------------------------------------------------------------ #

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Bajaruvchi izohi (completion paytida to'ldiriladi)",
    )

    meta: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Qo'shimcha ma'lumot: doza, mahsulot nomi, miqdor va boshqalar",
    )

    # Takrorlanuvchi vazifalar uchun (kelasi sprint)
    recurring_source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("farm_tasks.id", ondelete="SET NULL"),
        nullable=True,
        comment="Agar bu takrorlanuvchi vazifadan yaratilsa — manba ID si",
    )

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #

    animal: Mapped[Optional["Animal"]] = relationship(  # type: ignore[name-defined]
        "Animal",
        foreign_keys=[animal_id],
        lazy="noload",
    )

    assignee: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User",
        foreign_keys=[assigned_to],
        lazy="noload",
    )

    creator: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User",
        foreign_keys=[created_by],
        lazy="noload",
    )

    # ------------------------------------------------------------------ #
    # Indekslar                                                            #
    # ------------------------------------------------------------------ #

    __table_args__ = (
        Index("ix_farm_tasks_status_due",      "status", "due_date"),
        Index("ix_farm_tasks_type_status",     "task_type", "status"),
        Index("ix_farm_tasks_animal_status",   "animal_id", "status"),
        Index("ix_farm_tasks_assigned_status", "assigned_to", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<FarmTask("
            f"id={self.id}, "
            f"type={self.task_type}, "
            f"priority={self.priority}, "
            f"status={self.status}"
            f")>"
        )

    # ------------------------------------------------------------------ #
    # Helper properties                                                    #
    # ------------------------------------------------------------------ #

    @property
    def is_overdue(self) -> bool:
        """Muddati o'tib ketganmi?"""
        from datetime import timezone
        if self.due_date is None:
            return False
        if self.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            return False
        return datetime.now(timezone.utc) > self.due_date

    @property
    def is_open(self) -> bool:
        """Hali bajarilmagan yoki bekor qilinmaganmi?"""
        return self.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE)