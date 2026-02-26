"""
Taurus Vision — Notification Celery Tasks (Sprint 11)

Alert yaratilganda email yuborish uchun Celery tasklari.

TASK NOMI:
    notification.send_alert_email  — Alert emailini yuborish
    notification.send_test_email   — SMTP test emaili
    notification.send_daily_digest — Kunlik xulosa email

QUEUE:
    notification — barcha notification tasklari

XATO HANDLING:
    max_retries=3: Muvaffaqiyatsiz bo'lsa 3 marta qayta urinadi
    retry backoff: 60s, 120s, 240s (eksponensial)
    autoretry_for: SMTPException, ConnectionError

FOYDALANISH:
    # Asinxron (preferred)
    send_alert_email.delay(alert_id=42, animal_tag="JNV-001")

    # Celery chain bilan
    chain(
        save_alert.s(alert_data),
        send_alert_email.s(),
    ).apply_async()
"""

import logging
from typing import Optional

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN TASK: Alert Email
# =============================================================================

@celery_app.task(
    name="notification.send_alert_email",
    queue="notification",
    max_retries=3,
    default_retry_delay=60,   # 1 daqiqa
    acks_late=True,
    bind=True,
)
def send_alert_email(
    self,
    alert_id:   int,
    animal_tag: Optional[str]       = None,
    recipients: Optional[list[str]] = None,
) -> dict:
    """
    Alert uchun email xabarnomasi yuboradi.

    Celery worker tomonidan ishga tushiriladi.
    SMTP xatosida avtomatik qayta urinadi.

    Args:
        alert_id:   Alert ORM ID (DB dan yuklanadi)
        animal_tag: Jonivor teg raqami (email da ko'rsatish uchun)
        recipients: Override email manzillari (None = settings dan)

    Returns:
        {
            "sent": bool,
            "recipients": [...],
            "mode": "smtp" | "log",
            "alert_id": int,
        }
    """
    import asyncio

    logger.info(
        f"[notification] Alert email task boshlandi",
        extra={"extra_data": {
            "alert_id":   alert_id,
            "animal_tag": animal_tag,
            "recipients": recipients,
        }},
    )

    try:
        result = asyncio.run(_send_alert_email_async(
            alert_id   = alert_id,
            animal_tag = animal_tag,
            recipients = recipients,
        ))

        logger.info(
            f"[notification] Email task yakunlandi: alert #{alert_id} | sent={result.get('sent')}",
        )
        return {**result, "alert_id": alert_id}

    except Exception as exc:
        logger.error(
            f"[notification] Email task xatosi: alert #{alert_id}: {exc}",
            exc_info=True,
        )
        # SMTP yoki tarmoq xatosida qayta urinish
        try:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(
                f"[notification] Max retries exceeded: alert #{alert_id}"
            )
            return {
                "sent":     False,
                "alert_id": alert_id,
                "error":    str(exc),
                "retries":  self.request.retries,
            }


async def _send_alert_email_async(
    alert_id:   int,
    animal_tag: Optional[str],
    recipients: Optional[list[str]],
) -> dict:
    """
    Async wrapper — DB dan alert yuklab, email yuboradi.

    Args:
        alert_id:   Alert ID
        animal_tag: Jonivor teg (ixtiyoriy)
        recipients: Override recipients

    Returns:
        NotificationService.send_alert_email() natijasi
    """
    from app.core.database import AsyncSessionLocal
    from app.models.alert import Alert
    from app.services.notification_service import get_notification_service
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        # Alert DB dan yuklash
        result = await db.execute(select(Alert).where(Alert.id == alert_id))
        alert  = result.scalar_one_or_none()

        if alert is None:
            logger.warning(f"Alert #{alert_id} topilmadi — email yuborilmadi")
            return {
                "sent":   False,
                "reason": f"Alert #{alert_id} topilmadi",
            }

        # Email yuborish
        service = get_notification_service()
        return await service.send_alert_email(
            alert      = alert,
            animal_tag = animal_tag,
            recipients = recipients,
        )


# =============================================================================
# SMTP TEST TASK
# =============================================================================

@celery_app.task(
    name="notification.send_test_email",
    queue="notification",
    max_retries=1,
)
def send_test_email(recipient: str) -> dict:
    """
    SMTP ulanishini va email yuborishni tekshiradi.

    Frontend Settings sahifasidagi "Test Email" tugmasidan chaqiriladi.

    Args:
        recipient: Test email manzili

    Returns:
        {"sent": bool, "message": str}
    """
    import asyncio

    logger.info(f"[notification] SMTP test: {recipient}")

    try:
        result = asyncio.run(_send_test_email_async(recipient))
        return result
    except Exception as exc:
        logger.error(f"[notification] Test email xatosi: {exc}")
        return {"sent": False, "message": str(exc)}


