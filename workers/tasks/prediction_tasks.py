"""
Health Prediction Celery Tasks — Sprint 13-14.

TASKS:
    run_daily_predictions   — Har kuni 01:00 UTC: barcha aktiv jonivorlar bashorat
    train_prediction_models — Har kuni 05:00 UTC: RF + ISO modellarni qayta o'rgatish
    cleanup_old_predictions — Har hafta: 90 kundan eski bashoratlarni tozalash

CELERY BEAT INTEGRATION:
    celery_app.py CELERY_BEAT_SCHEDULE ga qo'shiladi.

PATTERN:
    ADI tasks bilan bir xil DatabaseTask base class ishlatiladi.
    Sync Celery → async service → asyncio.run() (alohida thread).
"""

import logging
from datetime import datetime, timezone

from workers.celery_app import celery_app
from workers.tasks.adi_tasks import DatabaseTask   # Base class qayta ishlatish

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# KUNLIK BASHORAT
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    name="predictions.run_daily",
    queue="default",
    bind=True,
    max_retries=2,
    default_retry_delay=300,      # 5 daqiqadan keyin retry
    base=DatabaseTask,
    soft_time_limit=600,          # 10 daqiqa
    time_limit=660,
)
def run_daily_predictions(self) -> dict:
    """
    Barcha aktiv jonivorlar uchun kunlik sog'liq bashoratini hisoblaydi.

    Har kuni 01:00 UTC da Celery Beat tomonidan chaqiriladi.
    ADI hisoblash (00:30 UTC) tugagandan keyin ishga tushishi muhim —
    yangi ADI ma'lumotlari feature engineering uchun ishlatiladi.

    Returns:
        {
            "date": str,
            "total": int,
            "succeeded": int,
            "failed": int,
            "at_risk_count": int,
            "duration_sec": float,
        }

    Raises:
        Celery retry: DatabaseError yoki connection timeout bo'lsa
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info(f"[task:predictions] Starting daily run for {today}")

    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.services.prediction_service import PredictionService

        async with AsyncSessionLocal() as db:
            service = PredictionService(db)
            return await service.predict_all_active(target_date=today)

    try:
        result = self.run_async(_run())
        logger.info(
            f"[task:predictions] Daily run complete: "
            f"{result['succeeded']}/{result['total']} succeeded, "
            f"{result['at_risk_count']} at risk, "
            f"{result['duration_sec']:.1f}s"
        )
        return result

    except Exception as exc:
        logger.error(f"[task:predictions] Daily run failed: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {
                "date": today, "total": 0,
                "succeeded": 0, "failed": 0,
                "at_risk_count": 0, "duration_sec": 0.0,
                "error": str(exc),
            }


# ─────────────────────────────────────────────────────────────────────────────
# MODEL O'RGATISH
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    name="predictions.train_models",
    queue="default",
    bind=True,
    max_retries=1,
    default_retry_delay=600,
    base=DatabaseTask,
    soft_time_limit=1800,         # 30 daqiqa
    time_limit=1860,
)
def train_prediction_models(self, days_back: int = 90) -> dict:
    """
    RandomForest va IsolationForest modellarini qayta o'rgatadi.

    Har kuni 05:00 UTC da chaqiriladi.
    Kechasi yangi data yig'ilgandan keyin — eng to'liq dataset bilan o'rgatish.

    Args:
        days_back: Training uchun necha kunlik tarix (default: 90)

    Returns:
        {
            "rf_trained": bool,
            "iso_trained": bool,
            "n_samples": int,
            "rf_accuracy": float,
            "duration_sec": float,
        }
    """
    logger.info(f"[task:predictions] Starting model training (days_back={days_back})")

    async def _train():
        from app.core.database import AsyncSessionLocal
        from app.services.prediction_service import PredictionService, get_prediction_service

        async with AsyncSessionLocal() as db:
            # Global singleton orqali train qilish — modellar shu ob'ektda saqlanadi
            service = get_prediction_service(db)
            return await service.train_models(days_back=days_back)

    try:
        result = self.run_async(_train())
        rf_status = "✅ RF o'rgatildi" if result.get("rf_trained") else "⚠️ RF o'rgatilmadi"
        logger.info(
            f"[task:predictions] Training complete: {rf_status}, "
            f"n={result.get('n_samples', 0)}, "
            f"roc_auc={result.get('rf_accuracy', 0.0):.3f}, "
            f"{result.get('duration_sec', 0.0):.1f}s"
        )
        return result

    except Exception as exc:
        logger.error(f"[task:predictions] Training failed: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {
                "rf_trained": False, "iso_trained": False,
                "n_samples": 0, "error": str(exc),
            }


# ─────────────────────────────────────────────────────────────────────────────
# TOZALASH
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    name="predictions.cleanup_old",
    queue="default",
    bind=True,
    max_retries=2,
    base=DatabaseTask,
    soft_time_limit=120,
)
def cleanup_old_predictions(self, older_than_days: int = 90) -> dict:
    """
    Eski bashorat yozuvlarini tozalaydi.

    Har hafta (Yakshanba, 03:00 UTC) chaqiriladi.
    90 kundan eski yozuvlar o'chiriladi.
    """
    logger.info(f"[task:predictions] Cleanup: older than {older_than_days} days")

    async def _cleanup():
        from app.core.database import AsyncSessionLocal
        from app.repositories.prediction_repository import PredictionRepository

        async with AsyncSessionLocal() as db:
            repo    = PredictionRepository(db)
            deleted = await repo.delete_old_predictions(older_than_days)
            await db.commit()
            return deleted

    try:
        deleted = self.run_async(_cleanup())
        logger.info(f"[task:predictions] Cleanup done: {deleted} records deleted")
        return {"deleted": deleted, "older_than_days": older_than_days}
    except Exception as exc:
        logger.error(f"[task:predictions] Cleanup failed: {exc}")
        return {"deleted": 0, "error": str(exc)}