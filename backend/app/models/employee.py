"""
Taurus Vision — Employee (Ishchi hodim) Model

Ferma xodimlari va ularga biriktirilgan vazifalar.

ROLLAR:
    FEEDER      — Boqituvchi
    VETERINARIAN — Veterinar
    MECHANIC    — Mexanik
    GUARD       — Qorovul
    MANAGER     — Boshqaruvchi
    CLEANER     — Tozalovchi
    OTHER       — Boshqa

VAZIFA LIFECYCLE:
    pending → in_progress → completed
                          → overdue
              → cancelled

KAMERA TASDIQLASH:
    Vazifa bajarilgandan so'ng kamera orqali vizual tasdiqlash
    imkoniyati mavjud (camera_verified flag).
"""

import enum
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    String, Text, ForeignKey, Index, DateTime,
    Date, Numeric, Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


# =============================================================================
# ENUMS
# =============================================================================

class EmployeePosition(str, enum.Enum):
    """Xodim lavozimi."""
    FEEDER       = "feeder"        # Boqituvchi
    VETERINARIAN = "veterinarian"  # Veterinar
    MECHANIC     = "mechanic"      # Mexanik
    GUARD        = "guard"         # Qorovul
    MANAGER      = "manager"       # Boshqaruvchi
    CLEANER      = "cleaner"       # Tozalovchi
    OTHER        = "other"         # Boshqa


class EmployeeStatus(str, enum.Enum):
    """Xodim holati."""
    ACTIVE    = "active"     # Ishlaydi
    INACTIVE  = "inactive"   # Ishlamaydi (ketgan)
    ON_LEAVE  = "on_leave"   # Ta'tilda


class WorkerTaskStatus(str, enum.Enum):
    """Xodim vazifasi holati."""
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    OVERDUE     = "overdue"
    CANCELLED   = "cancelled"


class WorkerTaskPriority(str, enum.Enum):
    """Vazifa muhimligi."""
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class WorkerTaskType(str, enum.Enum):
    """Vazifa turi."""
    FEEDING      = "feeding"       # Oziqlantiruv
    WATERING     = "watering"      # Suv berish
    CLEANING     = "cleaning"      # Tozalash
    VACCINATION  = "vaccination"   # Emlash
    HEALTH_CHECK = "health_check"  # Sog'liq tekshiruv
    MEDICATION   = "medication"    # Dori berish
    WEIGHING     = "weighing"      # Vazn o'lchash
    GROOMING     = "grooming"      # Parvarish
    TRANSFER     = "transfer"      # Ko'chirish
    REPAIR       = "repair"        # Ta'mirlash
    SECURITY     = "security"      # Qo'riqlash
    OTHER        = "other"         # Boshqa


class VerificationStatus(str, enum.Enum):
    """Kamera tasdiqlash holati."""
    UNVERIFIED = "unverified"  # Hali tekshirilmagan
    VERIFIED   = "verified"    # Tasdiqlangan
    FAILED     = "failed"      # Bajarilmagan (kameradan ko'rinmadi)


# =============================================================================
# EMPLOYEE MODEL
# =============================================================================

