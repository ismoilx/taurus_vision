"""
Taurus Vision — Farm Task Repository (Sprint 19-20)

Faqat DB operatsiyalari — biznes logika YO'Q.
FarmTaskService bu repository orqali DB bilan ishlaydi.

PATTERN:
    Service → Repository → SQLAlchemy → PostgreSQL
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, and_, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.farm_task import FarmTask, TaskStatus, TaskPriority, TaskType
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class FarmTaskRepository:
    """
    Farm task entity uchun DB operatsiyalari.

    Args:
        db: AsyncSession injected via FastAPI Depends()

    Example:
        repo = FarmTaskRepository(db)
        tasks = await repo.get_open_tasks(assigned_to=3)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create(self, task: FarmTask) -> FarmTask:
        """
        Yangi vazifani DB ga saqlash.

        Args:
            task: To'ldirilgan FarmTask instance

        Returns:
            Saqlangan FarmTask (id bilan)

        Raises:
            DatabaseError: DB xatosi bo'lsa
        """
        try:
            self.db.add(task)
            await self.db.flush()
            await self.db.refresh(task)
            logger.debug(
                f"[task_repo] Created task: id={task.id} "
                f"type={task.task_type} priority={task.priority}"
            )
            return task
        except Exception as exc:
            logger.error(f"[task_repo] create failed: {exc}", exc_info=True)
            raise DatabaseError(f"FarmTask yaratishda xato: {exc}") from exc

    # =========================================================================
    # READ
    # =========================================================================

    async def get_by_id(self, task_id: int) -> Optional[FarmTask]:
        """ID bo'yicha bitta vazifa."""
        result = await self.db.execute(
            select(FarmTask).where(FarmTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(self, task_id: int) -> Optional[FarmTask]:
        """ID bo'yicha vazifa + animal + assignee (eager load)."""
        result = await self.db.execute(
            select(FarmTask)
            .options(
                selectinload(FarmTask.animal),
                selectinload(FarmTask.assignee),
            )
            .where(FarmTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        *,
        status: Optional[list[TaskStatus]] = None,
        task_type: Optional[TaskType] = None,
        priority: Optional[TaskPriority] = None,
        animal_id: Optional[int] = None,
        assigned_to: Optional[int] = None,
        overdue_only: bool = False,
        due_today: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[FarmTask], int]:
        """
        Filtr bilan vazifalar ro'yxati.

        Returns:
            (items, total_count) tuple
        """
        filters = []

        if status:
            filters.append(FarmTask.status.in_(status))

        if task_type:
            filters.append(FarmTask.task_type == task_type)

        if priority:
            filters.append(FarmTask.priority == priority)

        if animal_id is not None:
            filters.append(FarmTask.animal_id == animal_id)

        if assigned_to is not None:
            filters.append(FarmTask.assigned_to == assigned_to)

        if overdue_only:
            now = datetime.now(timezone.utc)
            filters.append(
                and_(
                    FarmTask.due_date < now,
                    FarmTask.status.in_([
                        TaskStatus.PENDING,
                        TaskStatus.IN_PROGRESS,
                    ]),
                )
            )

        if due_today:
            now = datetime.now(timezone.utc)
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end   = start + timedelta(days=1)
            filters.append(
                and_(
                    FarmTask.due_date >= start,
                    FarmTask.due_date < end,
                )
            )

        where_clause = and_(*filters) if filters else True

        # Count
        count_result = await self.db.execute(
            select(func.count(FarmTask.id)).where(where_clause)
        )
        total = count_result.scalar_one()

        # Items — priority CRITICAL→LOW, due_date asc
        priority_order = {
            TaskPriority.CRITICAL: 0,
            TaskPriority.HIGH:     1,
            TaskPriority.MEDIUM:   2,
            TaskPriority.LOW:      3,
        }

        result = await self.db.execute(
            select(FarmTask)
            .where(where_clause)
            .order_by(
                # NULL due_date oxirida
                FarmTask.due_date.asc().nulls_last(),
                FarmTask.priority.asc(),
                FarmTask.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        items = list(result.scalars().all())

        return items, total

    async def get_overdue_tasks(self) -> list[FarmTask]:
        """
        Muddati o'tib ketgan, hali yopilmagan vazifalar.
        Celery task tomonidan status ni OVERDUE ga o'zgartirish uchun.
        """
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(FarmTask)
            .where(
                and_(
                    FarmTask.due_date < now,
                    FarmTask.status.in_([
                        TaskStatus.PENDING,
                        TaskStatus.IN_PROGRESS,
                    ]),
                )
            )
            .order_by(FarmTask.due_date.asc())
        )
        return list(result.scalars().all())

    async def get_due_soon(self, within_hours: int = 24) -> list[FarmTask]:
        """Yaqin soatlar ichida muddati tugaydigan vazifalar."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=within_hours)
        result = await self.db.execute(
            select(FarmTask)
            .where(
                and_(
                    FarmTask.due_date.between(now, cutoff),
                    FarmTask.status.in_([
                        TaskStatus.PENDING,
                        TaskStatus.IN_PROGRESS,
                    ]),
                )
            )
            .order_by(FarmTask.due_date.asc())
        )
        return list(result.scalars().all())

    async def get_for_animal(
        self,
        animal_id: int,
        status: Optional[list[TaskStatus]] = None,
        limit: int = 20,
    ) -> list[FarmTask]:
        """Bitta jonivorga tegishli vazifalar."""
        filters = [FarmTask.animal_id == animal_id]
        if status:
            filters.append(FarmTask.status.in_(status))

        result = await self.db.execute(
            select(FarmTask)
            .where(and_(*filters))
            .order_by(FarmTask.due_date.asc().nulls_last())
            .limit(limit)
        )
        return list(result.scalars().all())

    # =========================================================================
    # UPDATE
    # =========================================================================

    async def save(self, task: FarmTask) -> FarmTask:
        """O'zgartirilgan task ni flush + refresh."""
        try:
            await self.db.flush()
            await self.db.refresh(task)
            return task
        except Exception as exc:
            logger.error(f"[task_repo] save failed: {exc}", exc_info=True)
            raise DatabaseError(f"FarmTask saqlashda xato: {exc}") from exc

    async def bulk_mark_overdue(self, task_ids: list[int]) -> int:
        """
        Bir nechta vazifani OVERDUE ga o'zgartirish.

        Returns:
            O'zgartirilgan qatorlar soni
        """
        if not task_ids:
            return 0

        result = await self.db.execute(
            update(FarmTask)
            .where(FarmTask.id.in_(task_ids))
            .values(
                status=TaskStatus.OVERDUE,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(FarmTask.id)
        )
        updated = len(result.fetchall())
        logger.info(f"[task_repo] bulk_mark_overdue: {updated} tasks updated")
        return updated

    # =========================================================================
    # STATISTICS
    # =========================================================================

    async def get_stats(self) -> dict:
        """
        Dashboard uchun vazifa statistikasi.

        Returns:
            {
                open: int, overdue: int, today: int,
                completed_today: int,
                by_priority: {...}, by_type: {...}
            }
        """
        now   = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)

        open_statuses = [
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.OVERDUE,
        ]

        # Ochiq vazifalar soni
        open_count = await self.db.scalar(
            select(func.count(FarmTask.id))
            .where(FarmTask.status.in_(open_statuses))
        ) or 0

        # Muddati o'tganlar
        overdue_count = await self.db.scalar(
            select(func.count(FarmTask.id))
            .where(
                or_(
                    FarmTask.status == TaskStatus.OVERDUE,
                    and_(
                        FarmTask.due_date < now,
                        FarmTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                    ),
                )
            )
        ) or 0

        # Bugun muddati
        today_count = await self.db.scalar(
            select(func.count(FarmTask.id))
            .where(
                and_(
                    FarmTask.due_date >= today,
                    FarmTask.due_date < tomorrow,
                    FarmTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                )
            )
        ) or 0

        # Bugun bajarilgan
        completed_today = await self.db.scalar(
            select(func.count(FarmTask.id))
            .where(
                and_(
                    FarmTask.completed_at >= today,
                    FarmTask.completed_at < tomorrow,
                    FarmTask.status == TaskStatus.COMPLETED,
                )
            )
        ) or 0

        # Priority bo'yicha (faqat ochiq)
        priority_rows = await self.db.execute(
            select(FarmTask.priority, func.count(FarmTask.id))
            .where(FarmTask.status.in_(open_statuses))
            .group_by(FarmTask.priority)
        )
        by_priority = {row[0]: row[1] for row in priority_rows.fetchall()}

        # Tur bo'yicha (faqat ochiq)
        type_rows = await self.db.execute(
            select(FarmTask.task_type, func.count(FarmTask.id))
            .where(FarmTask.status.in_(open_statuses))
            .group_by(FarmTask.task_type)
        )
        by_type = {row[0]: row[1] for row in type_rows.fetchall()}

        # CRITICAL/HIGH overdue (max 5 ta — dashboard warning uchun)
        critical_overdue_result = await self.db.execute(
            select(FarmTask)
            .where(
                and_(
                    FarmTask.status.in_([
                        TaskStatus.OVERDUE,
                        TaskStatus.PENDING,
                        TaskStatus.IN_PROGRESS,
                    ]),
                    FarmTask.priority.in_([
                        TaskPriority.CRITICAL,
                        TaskPriority.HIGH,
                    ]),
                    or_(
                        FarmTask.status == TaskStatus.OVERDUE,
                        FarmTask.due_date < now,
                    ),
                )
            )
            .order_by(FarmTask.priority.asc(), FarmTask.due_date.asc())
            .limit(5)
        )
        critical_overdue = list(critical_overdue_result.scalars().all())

        return {
            "total_open":            open_count,
            "total_overdue":         overdue_count,
            "total_today":           today_count,
            "total_completed_today": completed_today,
            "by_priority":           by_priority,
            "by_type":               by_type,
            "critical_overdue":      critical_overdue,
        }