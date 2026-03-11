"""
Taurus Vision — Farm Task Schemas (Sprint 19-20)

API request/response validatsiyasi uchun Pydantic v2 schemalar.

SCHEMAS:
    FarmTaskCreate   — POST /tasks/   uchun
    FarmTaskUpdate   — PATCH /tasks/{id} uchun
    FarmTaskComplete — POST /tasks/{id}/complete uchun
    FarmTaskResponse — barcha response lar uchun
    FarmTaskSummary  — ro'yxat va statistika uchun (yengil variant)
    TaskStats        — dashboard statistikasi
"""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.farm_task import TaskType, TaskPriority, TaskStatus


# =============================================================================
# CREATE
# =============================================================================

class FarmTaskCreate(BaseModel):
    """Yangi vazifa yaratish."""

    title: str = Field(
        ...,
        min_length=3,
        max_length=300,
        description="Vazifa sarlavhasi",
        examples=["JNV-042 — Emlash (FMD)"],
    )

    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Batafsil tavsif",
    )

    task_type: TaskType = Field(
        TaskType.OTHER,
        description="Vazifa turi",
    )

    priority: TaskPriority = Field(
        TaskPriority.MEDIUM,
        description="Muhimlik darajasi",
    )

    due_date: Optional[datetime] = Field(
        None,
        description="Bajarish muddati (ISO 8601 + timezone)",
    )

    animal_id: Optional[int] = Field(
        None,
        gt=0,
        description="Jonivor ID (None = umumiy ferma vazifasi)",
    )

    assigned_to: Optional[int] = Field(
        None,
        gt=0,
        description="Bajaruvchi foydalanuvchi ID",
    )

    meta: Optional[dict[str, Any]] = Field(
        None,
        description="Qo'shimcha: doza, mahsulot, miqdor...",
        examples=[{"dose_ml": 5, "vaccine": "FMD-Gold", "batch": "2026-A"}],
    )

    @field_validator("due_date")
    @classmethod
    def due_date_must_be_future(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Muddati o'tgan vaqt bo'lmasligi kerak."""
        if v is None:
            return v
        from datetime import timezone
        # Timezone-aware qilish
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        # O'tganmi tekshirish (5 daqiqa tolerans)
        from datetime import timedelta
        if v < datetime.now(timezone.utc) - timedelta(minutes=5):
            raise ValueError("Muddati o'tgan sana bo'lishi mumkin emas.")
        return v


# =============================================================================
# UPDATE
# =============================================================================

class FarmTaskUpdate(BaseModel):
    """Vazifani qisman yangilash (PATCH)."""

    title: Optional[str] = Field(None, min_length=3, max_length=300)
    description: Optional[str] = Field(None, max_length=2000)
    task_type: Optional[TaskType] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    due_date: Optional[datetime] = None
    assigned_to: Optional[int] = Field(None, gt=0)
    notes: Optional[str] = Field(None, max_length=2000)
    meta: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "FarmTaskUpdate":
        """Hech bo'lmasa bitta maydon bo'lishi kerak."""
        values = self.model_dump(exclude_none=True)
        if not values:
            raise ValueError("Kamida bitta maydon yuborilishi kerak.")
        return self


# =============================================================================
# COMPLETE
# =============================================================================

class FarmTaskComplete(BaseModel):
    """Vazifani bajarilgan deb belgilash."""

    notes: Optional[str] = Field(
        None,
        max_length=2000,
        description="Bajaruvchi izohi (ixtiyoriy)",
    )

    meta: Optional[dict[str, Any]] = Field(
        None,
        description="Bajarilish ma'lumotlari (haqiqiy doza, vaqt va h.k.)",
    )


# =============================================================================
# RESPONSE
# =============================================================================

class AssigneeInfo(BaseModel):
    """Bajaruvchi haqida qisqa ma'lumot."""
    id: int
    username: str
    full_name: Optional[str] = None

    model_config = {"from_attributes": True}


class AnimalInfo(BaseModel):
    """Jonivor haqida qisqa ma'lumot."""
    id: int
    tag_id: str
    species: str

    model_config = {"from_attributes": True}


class FarmTaskResponse(BaseModel):
    """To'liq vazifa response — bitta vazifa uchun."""

    id: int
    title: str
    description: Optional[str] = None
    task_type: TaskType
    priority: TaskPriority
    status: TaskStatus

    due_date: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    animal_id: Optional[int] = None
    assigned_to: Optional[int] = None
    created_by: Optional[int] = None

    notes: Optional[str] = None
    meta: Optional[dict[str, Any]] = None

    is_overdue: bool = False

    created_at: datetime
    updated_at: datetime

    # Joined ma'lumotlar (eager load qilinsa)
    animal: Optional[AnimalInfo] = None
    assignee: Optional[AssigneeInfo] = None

    model_config = {"from_attributes": True}


class FarmTaskSummary(BaseModel):
    """Yengil variant — ro'yxat uchun."""

    id: int
    title: str
    task_type: TaskType
    priority: TaskPriority
    status: TaskStatus
    due_date: Optional[datetime] = None
    animal_id: Optional[int] = None
    assigned_to: Optional[int] = None
    is_overdue: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


# =============================================================================
# LIST RESPONSE
# =============================================================================

class FarmTaskListResponse(BaseModel):
    """Sahifalangan ro'yxat."""

    items: list[FarmTaskSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# STATISTICS
# =============================================================================

class TaskStats(BaseModel):
    """Dashboard uchun vazifa statistikasi."""

    total_open: int        = Field(description="Ochiq vazifalar (pending + in_progress)")
    total_overdue: int     = Field(description="Muddati o'tgan vazifalar")
    total_today: int       = Field(description="Bugun bajarish kerak (due today)")
    total_completed_today: int = Field(description="Bugun bajarilgan")

    by_priority: dict[str, int] = Field(
        description="Ochiq vazifalar muhimlik bo'yicha",
        examples=[{"critical": 2, "high": 5, "medium": 10, "low": 3}],
    )

    by_type: dict[str, int] = Field(
        description="Ochiq vazifalar tur bo'yicha",
    )

    critical_overdue: list[FarmTaskSummary] = Field(
        description="Muddati o'tgan CRITICAL va HIGH vazifalar (max 5)",
    )