"""
Taurus Vision — Notifications API (Sprint 11)

Notification sozlamalari va test endpointlari.

ENDPOINTLAR:
    GET  /notifications/settings         — SMTP sozlamalarini ko'rish
    POST /notifications/test             — Test email yuborish
    POST /notifications/send/{alert_id}  — Bitta alert uchun email yuborish (manual)
    GET  /notifications/history          — Oxirgi yuborilgan emaillar logi

AUTENTIFIKATSIYA:
    GET:  VIEWER+
    POST: MANAGER+
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel as PydanticModel, Field, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.v1.deps import CurrentUser, CurrentManager
from app.models.alert import Alert
from app.models.animal import Animal
from app.services.notification_service import get_notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# =============================================================================
# SCHEMAS
# =============================================================================

class TestEmailRequest(PydanticModel):
    """Test email yuborish uchun request."""
    recipient: str = Field(..., description="Test email manzili")


class ManualSendRequest(PydanticModel):
    """Qo'lda email yuborish."""
    recipients: Optional[list[str]] = Field(None, description="Manzillar (None = settings dan)")


class SmtpSettingsResponse(PydanticModel):
    """SMTP sozlamalari response (parolsiz)."""
    configured:       bool
    smtp_host:        str
    smtp_port:        int
    smtp_user:        str
    from_address:     str
    recipients:       list[str]
    total_recipients: int
    severity_rules: dict = {
        "critical": "✅ Email yuboriladi",
        "high":     "✅ Email yuboriladi",
        "medium":   "✅ Email yuboriladi",
        "low":      "❌ Email yuborilmaydi",
    }


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get(
    "/settings",
    response_model=SmtpSettingsResponse,
    status_code=http_status.HTTP_200_OK,
    summary="SMTP sozlamalarini ko'rish",
    description=(
        "Hozirgi SMTP konfiguratsiyasini qaytaradi. "
        "Parol ko'rsatilmaydi."
    ),
)
async def get_notification_settings(
    current_user: CurrentUser = ...,
) -> SmtpSettingsResponse:
    """
    SMTP sozlamalari va notification qoidalari.

    .env faylida quyidagilarni sozlang:
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
        SMTP_FROM, NOTIFICATION_EMAILS
    """
    service = get_notification_service()
    info    = service.get_settings_info()

    return SmtpSettingsResponse(**info)


@router.post(
    "/test",
    status_code=http_status.HTTP_200_OK,
    summary="Test email yuborish",
    description=(
        "SMTP ulanishini tekshiradi va ko'rsatilgan manzilga test email yuboradi. "
        "SMTP sozlanmagan bo'lsa — log da ko'rsatiladi."
    ),
)
async def send_test_email(
    body:         TestEmailRequest,
    current_user: CurrentManager = ...,
) -> dict:
    """
    SMTP ulanishini test qiladi.

    Args:
        body.recipient: Test email manzili

    Returns:
        {"sent": bool, "mode": "smtp"|"log", "message": str}
    """
    logger.info(
        f"Test email so'rovi",
        extra={"extra_data": {
            "recipient":    body.recipient,
            "requested_by": current_user.username,
        }},
    )

    # Celery task orqali yuborish
    try:
        from workers.tasks.notification_tasks import send_test_email as test_task
        # Celery mavjud bo'lmasa sync ishlatamiz
        result = test_task.apply(args=[body.recipient])
        return result.get(timeout=30)
    except Exception as exc:
        logger.warning(f"Celery task failed, trying direct: {exc}")
        # Celery yo'q bo'lsa — to'g'ridan yuborish
        service = get_notification_service()
        conn_test = await service.test_smtp_connection()
        return conn_test


@router.post(
    "/send/{alert_id}",
    status_code=http_status.HTTP_200_OK,
    summary="Alert uchun email yuborish",
    description="Belgilangan alert uchun qo'lda email xabarnomasi yuboradi.",
)
async def send_alert_notification(
    alert_id:     int,
    body:         ManualSendRequest,
    current_user: CurrentManager = ...,
    db:           AsyncSession   = Depends(get_db),
) -> dict:
    """
    Bitta alert uchun email yuborish.

    Args:
        alert_id:         Alert ID
        body.recipients:  Override recipients (None = settings dan)

    Raises:
        404: Alert topilmasa
    """
    # Alert topish
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert  = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Alert #{alert_id} topilmadi",
        )

    # Animal tag topish
    animal_tag: Optional[str] = None
    if alert.animal_id:
        animal_result = await db.execute(
            select(Animal.tag_id).where(Animal.id == alert.animal_id)
        )
        row = animal_result.fetchone()
        animal_tag = row[0] if row else None

    # Email yuborish
    service = get_notification_service()
    send_result = await service.send_alert_email(
        alert      = alert,
        animal_tag = animal_tag,
        recipients = body.recipients,
    )

    logger.info(
        f"Manual notification yuborildi",
        extra={"extra_data": {
            "alert_id":     alert_id,
            "sent":         send_result.get("sent"),
            "requested_by": current_user.username,
        }},
    )

    return {
        **send_result,
        "alert_id": alert_id,
    }


@router.post(
    "/send-bulk",
    status_code=http_status.HTTP_200_OK,
    summary="Bir nechta alert uchun email yuborish",
    description="Filtrga mos ochiq alertlar uchun email xabarnomasi yuboradi.",
)
async def send_bulk_notifications(
    severity:     Optional[str] = None,
    current_user: CurrentManager = ...,
    db:           AsyncSession   = Depends(get_db),
) -> dict:
    """
    Ochiq alertlar uchun toplu email yuborish.

    Args:
        severity: Filtr (critical|high|medium) — None = hammasi

    Returns:
        {"queued": int, "alert_ids": [...]}
    """
    from app.models.alert import AlertStatus
    from sqlalchemy import and_

    stmt = select(Alert).where(
        Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN])
    )
    if severity:
        stmt = stmt.where(Alert.severity == severity)

    stmt = stmt.order_by(Alert.triggered_at.desc()).limit(50)
    result  = await db.execute(stmt)
    alerts  = list(result.scalars().all())

    queued = 0
    ids    = []

    try:
        from workers.tasks.notification_tasks import send_alert_email
        for alert in alerts:
            send_alert_email.delay(alert_id=alert.id)
            queued += 1
            ids.append(alert.id)
    except Exception as exc:
        logger.warning(f"Celery unavailable for bulk send: {exc}")

    return {
        "queued":    queued,
        "alert_ids": ids,
        "message":   f"{queued} ta alert uchun email navbatga qo'shildi",
    }