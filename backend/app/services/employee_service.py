"""
Taurus Vision — Employee Service

Biznes logika: xodimlar va ularning vazifalari.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import (
    Employee, WorkerTask,
    EmployeePosition, EmployeeStatus,
    WorkerTaskStatus, WorkerTaskPriority, WorkerTaskType, VerificationStatus,
)
from app.repositories.employee_repository import EmployeeRepository
from app.schemas.employee import (
    EmployeeCreate, EmployeeUpdate, EmployeeResponse,
    EmployeeListResponse, EmployeeStats,
    WorkerTaskCreate, WorkerTaskUpdate, WorkerTaskComplete, WorkerTaskVerify,
    WorkerTaskResponse, WorkerTaskListResponse, WorkerTaskStats,
)
from app.core.exceptions import (
    EntityNotFoundError, BusinessRuleViolationError, ValidationError,
)

logger = logging.getLogger(__name__)

POSITION_LABELS = {
    "feeder":       "Boqituvchi",
    "veterinarian": "Veterinar",
    "mechanic":     "Mexanik",
    "guard":        "Qorovul",
    "manager":      "Boshqaruvchi",
    "cleaner":      "Tozalovchi",
    "other":        "Boshqa",
}


def _build_task_response(task: WorkerTask) -> WorkerTaskResponse:
    emp_name = None
    emp_pos  = None
    if task.employee:
        emp_name = task.employee.full_name
        emp_pos  = POSITION_LABELS.get(str(task.employee.position), str(task.employee.position))

    return WorkerTaskResponse(
        id=task.id, title=task.title, description=task.description,
        task_type=task.task_type, priority=task.priority, status=task.status,
        due_date=task.due_date, started_at=task.started_at, completed_at=task.completed_at,
        employee_id=task.employee_id, employee_name=emp_name, employee_position=emp_pos,
        animal_id=task.animal_id, assigned_by=task.assigned_by,
        requires_verification=task.requires_verification,
        verification_status=task.verification_status,
        verified_at=task.verified_at, verified_by=task.verified_by,
        completion_notes=task.completion_notes,
        is_overdue=task.is_overdue,
        created_at=task.created_at, updated_at=task.updated_at,
    )


class EmployeeService:

    def __init__(self, db: AsyncSession) -> None:
        self.db   = db
        self.repo = EmployeeRepository(db)

    # ── Employee ──────────────────────────────────────────────────────────

    async def create_employee(self, data: EmployeeCreate) -> EmployeeResponse:
        emp = Employee(
            full_name=data.full_name, phone=data.phone,
            position=data.position, status=data.status,
            hire_date=data.hire_date, salary=data.salary,
            notes=data.notes, farm_id=data.farm_id,
        )
        emp = await self.repo.create_employee(emp)
        await self.db.commit()
        logger.info(f"Employee created: id={emp.id} name={emp.full_name}")
        return await self._emp_response(emp)

    async def get_employee(self, emp_id: int) -> EmployeeResponse:
        emp = await self.repo.get_employee_by_id(emp_id)
        if not emp:
            raise EntityNotFoundError("Employee", emp_id)
        return await self._emp_response(emp)

    async def list_employees(
        self,
        farm_id: Optional[int] = None,
        status:  Optional[str] = None,
        position: Optional[str] = None,
        search:  Optional[str] = None,
        page: int = 1, size: int = 20,
    ) -> EmployeeListResponse:
        emp_status = EmployeeStatus(status) if status else None
        items, total = await self.repo.list_employees(
            farm_id=farm_id, status=emp_status, position=position,
            search=search, page=page, size=size,
        )
        responses = []
        for emp in items:
            responses.append(await self._emp_response(emp))
        pages = max(1, (total + size - 1) // size)
        return EmployeeListResponse(items=responses, total=total, page=page, size=size, pages=pages)

    async def update_employee(self, emp_id: int, data: EmployeeUpdate) -> EmployeeResponse:
        emp = await self.repo.get_employee_by_id(emp_id)
        if not emp:
            raise EntityNotFoundError("Employee", emp_id)

        for field, val in data.model_dump(exclude_unset=True).items():
            setattr(emp, field, val)

        emp = await self.repo.update_employee(emp)
        await self.db.commit()
        logger.info(f"Employee updated: id={emp_id}")
        return await self._emp_response(emp)

    async def deactivate_employee(self, emp_id: int) -> EmployeeResponse:
        emp = await self.repo.get_employee_by_id(emp_id)
        if not emp:
            raise EntityNotFoundError("Employee", emp_id)
        emp.status = EmployeeStatus.INACTIVE
        await self.repo.update_employee(emp)
        await self.db.commit()
        return await self._emp_response(emp)

    async def get_stats(self) -> EmployeeStats:
        raw = await self.repo.get_employee_stats()
        return EmployeeStats(**raw)

    async def _emp_response(self, emp: Employee) -> EmployeeResponse:
        counts = await self.repo.get_task_counts_for_employee(emp.id)
        return EmployeeResponse(
            id=emp.id, full_name=emp.full_name, phone=emp.phone,
            position=emp.position, status=emp.status,
            hire_date=emp.hire_date, salary=emp.salary,
            notes=emp.notes, farm_id=emp.farm_id,
            created_at=emp.created_at, updated_at=emp.updated_at,
            open_tasks=counts["open"],
            completed_tasks=counts["completed"],
            overdue_tasks=counts["overdue"],
        )

    # ── WorkerTask ────────────────────────────────────────────────────────

    async def create_task(self, data: WorkerTaskCreate, assigned_by: int) -> WorkerTaskResponse:
        if data.employee_id:
            emp = await self.repo.get_employee_by_id(data.employee_id)
            if not emp:
                raise EntityNotFoundError("Employee", data.employee_id)
            if emp.status == EmployeeStatus.INACTIVE:
                raise BusinessRuleViolationError("Faol bo'lmagan xodimga vazifa tayinlab bo'lmaydi.")

        task = WorkerTask(
            title=data.title, description=data.description,
            task_type=data.task_type, priority=data.priority,
            due_date=data.due_date, employee_id=data.employee_id,
            animal_id=data.animal_id, assigned_by=assigned_by,
            requires_verification=data.requires_verification,
        )
        task = await self.repo.create_task(task)
        await self.db.commit()

        task = await self.repo.get_task_by_id(task.id)
        logger.info(f"WorkerTask created: id={task.id}")
        return _build_task_response(task)

    async def get_task(self, task_id: int) -> WorkerTaskResponse:
        task = await self.repo.get_task_by_id(task_id)
        if not task:
            raise EntityNotFoundError("WorkerTask", task_id)
        return _build_task_response(task)

    async def list_tasks(
        self,
        employee_id: Optional[int] = None,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        priority: Optional[str] = None,
        overdue_only: bool = False,
        page: int = 1, size: int = 20,
    ) -> WorkerTaskListResponse:
        task_status = WorkerTaskStatus(status) if status else None
        items, total = await self.repo.list_tasks(
            employee_id=employee_id, status=task_status,
            task_type=task_type, priority=priority,
            overdue_only=overdue_only, page=page, size=size,
        )
        pages = max(1, (total + size - 1) // size)
        return WorkerTaskListResponse(
            items=[_build_task_response(t) for t in items],
            total=total, page=page, size=size, pages=pages,
        )

    async def update_task(self, task_id: int, data: WorkerTaskUpdate) -> WorkerTaskResponse:
        task = await self.repo.get_task_by_id(task_id)
        if not task:
            raise EntityNotFoundError("WorkerTask", task_id)
        if task.status in (WorkerTaskStatus.COMPLETED, WorkerTaskStatus.CANCELLED):
            raise BusinessRuleViolationError("Yakunlangan yoki bekor qilingan vazifani o'zgartirib bo'lmaydi.")

        for field, val in data.model_dump(exclude_unset=True).items():
            setattr(task, field, val)

        task = await self.repo.update_task(task)
        await self.db.commit()
        task = await self.repo.get_task_by_id(task_id)
        return _build_task_response(task)

    async def start_task(self, task_id: int) -> WorkerTaskResponse:
        task = await self.repo.get_task_by_id(task_id)
        if not task:
            raise EntityNotFoundError("WorkerTask", task_id)
        if task.status not in (WorkerTaskStatus.PENDING, WorkerTaskStatus.OVERDUE):
            raise BusinessRuleViolationError("Faqat kutilayotgan yoki muddati o'tgan vazifani boshlash mumkin.")
        task.status     = WorkerTaskStatus.IN_PROGRESS
        task.started_at = datetime.now(timezone.utc)
        await self.repo.update_task(task)
        await self.db.commit()
        task = await self.repo.get_task_by_id(task_id)
        return _build_task_response(task)

    async def complete_task(self, task_id: int, data: WorkerTaskComplete) -> WorkerTaskResponse:
        task = await self.repo.get_task_by_id(task_id)
        if not task:
            raise EntityNotFoundError("WorkerTask", task_id)
        if task.status == WorkerTaskStatus.COMPLETED:
            raise BusinessRuleViolationError("Vazifa allaqachon bajarilgan.")
        if task.status == WorkerTaskStatus.CANCELLED:
            raise BusinessRuleViolationError("Bekor qilingan vazifani bajarilgan deb belgilash mumkin emas.")

        task.status           = WorkerTaskStatus.COMPLETED
        task.completed_at     = datetime.now(timezone.utc)
        task.completion_notes = data.completion_notes
        if not task.started_at:
            task.started_at = task.completed_at

        await self.repo.update_task(task)
        await self.db.commit()
        task = await self.repo.get_task_by_id(task_id)
        logger.info(f"WorkerTask completed: id={task_id}")
        return _build_task_response(task)

    async def cancel_task(self, task_id: int) -> WorkerTaskResponse:
        task = await self.repo.get_task_by_id(task_id)
        if not task:
            raise EntityNotFoundError("WorkerTask", task_id)
        if task.status in (WorkerTaskStatus.COMPLETED, WorkerTaskStatus.CANCELLED):
            raise BusinessRuleViolationError("Bu vazifani bekor qilib bo'lmaydi.")
        task.status = WorkerTaskStatus.CANCELLED
        await self.repo.update_task(task)
        await self.db.commit()
        task = await self.repo.get_task_by_id(task_id)
        return _build_task_response(task)

    async def verify_task(self, task_id: int, data: WorkerTaskVerify, verifier_id: int) -> WorkerTaskResponse:
        task = await self.repo.get_task_by_id(task_id)
        if not task:
            raise EntityNotFoundError("WorkerTask", task_id)
        if not task.requires_verification:
            raise BusinessRuleViolationError("Bu vazifa uchun tasdiqlash talab qilinmaydi.")
        if task.status != WorkerTaskStatus.COMPLETED:
            raise BusinessRuleViolationError("Faqat bajarilgan vazifani tasdiqlash mumkin.")

        task.verification_status = data.verification_status
        task.verified_at         = datetime.now(timezone.utc)
        task.verified_by         = verifier_id
        if data.notes:
            task.completion_notes = (task.completion_notes or "") + f"\n[Tasdiqlash]: {data.notes}"

        await self.repo.update_task(task)
        await self.db.commit()
        task = await self.repo.get_task_by_id(task_id)
        return _build_task_response(task)

    async def get_task_stats(self, employee_id: Optional[int] = None) -> WorkerTaskStats:
        raw = await self.repo.get_task_stats(employee_id)
        return WorkerTaskStats(**raw)
