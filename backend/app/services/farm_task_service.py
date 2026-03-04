"""
Taurus Vision — Farm Task Service (Sprint 19-20)

Ferma vazifalari boshqaruvi — barcha biznes mantiq shu yerda.

JAVOBGARLIK:
    - Vazifa yaratish, yangilash, o'chirish
    - Holat o'tish qoidalari (status transition validation)
    - Overdue detection va alert integratsiyasi
    - Animal va User mavjudligini tekshirish
    - Statistika hisoblash

ARXITEKTURA:
    API endpoint (tasks.py)
        ↓
    FarmTaskService   ← bu fayl
        ↓
    FarmTaskRepository → PostgreSQL
        ↓
    AlertService (overdue uchun)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.farm_task import FarmTask, TaskStatus, TaskPriority, TaskType
from app.models.animal import Animal
from app.models.user import User
from app.repositories.farm_task_repository import FarmTaskRepository
from app.schemas.farm_task import (
    FarmTaskCreate,
    FarmTaskUpdate,
    FarmTaskComplete,
    FarmTaskResponse,
    FarmTaskListResponse,
    FarmTaskSummary,
    TaskStats,
)
from app.core.exceptions import (
    EntityNotFoundError,
    BusinessRuleViolationError,
    DatabaseError,
)

logger = logging.getLogger(__name__)

# Status o'tish matritsasi: qaysi statusdan qaysi statusga o'tish mumkin
ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING:     {TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, TaskStatus.CANCELLED},
    TaskStatus.IN_PROGRESS: {TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.PENDING},
    TaskStatus.OVERDUE:     {TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED:   set(),   # Terminal holat — o'zgartirib bo'lmaydi
    TaskStatus.CANCELLED:   {TaskStatus.PENDING},  # Qayta ochish mumkin
}


class FarmTaskService:
    """
    Farm task management servisi.

    Usage:
        service = FarmTaskService(db)
        task = await service.create_task(data, created_by=user.id)
        await service.complete_task(task_id=1, data=completion, user_id=3)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db   = db
        self._repo = FarmTaskRepository(db)

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create_task(
        self,
        data: FarmTaskCreate,
        created_by: Optional[int] = None,
    ) -> FarmTaskResponse:
        """
        Yangi vazifa yaratish.

        Animal va assigned_to mavjudligi tekshiriladi.

        Args:
            data:       FarmTaskCreate payload
            created_by: Yaratuvchi user ID (JWT dan)

        Returns:
            FarmTaskResponse

        Raises:
            EntityNotFoundError:       animal_id yoki assigned_to topilmasa
            BusinessRuleViolationError: noto'g'ri ma'lumot
        """
        # Animal mavjudligini tekshirish
        if data.animal_id is not None:
            animal = await self.db.get(Animal, data.animal_id)
            if animal is None:
                raise EntityNotFoundError(f"Jonivor ID={data.animal_id} topilmadi.")

        # Bajaruvchi mavjudligini tekshirish
        if data.assigned_to is not None:
            user = await self.db.get(User, data.assigned_to)
            if user is None:
                raise EntityNotFoundError(f"Foydalanuvchi ID={data.assigned_to} topilmadi.")

        task = FarmTask(
            title       = data.title,
            description = data.description,
            task_type   = data.task_type,
            priority    = data.priority,
            status      = TaskStatus.PENDING,
            due_date    = data.due_date,
            animal_id   = data.animal_id,
            assigned_to = data.assigned_to,
            created_by  = created_by,
            meta        = data.meta,
        )

        saved = await self._repo.create(task)
        await self.db.commit()

        logger.info(
            f"[task_svc] Task created | id={saved.id} | "
            f"type={saved.task_type} | priority={saved.priority} | "
            f"animal={saved.animal_id} | by={created_by}"
        )

        # CRITICAL vazifa yaratilsa alert
        if saved.priority == TaskPriority.CRITICAL and saved.due_date:
            await self._create_task_alert(saved)

        return self._to_response(saved)

    # =========================================================================
    # READ
    # =========================================================================

    async def get_task(self, task_id: int) -> FarmTaskResponse:
        """
        Bitta vazifani ID bo'yicha olish.

        Raises:
            EntityNotFoundError: topilmasa
        """
        task = await self._repo.get_by_id_with_relations(task_id)
        if task is None:
            raise EntityNotFoundError(f"Vazifa ID={task_id} topilmadi.")
        return self._to_response(task)

    async def get_tasks(
        self,
        *,
        status: Optional[list[TaskStatus]] = None,
        task_type: Optional[TaskType] = None,
        priority: Optional[TaskPriority] = None,
        animal_id: Optional[int] = None,
        assigned_to: Optional[int] = None,
        overdue_only: bool = False,
        due_today: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> FarmTaskListResponse:
        """Filtr va sahifalash bilan vazifalar ro'yxati."""
        page_size = min(page_size, 100)
        offset    = (page - 1) * page_size

        items, total = await self._repo.get_list(
            status      = status,
            task_type   = task_type,
            priority    = priority,
            animal_id   = animal_id,
            assigned_to = assigned_to,
            overdue_only= overdue_only,
            due_today   = due_today,
            limit       = page_size,
            offset      = offset,
        )

        total_pages = max(1, -(-total // page_size))  # ceiling division

        return FarmTaskListResponse(
            items       = [self._to_summary(t) for t in items],
            total       = total,
            page        = page,
            page_size   = page_size,
            total_pages = total_pages,
        )

    async def get_animal_tasks(
        self,
        animal_id: int,
        open_only: bool = True,
    ) -> list[FarmTaskSummary]:
        """Bitta jonivorga tegishli vazifalar."""
        status = None
        if open_only:
            status = [TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE]

        tasks = await self._repo.get_for_animal(animal_id, status=status)
        return [self._to_summary(t) for t in tasks]

    async def get_stats(self) -> TaskStats:
        """Dashboard uchun statistika."""
        raw = await self._repo.get_stats()
        return TaskStats(
            total_open            = raw["total_open"],
            total_overdue         = raw["total_overdue"],
            total_today           = raw["total_today"],
            total_completed_today = raw["total_completed_today"],
            by_priority           = raw["by_priority"],
            by_type               = raw["by_type"],
            critical_overdue      = [self._to_summary(t) for t in raw["critical_overdue"]],
        )

    # =========================================================================
    # UPDATE
    # =========================================================================

    async def update_task(
        self,
        task_id: int,
        data: FarmTaskUpdate,
        user_id: Optional[int] = None,
    ) -> FarmTaskResponse:
        """
        Vazifani yangilash.

        Status o'zgarishi ALLOWED_TRANSITIONS ga ko'ra tekshiriladi.

        Raises:
            EntityNotFoundError:       topilmasa
            BusinessRuleViolationError: noto'g'ri status transition
        """
        task = await self._repo.get_by_id(task_id)
        if task is None:
            raise EntityNotFoundError(f"Vazifa ID={task_id} topilmadi.")

        # Status transition tekshirish
        if data.status is not None and data.status != task.status:
            allowed = ALLOWED_TRANSITIONS.get(task.status, set())
            if data.status not in allowed:
                raise BusinessRuleViolationError(
                    f"'{task.status}' → '{data.status}' o'tish mumkin emas. "
                    f"Ruxsat etilgan: {[s.value for s in allowed] or 'hech narsa'}"
                )
            # started_at ni to'ldirish
            if data.status == TaskStatus.IN_PROGRESS and task.started_at is None:
                task.started_at = datetime.now(timezone.utc)

        # Assigned_to mavjudligi
        if data.assigned_to is not None:
            user = await self.db.get(User, data.assigned_to)
            if user is None:
                raise EntityNotFoundError(f"Foydalanuvchi ID={data.assigned_to} topilmadi.")

        # Maydonlarni yangilash
        update_data = data.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(task, field, value)

        saved = await self._repo.save(task)
        await self.db.commit()

        logger.info(
            f"[task_svc] Task updated | id={task_id} | "
            f"changes={list(update_data.keys())} | by={user_id}"
        )

        return self._to_response(saved)

    async def complete_task(
        self,
        task_id: int,
        data: FarmTaskComplete,
        user_id: Optional[int] = None,
    ) -> FarmTaskResponse:
        """
        Vazifani COMPLETED deb belgilash.

        Raises:
            EntityNotFoundError:       topilmasa
            BusinessRuleViolationError: allaqachon completed yoki cancelled
        """
        task = await self._repo.get_by_id(task_id)
        if task is None:
            raise EntityNotFoundError(f"Vazifa ID={task_id} topilmadi.")

        if task.status == TaskStatus.COMPLETED:
            raise BusinessRuleViolationError("Vazifa allaqachon bajarilgan.")
        if task.status == TaskStatus.CANCELLED:
            raise BusinessRuleViolationError("Bekor qilingan vazifani bajarilgan deb belgilab bo'lmaydi.")

        now = datetime.now(timezone.utc)

        task.status       = TaskStatus.COMPLETED
        task.completed_at = now
        task.notes        = data.notes or task.notes

        if data.meta:
            task.meta = {**(task.meta or {}), **data.meta}

        if task.started_at is None:
            task.started_at = now

        saved = await self._repo.save(task)
        await self.db.commit()

        logger.info(
            f"[task_svc] Task completed | id={task_id} | "
            f"type={task.task_type} | by={user_id}"
        )

        return self._to_response(saved)

    async def cancel_task(
        self,
        task_id: int,
        reason: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> FarmTaskResponse:
        """
        Vazifani bekor qilish.

        Raises:
            EntityNotFoundError:       topilmasa
            BusinessRuleViolationError: completed bo'lsa
        """
        task = await self._repo.get_by_id(task_id)
        if task is None:
            raise EntityNotFoundError(f"Vazifa ID={task_id} topilmadi.")

        if task.status == TaskStatus.COMPLETED:
            raise BusinessRuleViolationError("Bajarilgan vazifani bekor qilib bo'lmaydi.")

        task.status = TaskStatus.CANCELLED
        if reason:
            task.notes = reason

        saved = await self._repo.save(task)
        await self.db.commit()

        logger.info(f"[task_svc] Task cancelled | id={task_id} | by={user_id}")

        return self._to_response(saved)

    # =========================================================================
    # CELERY — overdue check
    # =========================================================================

    async def mark_overdue_tasks(self) -> dict:
        """
        Muddati o'tgan PENDING/IN_PROGRESS vazifalarni OVERDUE ga o'zgartirish.
        Celery task tomonidan har 30 daqiqada chaqiriladi.

        Returns:
            {"marked": int, "alerts_created": int}
        """
        overdue_tasks = await self._repo.get_overdue_tasks()

        # Hali OVERDUE statusida bo'lmagan (PENDING/IN_PROGRESS) larni ajratish
        to_mark = [
            t for t in overdue_tasks
            if t.status != TaskStatus.OVERDUE
        ]

        if not to_mark:
            return {"marked": 0, "alerts_created": 0}

        task_ids = [t.id for t in to_mark]
        marked   = await self._repo.bulk_mark_overdue(task_ids)

        # Alert yaratish (HIGH+ lar uchun)
        alert_count = 0
        for task in to_mark:
            if task.priority in (TaskPriority.CRITICAL, TaskPriority.HIGH):
                try:
                    await self._create_overdue_alert(task)
                    alert_count += 1
                except Exception as exc:
                    logger.error(
                        f"[task_svc] Overdue alert xatosi: task={task.id} | {exc}"
                    )

        await self.db.commit()

        logger.warning(
            f"[task_svc] Overdue check | marked={marked} | alerts={alert_count}"
        )

        return {"marked": marked, "alerts_created": alert_count}

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _to_response(self, task: FarmTask) -> FarmTaskResponse:
        """FarmTask → FarmTaskResponse."""
        resp = FarmTaskResponse.model_validate(task)
        resp.is_overdue = task.is_overdue
        return resp

    def _to_summary(self, task: FarmTask) -> FarmTaskSummary:
        """FarmTask → FarmTaskSummary."""
        s = FarmTaskSummary.model_validate(task)
        s.is_overdue = task.is_overdue
        return s

    async def _create_task_alert(self, task: FarmTask) -> None:
        """CRITICAL vazifa yaratilganda ogohlantirish."""
        try:
            from app.services.alert_service import AlertService
            from app.models.alert import AlertType, AlertSeverity

            alert_svc = AlertService(self.db)
            due_str = (
                task.due_date.strftime("%Y-%m-%d %H:%M UTC")
                if task.due_date else "muddatsiz"
            )
            await alert_svc._ensure_alert(
                animal_id   = task.animal_id,
                alert_type  = AlertType.CUSTOM,
                title       = f"Kritik vazifa: {task.title}",
                description = (
                    f"Kritik muhimlikdagi vazifa yaratildi. "
                    f"Tur: {task.task_type.value}. "
                    f"Muddat: {due_str}."
                ),
                severity    = AlertSeverity.HIGH,
                context     = {
                    "task_id":   task.id,
                    "task_type": task.task_type.value,
                    "due_date":  task.due_date.isoformat() if task.due_date else None,
                    "source":    "task_service",
                },
            )
        except Exception as exc:
            logger.error(f"[task_svc] Critical task alert xatosi: {exc}")

    async def _create_overdue_alert(self, task: FarmTask) -> None:
        """Muddati o'tgan HIGH/CRITICAL vazifa uchun ogohlantirish."""
        try:
            from app.services.alert_service import AlertService
            from app.models.alert import AlertType, AlertSeverity

            severity = (
                AlertSeverity.CRITICAL
                if task.priority == TaskPriority.CRITICAL
                else AlertSeverity.HIGH
            )

            alert_svc = AlertService(self.db)
            await alert_svc._ensure_alert(
                animal_id   = task.animal_id,
                alert_type  = AlertType.CUSTOM,
                title       = f"Vazifa muddati o'tdi: {task.title}",
                description = (
                    f"'{task.task_type.value}' turi vazifaning muddati o'tib ketdi. "
                    f"Bajaruvchi: {task.assigned_to or 'tayinlanmagan'}."
                ),
                severity    = severity,
                context     = {
                    "task_id":   task.id,
                    "task_type": task.task_type.value,
                    "due_date":  task.due_date.isoformat() if task.due_date else None,
                    "source":    "task_overdue_check",
                },
            )
        except Exception as exc:
            logger.error(f"[task_svc] Overdue alert xatosi: {exc}")