class Employee(BaseModel):
    """
    Ferma xodimi.

    Tizim foydalanuvchisidan farqli — bu jismoniy ishchi,
    uning tizimga kirish huquqi bo'lmasligi mumkin.

    Example:
        emp = Employee(
            full_name="Karimov Sardor",
            position=EmployeePosition.FEEDER,
            phone="+998901234567",
            hire_date=date(2025, 1, 15),
        )
    """

    __tablename__ = "employees"

    # ── Shaxsiy ma'lumotlar ──────────────────────────────────────────────── #

    full_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="To'liq ismi sharifi",
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Telefon raqami",
    )

    position: Mapped[EmployeePosition] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        default=EmployeePosition.OTHER,
        comment="Lavozim",
    )

    status: Mapped[EmployeeStatus] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        default=EmployeeStatus.ACTIVE,
        comment="Xodim holati",
    )

    # ── Ish ma'lumotlari ─────────────────────────────────────────────────── #

    hire_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Ishga qabul sanasi",
    )

    salary: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Oylik maosh (so'm)",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Qo'shimcha izoh",
    )

    # ── Foreign Keys ─────────────────────────────────────────────────────── #

    farm_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("farms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Qaysi fermada ishlaydi",
    )

    # ── Relationships ────────────────────────────────────────────────────── #

    tasks: Mapped[list["WorkerTask"]] = relationship(
        "WorkerTask",
        back_populates="employee",
        foreign_keys="WorkerTask.employee_id",
        lazy="noload",
    )

    # ── Indexes ──────────────────────────────────────────────────────────── #

    __table_args__ = (
        Index("ix_employees_status_position", "status", "position"),
        Index("ix_employees_farm_status",     "farm_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Employee(id={self.id}, name={self.full_name}, pos={self.position})>"

    @property
    def is_active(self) -> bool:
        return self.status == EmployeeStatus.ACTIVE


# =============================================================================
# WORKER TASK MODEL
# =============================================================================

class WorkerTask(BaseModel):
    """
    Xodimga biriktirilgan vazifa.

    Kamera orqali tasdiqlash imkoniyati bor —
    vazifa bajarilgandan keyin kamera yordamida
    vizual tasdiqlash mumkin.

    Example:
        task = WorkerTask(
            title="Sigirlarni ertalabki oziqlantiruvi",
            task_type=WorkerTaskType.FEEDING,
            priority=WorkerTaskPriority.HIGH,
            employee_id=5,
            due_date=datetime(2026, 3, 7, 8, 0),
        )
    """

    __tablename__ = "worker_tasks"

    # ── Asosiy maydonlar ─────────────────────────────────────────────────── #

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

    task_type: Mapped[WorkerTaskType] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="Vazifa turi",
    )

    priority: Mapped[WorkerTaskPriority] = mapped_column(
        String(20),
        nullable=False,
        default=WorkerTaskPriority.MEDIUM,
        index=True,
        comment="Muhimlik darajasi",
    )

    status: Mapped[WorkerTaskStatus] = mapped_column(
        String(20),
        nullable=False,
        default=WorkerTaskStatus.PENDING,
        index=True,
        comment="Vazifa holati",
    )

    # ── Muddatlar ────────────────────────────────────────────────────────── #

    due_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Bajarish muddati",
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Boshlanish vaqti",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Bajarilish vaqti",
    )

    # ── Foreign Keys ─────────────────────────────────────────────────────── #

    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Kim bajaradi",
    )

    animal_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("animals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Qaysi jonivorga tegishli (ixtiyoriy)",
    )

    assigned_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Kim tayinladi (system user)",
    )

    # ── Kamera tasdiqlash ────────────────────────────────────────────────── #

    requires_verification: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Kamera tasdiqlash talab qilinadimi",
    )

    verification_status: Mapped[VerificationStatus] = mapped_column(
        String(20),
        nullable=False,
        default=VerificationStatus.UNVERIFIED,
        comment="Kamera tasdiqlash holati",
    )

    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Tasdiqlangan vaqt",
    )

    verified_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Kim tasdiqladi",
    )

    # ── Izoh ─────────────────────────────────────────────────────────────── #

    completion_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Bajaruvchinning izohi",
    )

    # ── Relationships ────────────────────────────────────────────────────── #

    employee: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        back_populates="tasks",
        foreign_keys=[employee_id],
        lazy="noload",
    )

    # ── Indexes ──────────────────────────────────────────────────────────── #

    __table_args__ = (
        Index("ix_worker_tasks_emp_status",    "employee_id", "status"),
        Index("ix_worker_tasks_status_due",    "status", "due_date"),
        Index("ix_worker_tasks_type_status",   "task_type", "status"),
        Index("ix_worker_tasks_animal_status", "animal_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<WorkerTask(id={self.id}, type={self.task_type}, "
            f"status={self.status}, emp={self.employee_id})>"
        )

    @property
    def is_overdue(self) -> bool:
        from datetime import timezone
        if not self.due_date:
            return False
        if self.status in (WorkerTaskStatus.COMPLETED, WorkerTaskStatus.CANCELLED):
            return False
        return datetime.now(timezone.utc) > self.due_date

    @property
    def is_open(self) -> bool:
        return self.status in (
            WorkerTaskStatus.PENDING,
            WorkerTaskStatus.IN_PROGRESS,
            WorkerTaskStatus.OVERDUE,
        )