async def _send_test_email_async(recipient: str) -> dict:
    """Async SMTP test helper."""
    from app.services.notification_service import get_notification_service

    service = get_notification_service()
    connection_test = await service.test_smtp_connection()

    if not connection_test["ok"]:
        return {"sent": False, "message": connection_test["message"]}

    # Fake alert bilan test email
    class FakeAlert:
        id          = 0
        alert_type  = "test"
        severity    = "medium"
        title       = "SMTP Test — Taurus Vision"
        description = "Bu test email. SMTP ulanish muvaffaqiyatli sozlangan."
        camera_id   = None

    service2 = get_notification_service()
    result = await service2.send_alert_email(
        alert      = FakeAlert(),
        animal_tag = None,
        recipients = [recipient],
    )
    return result


# =============================================================================
# DAILY DIGEST TASK
# =============================================================================

@celery_app.task(
    name="notification.send_daily_digest",
    queue="notification",
    max_retries=2,
)
def send_daily_digest() -> dict:
    """
    Kunlik alert xulosasini yuboradi.

    Celery beat tomonidan har kuni ertalab chaqiriladi.
    Kechagi kun uchun: ochiq alertlar soni, yangi alertlar, hal etilganlar.

    Returns:
        {"sent": bool, "recipients": [...]}
    """
    import asyncio

    logger.info("[notification] Kunlik digest task boshlandi")

    try:
        result = asyncio.run(_send_daily_digest_async())
        logger.info(f"[notification] Kunlik digest yuborildi: {result}")
        return result
    except Exception as exc:
        logger.error(f"[notification] Digest xatosi: {exc}", exc_info=True)
        return {"sent": False, "error": str(exc)}


async def _send_daily_digest_async() -> dict:
    """Kunlik digest — DB dan statistika olib email yuboradi."""
    from datetime import datetime, timezone, timedelta

    from app.core.database import AsyncSessionLocal
    from app.models.alert import Alert, AlertStatus
    from app.services.notification_service import get_notification_service
    from sqlalchemy import select, func, and_

    async with AsyncSessionLocal() as db:
        now       = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)

        # Ochiq alertlar soni
        open_count = await db.scalar(
            select(func.count(Alert.id)).where(
                Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN])
            )
        ) or 0

        # Kecha yaratilgan alertlar
        new_count = await db.scalar(
            select(func.count(Alert.id)).where(
                Alert.triggered_at >= yesterday
            )
        ) or 0

        # Kecha hal etilganlar
        resolved_count = await db.scalar(
            select(func.count(Alert.id)).where(
                and_(
                    Alert.resolved_at >= yesterday,
                    Alert.status == AlertStatus.RESOLVED,
                )
            )
        ) or 0

    service    = get_notification_service()
    recipients = service._settings["recipients"]

    if not recipients:
        return {"sent": False, "reason": "Recipient sozlanmagan"}

    # Oddiy text digest
    subject = f"📊 Taurus Vision — Kunlik Xulosa {now.strftime('%Y-%m-%d')}"
    body    = f"""TAURUS VISION — KUNLIK XULOSA
{now.strftime('%Y-%m-%d')}
{'='*40}

📊 ALERT STATISTIKASI:
  Hozir ochiq alertlar: {open_count}
  Kecha yangi alertlar: {new_count}
  Kecha hal etildi:     {resolved_count}

Tizimni kuzatish: http://localhost:5173/alerts

---
Taurus Vision Monitoring System
"""

    if service.is_configured:
        try:
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            import smtplib

            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"]    = service._settings["from_addr"]
            msg["To"]      = ", ".join(recipients)
            msg.attach(MIMEText(body, "plain", "utf-8"))

            import asyncio
            s = service._settings

            def _send():
                with smtplib.SMTP(s["host"], s["port"]) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(s["user"], s["password"])
                    server.sendmail(s["from_addr"], recipients, msg.as_string())

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _send)
            return {"sent": True, "recipients": recipients}
        except Exception as exc:
            return {"sent": False, "error": str(exc)}
    else:
        logger.info(f"[DEV] Daily digest log:\n{body}")
        return {"sent": True, "recipients": recipients, "mode": "log"}