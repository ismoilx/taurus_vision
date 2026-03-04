"""
Taurus Vision — Feed Management Celery Tasks (Sprint 20)

TASKLAR:
    feed.check_low_stock   — Har kecha 08:00: kam zaxiralarga alert
    feed.daily_report      — Har kecha 07:30: kunlik iste'mol xulosasi
    feed.check_expiry       — Har kecha 09:00: muddati yaqin zaxiralar
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from workers.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


def _run(coro):
    import asyncio, concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()


# =============================================================================
# TASK 1: LOW STOCK CHECK
# =============================================================================

@celery_app.task(
    bind=True, name="feed.check_low_stock",
    max_retries=2, default_retry_delay=120,
    soft_time_limit=180, time_limit=240, acks_late=True,
)
def check_low_stock(self) -> dict:
    """
    Barcha aktiv zaxiralarni tekshirib, kam bo'lganlarga alert yuborish.
    Har kecha 08:00 UTC.
    """
    try:
        result = _run(_check_low_stock_async())
        if result["alerts_sent"]:
            logger.warning(
                f"[feed] Low stock alert | "
                f"low={result['checked']} | sent={result['alerts_sent']}"
            )
        return result
    except Exception as exc:
        logger.error(f"[feed] check_low_stock failed: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"error": str(exc)}


async def _check_low_stock_async() -> dict:
    async with AsyncSessionLocal() as db:
        from app.services.feed_service import FeedService
        return await FeedService(db).check_low_stock_alerts()


# =============================================================================
# TASK 2: EXPIRY CHECK
# =============================================================================

@celery_app.task(
    bind=True, name="feed.check_expiry",
    max_retries=2, default_retry_delay=120,
    soft_time_limit=120, time_limit=180, acks_late=True,
)
def check_expiry(self) -> dict:
    """
    7 kun ichida muddati tugaydigan zaxiralarga ogohlantirish.
    Har kecha 09:00 UTC.
    """
    try:
        return _run(_check_expiry_async())
    except Exception as exc:
        logger.error(f"[feed] check_expiry failed: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"error": str(exc)}


async def _check_expiry_async() -> dict:
    alerts_sent = 0
    async with AsyncSessionLocal() as db:
        from app.repositories.feed_repository import FeedStockRepository
        from app.services.alert_service import AlertService
        from app.models.alert import AlertType, AlertSeverity

        repo      = FeedStockRepository(db)
        alert_svc = AlertService(db)
        expiring  = await repo.get_expiring_soon(within_days=7)

        for stock in expiring:
            days_left = (stock.expiry_date - datetime.now(timezone.utc)).days
            try:
                await alert_svc._ensure_alert(
                    animal_id   = None,
                    alert_type  = AlertType.CUSTOM,
                    title       = f"Ozuqa muddati tugaydi: {stock.name}",
                    description = (
                        f"'{stock.name}' ozuqasining yaroqlilik muddati "
                        f"{days_left} kundan keyin tugaydi. "
                        f"Mavjud: {stock.current_kg:.1f} kg."
                    ),
                    severity    = AlertSeverity.HIGH if days_left <= 3 else AlertSeverity.MEDIUM,
                    context     = {
                        "stock_id":    stock.id,
                        "stock_name":  stock.name,
                        "expiry_date": stock.expiry_date.isoformat(),
                        "days_left":   days_left,
                        "current_kg":  stock.current_kg,
                        "source":      "feed_expiry_check",
                    },
                )
                alerts_sent += 1
            except Exception as e:
                logger.error(f"[feed] Expiry alert xatosi: stock={stock.id} | {e}")

        if alerts_sent:
            await db.commit()

    logger.info(f"[feed] Expiry check | expiring={len(expiring)} | alerts={alerts_sent}")
    return {"expiring": len(expiring), "alerts_sent": alerts_sent}


# =============================================================================
# TASK 3: DAILY REPORT
# =============================================================================

@celery_app.task(
    bind=True, name="feed.daily_report",
    max_retries=2, default_retry_delay=300,
    soft_time_limit=300, time_limit=360, acks_late=True,
)
def daily_feed_report(self, target_date: Optional[str] = None) -> dict:
    """
    Kunlik ozuqa iste'mol xulosasi.
    Har kecha 07:30 UTC.
    """
    try:
        return _run(_daily_report_async(target_date))
    except Exception as exc:
        logger.error(f"[feed] daily_report failed: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"error": str(exc)}


async def _daily_report_async(target_date: Optional[str]) -> dict:
    from datetime import timedelta
    now      = datetime.now(timezone.utc)
    date_str = target_date or (now - timedelta(days=1)).strftime("%Y-%m-%d")

    day_start = datetime.fromisoformat(date_str + "T00:00:00+00:00")
    day_end   = day_start + timedelta(days=1)

    async with AsyncSessionLocal() as db:
        from app.repositories.feed_repository import FeedRecordRepository, FeedStockRepository

        rec_repo   = FeedRecordRepository(db)
        stock_repo = FeedStockRepository(db)

        consumed   = await rec_repo.get_consumed_kg(day_start, day_end)
        low_stocks = await stock_repo.get_low_stock()

    result = {
        "date":           date_str,
        "consumed_kg":    round(consumed, 1),
        "low_stock_count": len(low_stocks),
        "low_stocks":     [s.name for s in low_stocks],
    }

    logger.info(
        f"[feed] Daily report | date={date_str} | "
        f"consumed={consumed:.1f}kg | low={len(low_stocks)}"
    )
    return result