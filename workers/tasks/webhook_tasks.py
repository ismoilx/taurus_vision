"""
Taurus Vision — Webhook Celery Tasks

TASKLAR:
  dispatch_webhook(event, payload)  — Voqeani barcha webhooklarga yuborish

QAYTA URINISH STRATEGIYASI:
  1-urinish: darhol
  2-urinish: 60s
  3-urinish: 5 daqiqa
  Hammasi muvaffaqiyatsiz → failure_count oshadi → 5 dan oshsa webhook o'chadi

FOYDALANISH (boshqa tasklar ichida):
  from workers.tasks.webhook_tasks import dispatch_webhook
  dispatch_webhook.delay("alert.created", {"alert_id": 42, "message": "..."})
"""

import asyncio
import logging

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="webhook.dispatch",
    bind=True,
    queue="notification",
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=30,
)
def dispatch_webhook(self, event: str, payload: dict) -> dict:
    """
    Voqeani barcha aktiv webhooklarga yuborish.

    Args:
        event:   WebhookEvent qiymati ("alert.created", "adi.critical", ...)
        payload: Voqea ma'lumotlari (serializatsiya qilingan dict)

    Returns:
        {"event": str, "dispatched": int}
    """
    try:
        return _run(_dispatch_async(event, payload))
    except Exception as exc:
        logger.error(f"dispatch_webhook xatosi: event={event}, err={exc}")
        raise self.retry(exc=exc)


async def _dispatch_async(event: str, payload: dict) -> dict:
    from app.services.integration_service import IntegrationService
    await IntegrationService.dispatch_event(event, payload)
    return {"event": event, "status": "dispatched"}


# =============================================================================
# QULAYLIK FUNKSIYALARI — boshqa tasklar uchun
# =============================================================================

def trigger_alert_webhook(alert_data: dict) -> None:
    """
    Alert yaratilganda chaqiriladi.
    severity bo'yicha voqea nomi aniqlanadi.
    """
    severity = alert_data.get("severity", "").lower()

    # Har qanday alert uchun
    dispatch_webhook.delay("alert.created", alert_data)

    # Kritik/yuqori alertlar uchun alohida
    if severity in ("critical", "high"):
        dispatch_webhook.delay("alert.critical", alert_data)


def trigger_weight_anomaly_webhook(animal_id: int, tag_id: str, change_pct: float) -> None:
    """Vazn >5% o'zgarsa chaqiriladi."""
    dispatch_webhook.delay("weight.anomaly", {
        "animal_id":  animal_id,
        "tag_id":     tag_id,
        "change_pct": change_pct,
    })


def trigger_sensor_anomaly_webhook(camera_id: int, anomaly: dict) -> None:
    """Sensor normal diapazondan chiqsa chaqiriladi."""
    dispatch_webhook.delay("sensor.anomaly", {
        "camera_id": camera_id,
        **anomaly,
    })


def trigger_adi_critical_webhook(animal_id: int, tag_id: str, adi_score: float) -> None:
    """ADI < 30 bo'lsa chaqiriladi."""
    dispatch_webhook.delay("adi.critical", {
        "animal_id": animal_id,
        "tag_id":    tag_id,
        "adi_score": adi_score,
    })


def trigger_animal_not_seen_webhook(animal_id: int, tag_id: str, hours: int) -> None:
    """Jonivor N soat ko'rinmasa chaqiriladi."""
    dispatch_webhook.delay("animal.not_seen", {
        "animal_id":    animal_id,
        "tag_id":       tag_id,
        "hours_missing": hours,
    })