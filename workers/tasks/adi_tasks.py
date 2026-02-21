"""
ADI Celery Tasks — Avtomatik scheduled vazifalar.

TASKS:
    calculate_daily_adi         — Har kecha 00:30 UTC: barcha jonivorlar ADI
    check_missing_animals       — Har soat: ko'rinmayotganlarni tekshirish
    check_growth_stagnation     — Har haftada: o'sish to'xtagan jonivorlar
    cleanup_old_alerts          — Har haftada: eski yopilgan alertlarni tozalash

CELERY BEAT SCHEDULE:
    Bu faylni celery_app.py ga import qilish kerak.
    Schedule celery_app.py da CELERY_BEAT_SCHEDULE orqali sozlanadi.

XATO BOSHQARISH:
    - Har bir task mustaqil — biri xato qilsa, boshqasi davom etadi
    - Retry: 3 marta, exponential backoff
    - Barcha xatolar log ga yoziladi
    - Kritik xatolarda alert yaratiladi
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from celery import Task
from sqlalchemy import select

from workers.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.animal import Animal, AnimalStatus
from app.models.adi_log import ADILog
from app.models.alert import Alert, AlertStatus

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Base Task: DB session boshqarish                                    #
# ------------------------------------------------------------------ #

class DatabaseTask(Task):
    """
    Base task classi — async DB session ni sync Celery bilan ko'prik.

    Celery sync muhitda ishlaydi, bizning servislar async.

    PYTHON 3.12 MUAMMO:
        asyncio.get_event_loop() — deprecated va ishonchsiz.
        ThreadPoolExecutor ichida asyncio.run() — deadlock xavfi.

    TO'G'RI YECHIM:
        Har doim alohida thread yaratib, u yerda asyncio.run() chaqirish.
        Bu Celery worker thread dan to'liq izolyatsiyani ta'minlaydi.
    """
    abstract = True

    def run_async(self, coro) -> object:
        """
        Async coroutine ni sync Celery muhitda xavfsiz ishlatish.

        Har doim yangi thread + yangi event loop ishlatiladi.
        Bu Python 3.10+ va 3.12 da to'liq xavfsiz.

        Args:
            coro: Await qilinadigan coroutine

        Returns:
            Coroutine natijasi

        Raises:
            Exception: Coroutine ichidagi har qanday xato yuqoriga uzatiladi
        """
        import asyncio
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()


# ================================================================ #
# TASK 1: KUNLIK ADI HISOBLASH                                      #
# ================================================================ #

@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="adi.calculate_daily",
    max_retries=3,
    default_retry_delay=300,        # 5 daqiqa kutib qayta urinish
    soft_time_limit=3600,           # 1 soat soft limit
    time_limit=4200,                # 1 soat 10 daqiqa hard limit
    acks_late=True,                 # Task muvaffaqiyatli tugagach ACK
)
def calculate_daily_adi(
    self,
    target_date: Optional[str] = None,
    force_recalculate: bool = False,
) -> dict:
    """
    Barcha aktiv jonivorlar uchun kunlik ADI hisoblash.

    Har kecha 00:30 UTC da ishga tushadi.
    Buning uchun vaqt tanlangan: tungi soatda kamera
    faolligi past, DB load minimal.

    Args:
        target_date:       YYYY-MM-DD (None = bugun)
        force_recalculate: True = mavjud yozuvni qayta hisoblash

    Returns:
        {
            "date": str,
            "total": int,
            "success": int,
            "failed": int,
            "duration_seconds": float,
            "farm_summary": dict
        }
    """
    return self.run_async(
        _calculate_daily_adi_async(
            task=self,
            target_date=target_date,
            force_recalculate=force_recalculate,
        )
    )


async def _calculate_daily_adi_async(
    task,
    target_date: Optional[str],
    force_recalculate: bool,
) -> dict:
    """calculate_daily_adi ning async implementatsiyasi."""
    import time
    start_time = time.monotonic()

    date_str = target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info(
        f"Daily ADI calculation started | date={date_str} | "
        f"force={force_recalculate}"
    )

    success_count  = 0
    failed_count   = 0
    failed_animals = []

    async with AsyncSessionLocal() as db:
        from app.services.adi_service import ADIService
        from app.services.alert_service import AlertService

        adi_service   = ADIService(db)
        alert_service = AlertService(db)

        # Aktiv jonivorlar
        stmt = select(Animal).where(Animal.status == AnimalStatus.ACTIVE)
        result = await db.execute(stmt)
        animals = list(result.scalars().all())

        logger.info(f"Processing {len(animals)} active animals")

        for animal in animals:
            try:
                # Kechagi scoreini olish (trend uchun)
                yesterday = (
                    datetime.strptime(date_str, "%Y-%m-%d")
                    - timedelta(days=1)
                ).strftime("%Y-%m-%d")

                prev_stmt = select(ADILog.adi_score).where(
                    ADILog.animal_id        == animal.id,
                    ADILog.calculation_date == yesterday,
                )
                prev_result = await db.execute(prev_stmt)
                prev_row    = prev_result.fetchone()
                prev_score  = float(prev_row[0]) if prev_row else None

                # ADI hisoblash
                adi_result = await adi_service.calculate_for_animal(
                    animal_id=        animal.id,
                    target_date=      date_str,
                    force_recalculate=force_recalculate,
                )

                # Alert tekshirish
                feeding_comp = adi_result.components.get("feeding")
                await alert_service.process_adi_result(
                    animal_id=     animal.id,
                    adi_score=     adi_result.adi_score,
                    category=      adi_result.category,
                    prev_score=    prev_score,
                    feeding_score= (
                        feeding_comp.score
                        if feeding_comp else None
                    ),
                )

                success_count += 1

                logger.debug(
                    f"ADI calculated | "
                    f"animal={animal.tag_id} | "
                    f"score={adi_result.adi_score:.1f} | "
                    f"category={adi_result.category}"
                )

            except Exception as e:
                failed_count += 1
                failed_animals.append(animal.id)
                logger.error(
                    f"ADI failed for animal {animal.tag_id}: {e}",
                    exc_info=True,
                )

        # Ferma xulosasi
        farm_summary = await adi_service.get_farm_summary(
            target_date=date_str
        )

    duration = time.monotonic() - start_time

    result_data = {
        "date":             date_str,
        "total":            len(animals),
        "success":          success_count,
        "failed":           failed_count,
        "failed_animal_ids":failed_animals,
        "duration_seconds": round(duration, 2),
        "farm_adi_score":   farm_summary.get("farm_adi_score", 0),
        "critical_count":   farm_summary.get("critical_count", 0),
        "warning_count":    farm_summary.get("warning_count",  0),
    }

    logger.info(
        f"Daily ADI complete | "
        f"date={date_str} | "
        f"success={success_count} | "
        f"failed={failed_count} | "
        f"farm_score={farm_summary.get('farm_adi_score', 0):.1f} | "
        f"duration={duration:.1f}s"
    )

    return result_data


# ================================================================ #
# TASK 2: KO'RINMAYOTGAN JONIVORLAR                                 #
# ================================================================ #

@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="adi.check_missing_animals",
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=300,
    time_limit=360,
    acks_late=True,
)
def check_missing_animals(self) -> dict:
    """
    Ko'rinmayotgan jonivorlarni tekshirish va alert yaratish.

    Har soatda ishga tushadi.
    24 soat → ANIMAL_MISSING (high)
    48 soat → ANIMAL_MISSING_LONG (critical)

    Returns:
        {"checked": int, "alerts_created": int}
    """
    return self.run_async(_check_missing_async(task=self))


async def _check_missing_async(task) -> dict:
    """check_missing_animals ning async implementatsiyasi."""
    logger.info("Missing animal check started")

    async with AsyncSessionLocal() as db:
        from app.services.alert_service import AlertService
        alert_service = AlertService(db)

        # Aktiv jonivorlar sonini olish
        count_stmt = select(Animal).where(Animal.status == AnimalStatus.ACTIVE)
        count_result = await db.execute(count_stmt)
        animal_count = len(count_result.scalars().all())

        alerts = await alert_service.check_missing_animals()

    logger.info(
        f"Missing check complete | "
        f"checked={animal_count} | "
        f"alerts={len(alerts)}"
    )

    return {
        "checked":        animal_count,
        "alerts_created": len(alerts),
        "alert_ids":      [a.id for a in alerts],
    }


# ================================================================ #
# TASK 3: O'SISH TO'XTAGAN JONIVORLAR                              #
# ================================================================ #

@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="adi.check_growth_stagnation",
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=600,
    time_limit=720,
    acks_late=True,
)
def check_growth_stagnation(self) -> dict:
    """
    14 kundan ortiq o'sish trendi neytral yoki
    salbiy bo'lgan jonivorlarni aniqlash.

    Har haftada bir marta (Dushanba 02:00 UTC) ishga tushadi.

    Returns:
        {"checked": int, "stagnation_alerts": int}
    """
    return self.run_async(_check_growth_stagnation_async(task=self))


async def _check_growth_stagnation_async(task) -> dict:
    """check_growth_stagnation ning async implementatsiyasi."""
    logger.info("Growth stagnation check started")

    stagnation_count = 0
    checked_count    = 0

    async with AsyncSessionLocal() as db:
        from app.services.alert_service import AlertService
        from app.models.alert import AlertType

        alert_service = AlertService(db)

        # Aktiv jonivorlar
        stmt = select(Animal).where(Animal.status == AnimalStatus.ACTIVE)
        result = await db.execute(stmt)
        animals = list(result.scalars().all())

        for animal in animals:
            checked_count += 1

            # So'nggi 14 kunlik growth_score larini olish
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            two_weeks_ago = (
                datetime.now(timezone.utc) - timedelta(days=14)
            ).strftime("%Y-%m-%d")

            growth_stmt = select(
                ADILog.calculation_date,
                ADILog.growth_score,
            ).where(
                ADILog.animal_id        == animal.id,
                ADILog.calculation_date >= two_weeks_ago,
                ADILog.growth_score.isnot(None),
            ).order_by(ADILog.calculation_date.asc())

            growth_result = await db.execute(growth_stmt)
            growth_rows   = growth_result.fetchall()

            if len(growth_rows) < 7:
                # Yetarli ma'lumot yo'q
                continue

            scores = [float(row[1]) for row in growth_rows]
            avg_growth_score = sum(scores) / len(scores)

            if avg_growth_score < 40.0:
                # O'sish muammosi aniqlandi
                await alert_service._ensure_alert(
                    animal_id=  animal.id,
                    alert_type= AlertType.GROWTH_STAGNATION,
                    title=(
                        f"O'sish to'xtagan: {animal.tag_id} "
                        f"(score: {avg_growth_score:.1f})"
                    ),
                    description=(
                        f"Jonivor {animal.tag_id} ning so'nggi 14 kunlik "
                        f"o'sish ko'rsatkichi past ({avg_growth_score:.1f}/100). "
                        f"Oziqlanish sifati yoki sog'liq muammosi bo'lishi mumkin."
                    ),
                    context={
                        "avg_growth_score": round(avg_growth_score, 2),
                        "period_days":      len(growth_rows),
                        "threshold":        40.0,
                    },
                )
                stagnation_count += 1
                logger.warning(
                    f"Growth stagnation: animal={animal.tag_id} | "
                    f"avg_score={avg_growth_score:.1f}"
                )

    logger.info(
        f"Growth check complete | "
        f"checked={checked_count} | "
        f"stagnation={stagnation_count}"
    )

    return {
        "checked":           checked_count,
        "stagnation_alerts": stagnation_count,
    }


# ================================================================ #
# TASK 4: ESKI ALERTLARNI TOZALASH                                  #
# ================================================================ #

@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="adi.cleanup_old_alerts",
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=300,
    time_limit=360,
    acks_late=True,
)
def cleanup_old_alerts(
    self,
    keep_days: int = 90,
) -> dict:
    """
    90 kundan eski yopilgan alertlarni o'chirish.

    Har haftada Yakshanba 03:00 UTC da ishga tushadi.
    Ochiq alertlar hech qachon o'chirilmaydi.

    Args:
        keep_days: Necha kunlik alertlarni saqlash (default: 90)

    Returns:
        {"deleted": int, "kept": int}
    """
    return self.run_async(
        _cleanup_old_alerts_async(task=self, keep_days=keep_days)
    )


async def _cleanup_old_alerts_async(task, keep_days: int) -> dict:
    """cleanup_old_alerts ning async implementatsiyasi."""
    from sqlalchemy import delete, and_, func

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=keep_days)

    logger.info(
        f"Alert cleanup started | "
        f"cutoff={cutoff_date.strftime('%Y-%m-%d')} | "
        f"keep_days={keep_days}"
    )

    async with AsyncSessionLocal() as db:
        # Faqat yopilgan alertlarni o'chirish
        delete_stmt = (
            delete(Alert)
            .where(
                and_(
                    Alert.status.in_([
                        AlertStatus.RESOLVED,
                        AlertStatus.DISMISSED,
                    ]),
                    Alert.resolved_at < cutoff_date,
                )
            )
        )
        result = await db.execute(delete_stmt)
        deleted_count = result.rowcount
        await db.commit()

        # Qolgan alertlar soni
        remaining_stmt = select(func.count(Alert.id))
        remaining      = await db.scalar(remaining_stmt) or 0

    logger.info(
        f"Alert cleanup complete | "
        f"deleted={deleted_count} | "
        f"remaining={remaining}"
    )

    return {
        "deleted":    deleted_count,
        "kept":       remaining,
        "cutoff_date":cutoff_date.strftime("%Y-%m-%d"),
    }