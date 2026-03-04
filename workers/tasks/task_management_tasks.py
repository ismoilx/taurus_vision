"""
Taurus Vision — Farm Task Celery Tasks (Sprint 19-20)

Ferma vazifalari uchun avtomatik background tasklar.

TASKLAR:
    tasks.mark_overdue      — Har 30 daqiqada: PENDING/IN_PROGRESS → OVERDUE
    tasks.remind_due_soon   — Har soatda: 24 soatda muddati tugaydigan vazifalar uchun ogohlantirish
    tasks.daily_task_report — Har kecha 06:00: kunlik vazifa xulosasi (email)

QUEUE:
    default — barcha task management tasklar (yengil)

INTEGRATSIYA:
    FarmTaskService → FarmTaskRepository → PostgreSQL
    AlertService    → alert yaratish (HIGH/CRITICAL overdue uchun)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from workers.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


# =============================================================================
# TASK 1: OVERDUE MARK — har 30 daqiqada
# =============================================================================

@celery_app.task(
    bind=True,
    name="tasks.mark_overdue",
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=120,
    time_limit=180,
    acks_late=True,
)
def mark_overdue_tasks(self) -> dict:
    """
    Muddati o'tib ketgan PENDING/IN_PROGRESS vazifalarni OVERDUE ga o'zgartirish.

    HIGH va CRITICAL overdue uchun avtomatik alert yaratiladi.

    Returns:
        {"marked": int, "alerts_created": int}
    """
    import asyncio
    import concurrent.futures

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, _mark_overdue_async())
            result = future.result()

        if result["marked"]:
            logger.warning(
                f"[tasks] Overdue marked | "
                f"count={result['marked']} | "
                f"alerts={result['alerts_created']}"
            )
        else:
            logger.debug("[tasks] Overdue check — nothing to mark")

        return result

    except Exception as exc:
        logger.error(f"[tasks] mark_overdue failed: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"marked": 0, "alerts_created": 0, "error": str(exc)}


async def _mark_overdue_async() -> dict:
    async with AsyncSessionLocal() as db:
        from app.services.farm_task_service import FarmTaskService
        svc = FarmTaskService(db)
        return await svc.mark_overdue_tasks()


# =============================================================================
# TASK 2: REMIND DUE SOON — har soatda
# =============================================================================

@celery_app.task(
    bind=True,
    name="tasks.remind_due_soon",
    max_retries=2,
    default_retry_delay=120,
    soft_time_limit=180,
    time_limit=240,
    acks_late=True,
)
def remind_due_soon(self) -> dict:
    """
    Kelasi 24 soatda muddati tugaydigan HIGH/CRITICAL vazifalar uchun
    ogohlantirish yaratish.

    Bu foydalanuvchiga muddatdan oldin ogohlantirishni ta'minlaydi.

    Returns:
        {"checked": int, "reminded": int}
    """
    import asyncio
    import concurrent.futures

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, _remind_due_soon_async())
            result = future.result()

        logger.info(
            f"[tasks] Due-soon check | "
            f"checked={result['checked']} | reminded={result['reminded']}"
        )
        return result

    except Exception as exc:
        logger.error(f"[tasks] remind_due_soon failed: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"checked": 0, "reminded": 0, "error": str(exc)}


async def _remind_due_soon_async() -> dict:
    """Yaqin muddatli HIGH/CRITICAL vazifalarga ogohlantirish."""
    reminded = 0

    async with AsyncSessionLocal() as db:
        from app.repositories.farm_task_repository import FarmTaskRepository
        from app.services.alert_service import AlertService
        from app.models.alert import AlertType, AlertSeverity
        from app.models.farm_task import TaskPriority

        repo      = FarmTaskRepository(db)
        alert_svc = AlertService(db)

        # Kelasi 24 soatda muddati tugaydigan vazifalar
        due_soon = await repo.get_due_soon(within_hours=24)
        checked  = len(due_soon)

        for task in due_soon:
            # Faqat HIGH va CRITICAL uchun ogohlantirish
            if task.priority not in (TaskPriority.HIGH, TaskPriority.CRITICAL):
                continue

            due_str = (
                task.due_date.strftime("%Y-%m-%d %H:%M UTC")
                if task.due_date else ""
            )

            try:
                await alert_svc._ensure_alert(
                    animal_id   = task.animal_id,
                    alert_type  = AlertType.CUSTOM,
                    title       = f"Vazifa muddati yaqin: {task.title}",
                    description = (
                        f"'{task.task_type.value}' vazifasining muddati "
                        f"{due_str} da tugaydi. "
                        f"Bajaruvchi: {task.assigned_to or 'tayinlanmagan'}."
                    ),
                    severity    = (
                        AlertSeverity.HIGH
                        if task.priority == TaskPriority.CRITICAL
                        else AlertSeverity.MEDIUM
                    ),
                    context={
                        "task_id":   task.id,
                        "task_type": task.task_type.value,
                        "due_date":  task.due_date.isoformat() if task.due_date else None,
                        "source":    "task_due_soon_reminder",
                    },
                )
                reminded += 1
            except Exception as e:
                logger.error(f"[tasks] Reminder alert xatosi: task={task.id} | {e}")

        await db.commit()

    return {"checked": checked, "reminded": reminded}


# =============================================================================
# TASK 3: KUNLIK XULOSA — har kecha 06:00
# =============================================================================

@celery_app.task(
    bind=True,
    name="tasks.daily_report",
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=300,
    time_limit=360,
    acks_late=True,
)
def daily_task_report(
    self,
    target_date: Optional[str] = None,
) -> dict:
    """
    Kunlik vazifa xulosasini hisoblash va log ga yozish.

    Bugungi bajarilgan, o'tgan, qolgan vazifalar soni.
    Kelajakda email notification bilan integratsiya qilinadi.

    Args:
        target_date: YYYY-MM-DD (None = bugun)

    Returns:
        Kunlik statistika dict
    """
    import asyncio
    import concurrent.futures

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, _daily_report_async(target_date))
            result = future.result()

        logger.info(
            f"[tasks] Daily report | "
            f"date={result.get('date')} | "
            f"completed={result.get('completed')} | "
            f"overdue={result.get('overdue')} | "
            f"pending={result.get('pending')}"
        )
        return result

    except Exception as exc:
        logger.error(f"[tasks] daily_report failed: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"error": str(exc)}


async def _daily_report_async(target_date: Optional[str]) -> dict:
    """Kunlik vazifa statistikasi."""
    from sqlalchemy import select, func, and_
    from datetime import timedelta

    now      = datetime.now(timezone.utc)
    date_str = target_date or now.strftime("%Y-%m-%d")

    today    = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    async with AsyncSessionLocal() as db:
        from app.models.farm_task import FarmTask, TaskStatus

        # Bugun bajarilgan
        completed = await db.scalar(
            select(func.count(FarmTask.id)).where(
                and_(
                    FarmTask.completed_at >= today,
                    FarmTask.completed_at < tomorrow,
                    FarmTask.status == TaskStatus.COMPLETED,
                )
            )
        ) or 0

        # Hozir overdue
        overdue = await db.scalar(
            select(func.count(FarmTask.id)).where(
                FarmTask.status == TaskStatus.OVERDUE
            )
        ) or 0

        # Hozir pending
        pending = await db.scalar(
            select(func.count(FarmTask.id)).where(
                FarmTask.status == TaskStatus.PENDING
            )
        ) or 0

        # Hozir in_progress
        in_progress = await db.scalar(
            select(func.count(FarmTask.id)).where(
                FarmTask.status == TaskStatus.IN_PROGRESS
            )
        ) or 0

        # Ertaga muddati tugaydigan
        due_tomorrow_start = tomorrow
        due_tomorrow_end   = tomorrow + timedelta(days=1)
        due_tomorrow = await db.scalar(
            select(func.count(FarmTask.id)).where(
                and_(
                    FarmTask.due_date >= due_tomorrow_start,
                    FarmTask.due_date < due_tomorrow_end,
                    FarmTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                )
            )
        ) or 0

    return {
        "date":        date_str,
        "completed":   completed,
        "overdue":     overdue,
        "pending":     pending,
        "in_progress": in_progress,
        "due_tomorrow": due_tomorrow,
    }