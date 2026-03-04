"""
Taurus Vision — Farm Task API Endpoints (Sprint 19-20)

REST API for farm task management.

ENDPOINTS:
    GET    /tasks/             — Ro'yxat (filtr + sahifalash)
    POST   /tasks/             — Yangi vazifa
    GET    /tasks/stats        — Dashboard statistikasi
    GET    /tasks/{id}         — Bitta vazifa
    PATCH  /tasks/{id}         — Yangilash
    POST   /tasks/{id}/start   — Boshlash (PENDING → IN_PROGRESS)
    POST   /tasks/{id}/complete — Bajarildi
    POST   /tasks/{id}/cancel  — Bekor qilish

AUTH:
    Barcha endpointlar JWT talab qiladi.
    Faqat admin/manager yaratishi/bekor qilishi mumkin.
    Viewer faqat ko'rishi mumkin.
"""

import logging
from typing import Optional, Annotated

from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_user, require_manager
from app.core.database import get_db
from app.models.farm_task import TaskType, TaskPriority, TaskStatus
from app.models.user import User
from app.schemas.farm_task import (
    FarmTaskCreate,
    FarmTaskUpdate,
    FarmTaskComplete,
    FarmTaskResponse,
    FarmTaskListResponse,
    TaskStats,
)
from app.services.farm_task_service import FarmTaskService

logger   = logging.getLogger(__name__)
router   = APIRouter(prefix="/tasks", tags=["Tasks"])

# Qisqa alias
CurrentUser    = Annotated[User, Depends(get_current_active_user)]
CurrentManager = Annotated[User, Depends(require_manager)]
DB             = Annotated[AsyncSession, Depends(get_db)]


# =============================================================================
# LIST
# =============================================================================

@router.get("/", response_model=FarmTaskListResponse)
async def list_tasks(
    db:   DB,
    user: CurrentUser,
    # Filtrlar
    status:      Optional[list[TaskStatus]] = Query(None, description="Holat bo'yicha filtr"),
    task_type:   Optional[TaskType]         = Query(None),
    priority:    Optional[TaskPriority]     = Query(None),
    animal_id:   Optional[int]              = Query(None, gt=0),
    assigned_to: Optional[int]              = Query(None, gt=0),
    overdue_only: bool                      = Query(False, description="Faqat muddati o'tganlar"),
    due_today:   bool                       = Query(False, description="Faqat bugungi"),
    # Sahifalash
    page:      int = Query(1,  ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> FarmTaskListResponse:
    """
    Vazifalar ro'yxati.

    Filtrlar kombinatsiyalash mumkin.
    Natija due_date (eski avval) va priority (critical avval) bo'yicha tartiblanadi.
    """
    svc = FarmTaskService(db)
    return await svc.get_tasks(
        status       = status,
        task_type    = task_type,
        priority     = priority,
        animal_id    = animal_id,
        assigned_to  = assigned_to,
        overdue_only = overdue_only,
        due_today    = due_today,
        page         = page,
        page_size    = page_size,
    )


# =============================================================================
# STATISTICS
# =============================================================================

@router.get("/stats", response_model=TaskStats)
async def get_task_stats(
    db:   DB,
    user: CurrentUser,
) -> TaskStats:
    """
    Dashboard uchun vazifa statistikasi.

    Qaytaradi: ochiq, muddati o'tgan, bugungi, bugun bajarilgan vazifalar soni,
    priority va tur bo'yicha breakdown, kritik muddati o'tganlar ro'yxati.
    """
    svc = FarmTaskService(db)
    return await svc.get_stats()


# =============================================================================
# CREATE
# =============================================================================

@router.post("/", response_model=FarmTaskResponse, status_code=201)
async def create_task(
    db:   DB,
    user: CurrentManager,
    data: FarmTaskCreate = Body(...),
) -> FarmTaskResponse:
    """
    Yangi vazifa yaratish.

    Faqat admin va manager yarata oladi.
    Animal va assigned_to ID lari tekshiriladi.
    CRITICAL priority bo'lsa avtomatik alert yaratiladi.
    """
    svc = FarmTaskService(db)
    return await svc.create_task(data, created_by=user.id)


# =============================================================================
# GET ONE
# =============================================================================

@router.get("/{task_id}", response_model=FarmTaskResponse)
async def get_task(
    task_id: int,
    db:      DB,
    user:    CurrentUser,
) -> FarmTaskResponse:
    """Bitta vazifa — to'liq ma'lumot (animal va assignee bilan)."""
    svc = FarmTaskService(db)
    return await svc.get_task(task_id)


# =============================================================================
# UPDATE
# =============================================================================

@router.patch("/{task_id}", response_model=FarmTaskResponse)
async def update_task(
    task_id: int,
    db:      DB,
    user:    CurrentManager,
    data:    FarmTaskUpdate = Body(...),
) -> FarmTaskResponse:
    """
    Vazifani qisman yangilash.

    Status o'zgartirish uchun transition qoidalari tekshiriladi.
    Faqat admin va manager yangilay oladi.
    """
    svc = FarmTaskService(db)
    return await svc.update_task(task_id, data, user_id=user.id)


# =============================================================================
# START
# =============================================================================

@router.post("/{task_id}/start", response_model=FarmTaskResponse)
async def start_task(
    task_id: int,
    db:      DB,
    user:    CurrentUser,
) -> FarmTaskResponse:
    """
    Vazifani boshlash (PENDING/OVERDUE → IN_PROGRESS).

    Har qanday autentifikatsiyalangan foydalanuvchi boshlashi mumkin
    (field worker ham).
    """
    svc  = FarmTaskService(db)
    data = FarmTaskUpdate(status=TaskStatus.IN_PROGRESS)
    return await svc.update_task(task_id, data, user_id=user.id)


# =============================================================================
# COMPLETE
# =============================================================================

@router.post("/{task_id}/complete", response_model=FarmTaskResponse)
async def complete_task(
    task_id: int,
    db:      DB,
    user:    CurrentUser,
    data:    FarmTaskComplete = Body(FarmTaskComplete()),
) -> FarmTaskResponse:
    """
    Vazifani bajarilgan deb belgilash.

    Ixtiyoriy: izoh va qo'shimcha ma'lumot (haqiqiy doza, mahsulot va h.k.).
    """
    svc = FarmTaskService(db)
    return await svc.complete_task(task_id, data, user_id=user.id)


# =============================================================================
# CANCEL
# =============================================================================

@router.post("/{task_id}/cancel", response_model=FarmTaskResponse)
async def cancel_task(
    task_id: int,
    db:      DB,
    user:    CurrentManager,
    reason:  Optional[str] = Body(None, embed=True, max_length=500),
) -> FarmTaskResponse:
    """
    Vazifani bekor qilish.

    Bajarilgan vazifani bekor qilib bo'lmaydi.
    Faqat admin va manager bekor qila oladi.
    """
    svc = FarmTaskService(db)
    return await svc.cancel_task(task_id, reason=reason, user_id=user.id)