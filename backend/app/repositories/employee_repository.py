"""
Taurus Vision — Employee Repository

Faqat DB operatsiyalari — biznes logika YO'Q.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.employee import (
    Employee, WorkerTask,
    EmployeeStatus, WorkerTaskStatus,
)
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class EmployeeRepository:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Employee CRUD ─────────────────────────────────────────────────────

    async def create_employee(self, emp: Employee) -> Employee:
        try:
            self.db.add(emp)
            await self.db.flush()
            await self.db.refresh(emp)
            return emp
        except Exception as e:
            raise DatabaseError(f"Xodim yaratishda xato: {e}")

    async def get_employee_by_id(self, emp_id: int) -> Optional[Employee]:
        try:
            result = await self.db.execute(
                select(Employee).where(Employee.id == emp_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError(f"Xodimni olishda xato: {e}")

    async def list_employees(
        self,
        farm_id:  Optional[int]          = None,
        status:   Optional[EmployeeStatus] = None,
        position: Optional[str]          = None,
        search:   Optional[str]          = None,
        page:     int = 1,
        size:     int = 20,
    ) -> tuple[list[Employee], int]:
        try:
            q = select(Employee)
            conditions = []

            if farm_id:
                conditions.append(Employee.farm_id == farm_id)
            if status:
                conditions.append(Employee.status == status)
            if position:
                conditions.append(Employee.position == position)
            if search:
                conditions.append(
                    or_(
                        Employee.full_name.ilike(f"%{search}%"),
                        Employee.phone.ilike(f"%{search}%"),
                    )
                )

            if conditions:
                q = q.where(and_(*conditions))

            total_q = select(func.count()).select_from(q.subquery())
            total   = await self.db.scalar(total_q) or 0

            q = q.order_by(Employee.full_name).offset((page - 1) * size).limit(size)
            result = await self.db.execute(q)
            return result.scalars().all(), total
        except Exception as e:
            raise DatabaseError(f"Xodimlar ro'yxatida xato: {e}")

    async def update_employee(self, emp: Employee) -> Employee:
        try:
            await self.db.flush()
            await self.db.refresh(emp)
            return emp
        except Exception as e:
            raise DatabaseError(f"Xodimni yangilashda xato: {e}")

    async def get_employee_stats(self) -> dict:
        try:
            total    = await self.db.scalar(select(func.count(Employee.id))) or 0
            active   = await self.db.scalar(select(func.count(Employee.id)).where(Employee.status == EmployeeStatus.ACTIVE)) or 0
            on_leave = await self.db.scalar(select(func.count(Employee.id)).where(Employee.status == EmployeeStatus.ON_LEAVE)) or 0
            inactive = await self.db.scalar(select(func.count(Employee.id)).where(Employee.status == EmployeeStatus.INACTIVE)) or 0

            # By position
            pos_q = await self.db.execute(
                select(Employee.position, func.count(Employee.id))
                .group_by(Employee.position)
            )
            by_position = {str(row[0]): row[1] for row in pos_q}

            # Tasks today
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
            today_end   = today_start + timedelta(days=1)
            tasks_today = await self.db.scalar(
                select(func.count(WorkerTask.id)).where(
                    and_(
                        WorkerTask.due_date >= today_start,
                        WorkerTask.due_date < today_end,
                        WorkerTask.status.notin_([WorkerTaskStatus.CANCELLED]),
                    )
                )
            ) or 0

            overdue = await self.db.scalar(
                select(func.count(WorkerTask.id)).where(
                    WorkerTask.status == WorkerTaskStatus.OVERDUE
                )
            ) or 0

            return {
                "total": total, "active": active,
                "on_leave": on_leave, "inactive": inactive,
                "by_position": by_position,
                "tasks_today": tasks_today, "overdue_tasks": overdue,
            }
        except Exception as e:
            raise DatabaseError(f"Statistikada xato: {e}")

    async def get_task_counts_for_employee(self, emp_id: int) -> dict:
        try:
            open_cnt = await self.db.scalar(
                select(func.count(WorkerTask.id)).where(
                    and_(
                        WorkerTask.employee_id == emp_id,
                        WorkerTask.status.in_([
                            WorkerTaskStatus.PENDING,
                            WorkerTaskStatus.IN_PROGRESS,
                        ])
                    )
                )
            ) or 0
            done_cnt = await self.db.scalar(
                select(func.count(WorkerTask.id)).where(
                    and_(
                        WorkerTask.employee_id == emp_id,
                        WorkerTask.status == WorkerTaskStatus.COMPLETED,
                    )
                )
            ) or 0
            overdue_cnt = await self.db.scalar(
                select(func.count(WorkerTask.id)).where(
                    and_(
                        WorkerTask.employee_id == emp_id,
                        WorkerTask.status == WorkerTaskStatus.OVERDUE,
                    )
                )
            ) or 0
            return {"open": open_cnt, "completed": done_cnt, "overdue": overdue_cnt}
        except Exception as e:
            raise DatabaseError(f"Vazifa hisoblashda xato: {e}")

    # ── WorkerTask CRUD ───────────────────────────────────────────────────

    async def create_task(self, task: WorkerTask) -> WorkerTask:
        try:
            self.db.add(task)
            await self.db.flush()
            await self.db.refresh(task)
            return task
        except Exception as e:
            raise DatabaseError(f"Vazifa yaratishda xato: {e}")

    async def get_task_by_id(self, task_id: int) -> Optional[WorkerTask]:
        try:
            result = await self.db.execute(
                select(WorkerTask)
                .options(selectinload(WorkerTask.employee))
                .where(WorkerTask.id == task_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError(f"Vazifani olishda xato: {e}")

    async def list_tasks(
        self,
        employee_id: Optional[int]             = None,
        status:      Optional[WorkerTaskStatus] = None,
        task_type:   Optional[str]             = None,
        priority:    Optional[str]             = None,
        overdue_only: bool                     = False,
        page:        int = 1,
        size:        int = 20,
    ) -> tuple[list[WorkerTask], int]:
        try:
            q = select(WorkerTask).options(selectinload(WorkerTask.employee))
            conditions = []

            if employee_id:
                conditions.append(WorkerTask.employee_id == employee_id)
            if status:
                conditions.append(WorkerTask.status == status)
            if task_type:
                conditions.append(WorkerTask.task_type == task_type)
            if priority:
                conditions.append(WorkerTask.priority == priority)
            if overdue_only:
                conditions.append(WorkerTask.status == WorkerTaskStatus.OVERDUE)

            if conditions:
                q = q.where(and_(*conditions))

            total_q = select(func.count()).select_from(q.subquery())
            total   = await self.db.scalar(total_q) or 0

            q = q.order_by(WorkerTask.due_date.asc().nulls_last()).offset((page - 1) * size).limit(size)
            result = await self.db.execute(q)
            return result.scalars().all(), total
        except Exception as e:
            raise DatabaseError(f"Vazifalar ro'yxatida xato: {e}")

    async def update_task(self, task: WorkerTask) -> WorkerTask:
        try:
            await self.db.flush()
            await self.db.refresh(task)
            return task
        except Exception as e:
            raise DatabaseError(f"Vazifani yangilashda xato: {e}")

    async def get_task_stats(self, employee_id: Optional[int] = None) -> dict:
        try:
            base = select(func.count(WorkerTask.id))
            if employee_id:
                base = base.where(WorkerTask.employee_id == employee_id)

            total       = await self.db.scalar(base) or 0
            pending     = await self.db.scalar(base.where(WorkerTask.status == WorkerTaskStatus.PENDING)) or 0
            in_progress = await self.db.scalar(base.where(WorkerTask.status == WorkerTaskStatus.IN_PROGRESS)) or 0
            completed   = await self.db.scalar(base.where(WorkerTask.status == WorkerTaskStatus.COMPLETED)) or 0
            overdue     = await self.db.scalar(base.where(WorkerTask.status == WorkerTaskStatus.OVERDUE)) or 0
            cancelled   = await self.db.scalar(base.where(WorkerTask.status == WorkerTaskStatus.CANCELLED)) or 0
            needs_verif = await self.db.scalar(
                base.where(
                    and_(
                        WorkerTask.requires_verification == True,
                        WorkerTask.verification_status == "unverified",
                        WorkerTask.status == WorkerTaskStatus.COMPLETED,
                    )
                )
            ) or 0

            done_total = completed + cancelled
            rate = round((completed / done_total * 100) if done_total > 0 else 0, 1)

            return {
                "total": total, "pending": pending, "in_progress": in_progress,
                "completed": completed, "overdue": overdue, "cancelled": cancelled,
                "needs_verification": needs_verif, "completion_rate": rate,
            }
        except Exception as e:
            raise DatabaseError(f"Vazifa statistikasida xato: {e}")

    async def mark_overdue_tasks(self) -> int:
        """Muddati o'tgan vazifalarni OVERDUE ga o'tkazish."""
        try:
            now = datetime.now(timezone.utc)
            result = await self.db.execute(
                select(WorkerTask).where(
                    and_(
                        WorkerTask.due_date < now,
                        WorkerTask.status.in_([
                            WorkerTaskStatus.PENDING,
                            WorkerTaskStatus.IN_PROGRESS,
                        ])
                    )
                )
            )
            tasks = result.scalars().all()
            for t in tasks:
                t.status = WorkerTaskStatus.OVERDUE
            await self.db.flush()
            return len(tasks)
        except Exception as e:
            raise DatabaseError(f"Overdue belgilashda xato: {e}")
