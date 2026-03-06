"""
Taurus Vision — Employee & WorkerTask Endpoints

ENDPOINTS:
  GET    /employees/                   — Ro'yxat
  POST   /employees/                   — Yaratish (MANAGER+)
  GET    /employees/stats              — Statistika
  GET    /employees/{id}               — Bitta xodim
  PATCH  /employees/{id}              — Yangilash (MANAGER+)
  POST   /employees/{id}/deactivate   — Ishdan bo'shatish (ADMIN)

  GET    /employees/tasks/             — Vazifalar ro'yxati
  POST   /employees/tasks/             — Vazifa yaratish (MANAGER+)
  GET    /employees/tasks/stats        — Vazifa statistikasi
  GET    /employees/tasks/{id}         — Bitta vazifa
  PATCH  /employees/tasks/{id}         — Yangilash (MANAGER+)
  POST   /employees/tasks/{id}/start   — Boshlash
  POST   /employees/tasks/{id}/complete — Bajarildi
  POST   /employees/tasks/{id}/cancel  — Bekor qilish (MANAGER+)
  POST   /employees/tasks/{id}/verify  — Tasdiqlash (MANAGER+)
"""

import logging
from typing import Optional, Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import (
    get_current_active_user, require_manager, require_admin,
    CurrentUser, CurrentManager, CurrentAdmin,
)
from app.schemas.employee import (
    EmployeeCreate, EmployeeUpdate, EmployeeResponse,
    EmployeeListResponse, EmployeeStats,
    WorkerTaskCreate, WorkerTaskUpdate, WorkerTaskComplete, WorkerTaskVerify,
    WorkerTaskResponse, WorkerTaskListResponse, WorkerTaskStats,
)
from app.services.employee_service import EmployeeService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/employees", tags=["Employees"])


def get_service(db: AsyncSession = Depends(get_db)) -> EmployeeService:
    return EmployeeService(db)


# =============================================================================
# EMPLOYEE ENDPOINTS
# =============================================================================

@router.get("/stats", response_model=EmployeeStats, summary="Xodimlar statistikasi")
async def get_employee_stats(
    current_user: CurrentUser,
    svc: EmployeeService = Depends(get_service),
):
    return await svc.get_stats()


@router.get("/", response_model=EmployeeListResponse, summary="Xodimlar ro'yxati")
async def list_employees(
    current_user: CurrentUser,
    farm_id:  Optional[int] = Query(None),
    status:   Optional[str] = Query(None),
    position: Optional[str] = Query(None),
    search:   Optional[str] = Query(None),
    page:     int           = Query(1, ge=1),
    size:     int           = Query(20, ge=1, le=100),
    svc: EmployeeService = Depends(get_service),
):
    return await svc.list_employees(
        farm_id=farm_id, status=status,
        position=position, search=search,
        page=page, size=size,
    )


@router.post("/", response_model=EmployeeResponse, status_code=201, summary="Xodim qo'shish")
async def create_employee(
    data: EmployeeCreate,
    current_user: CurrentManager,
    svc: EmployeeService = Depends(get_service),
):
    return await svc.create_employee(data)


@router.get("/{emp_id}", response_model=EmployeeResponse, summary="Xodim tafsiloti")
async def get_employee(
    emp_id: int,
    current_user: CurrentUser,
    svc: EmployeeService = Depends(get_service),
):
    return await svc.get_employee(emp_id)


@router.patch("/{emp_id}", response_model=EmployeeResponse, summary="Xodimni yangilash")
async def update_employee(
    emp_id: int,
    data: EmployeeUpdate,
    current_user: CurrentManager,
    svc: EmployeeService = Depends(get_service),
):
    return await svc.update_employee(emp_id, data)


@router.post("/{emp_id}/deactivate", response_model=EmployeeResponse, summary="Xodimni ishdan bo'shatish")
async def deactivate_employee(
    emp_id: int,
    current_user: CurrentAdmin,
    svc: EmployeeService = Depends(get_service),
):
    return await svc.deactivate_employee(emp_id)


# =============================================================================
# WORKER TASK ENDPOINTS
# =============================================================================

@router.get("/tasks/stats", response_model=WorkerTaskStats, summary="Vazifa statistikasi")
async def get_task_stats(
    current_user: CurrentUser,
    employee_id: Optional[int] = Query(None),
    svc: EmployeeService = Depends(get_service),
):
    return await svc.get_task_stats(employee_id=employee_id)


@router.get("/tasks/", response_model=WorkerTaskListResponse, summary="Vazifalar ro'yxati")
async def list_tasks(
    current_user: CurrentUser,
    employee_id:  Optional[int] = Query(None),
    status:       Optional[str] = Query(None),
    task_type:    Optional[str] = Query(None),
    priority:     Optional[str] = Query(None),
    overdue_only: bool          = Query(False),
    page:         int           = Query(1, ge=1),
    size:         int           = Query(20, ge=1, le=100),
    svc: EmployeeService = Depends(get_service),
):
    return await svc.list_tasks(
        employee_id=employee_id, status=status,
        task_type=task_type, priority=priority,
        overdue_only=overdue_only, page=page, size=size,
    )


@router.post("/tasks/", response_model=WorkerTaskResponse, status_code=201, summary="Vazifa yaratish")
async def create_task(
    data: WorkerTaskCreate,
    current_user: CurrentManager,
    svc: EmployeeService = Depends(get_service),
):
    return await svc.create_task(data, assigned_by=current_user.id)


@router.get("/tasks/{task_id}", response_model=WorkerTaskResponse, summary="Vazifa tafsiloti")
async def get_task(
    task_id: int,
    current_user: CurrentUser,
    svc: EmployeeService = Depends(get_service),
):
    return await svc.get_task(task_id)


@router.patch("/tasks/{task_id}", response_model=WorkerTaskResponse, summary="Vazifani yangilash")
async def update_task(
    task_id: int,
    data: WorkerTaskUpdate,
    current_user: CurrentManager,
    svc: EmployeeService = Depends(get_service),
):
    return await svc.update_task(task_id, data)


@router.post("/tasks/{task_id}/start", response_model=WorkerTaskResponse, summary="Vazifani boshlash")
async def start_task(
    task_id: int,
    current_user: CurrentUser,
    svc: EmployeeService = Depends(get_service),
):
    return await svc.start_task(task_id)


@router.post("/tasks/{task_id}/complete", response_model=WorkerTaskResponse, summary="Vazifani bajarish")
async def complete_task(
    task_id: int,
    data: WorkerTaskComplete,
    current_user: CurrentUser,
    svc: EmployeeService = Depends(get_service),
):
    return await svc.complete_task(task_id, data)


@router.post("/tasks/{task_id}/cancel", response_model=WorkerTaskResponse, summary="Vazifani bekor qilish")
async def cancel_task(
    task_id: int,
    current_user: CurrentManager,
    svc: EmployeeService = Depends(get_service),
):
    return await svc.cancel_task(task_id)


@router.post("/tasks/{task_id}/verify", response_model=WorkerTaskResponse, summary="Kamera orqali tasdiqlash")
async def verify_task(
    task_id: int,
    data: WorkerTaskVerify,
    current_user: CurrentManager,
    svc: EmployeeService = Depends(get_service),
):
    return await svc.verify_task(task_id, data, verifier_id=current_user.id)
