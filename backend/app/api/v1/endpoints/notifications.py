"""
Taurus Vision — Notifications API

Ikki qism:
  1. IN-APP BILDIRISHNOMALAR (yangi, to'liq)
     GET  /notifications/             — Foydalanuvchi notificationlari
     GET  /notifications/count        — O'qilmagan son (badge uchun)
     POST /notifications/read/{id}    — Bitta o'qildi
     POST /notifications/read-all     — Hammasi o'qildi
     POST /notifications/dismiss/{id} — Bitta yashirildi
     POST /notifications/dismiss-all  — Hammasi yashirildi
     POST /notifications/             — Yangi notification yaratish [ADMIN]

  2. EMAIL SOZLAMALARI
     GET  /notifications/email/settings
     POST /notifications/email/test
     POST /notifications/email/send/{alert_id}
     POST /notifications/email/send-bulk
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from pydantic import BaseModel as PydanticModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.v1.deps import CurrentUser, CurrentManager, CurrentAdmin
from app.models.notification import NotificationType
from app.models.alert import Alert
from app.models.animal import Animal
from app.services.notification_service import get_notification_service
from app.services.inapp_notification_service import InAppNotificationService
from app.schemas.notification import (
    NotificationOut,
    NotificationListOut,
    NotificationCountOut,
    NotificationCreateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# =============================================================================
# IN-APP BILDIRISHNOMALAR
# =============================================================================

@router.get(
    "",
    response_model=NotificationListOut,
    summary="Notificationlarni olish",
)
async def list_notifications(
    limit:       int  = Query(30,    ge=1,  le=100),
    offset:      int  = Query(0,     ge=0),
    unread_only: bool = Query(False),
    n_type: Optional[NotificationType] = Query(None),
    current_user: CurrentUser = ...,
    db:           AsyncSession = Depends(get_db),
) -> NotificationListOut:
    svc    = InAppNotificationService(db)
    result = await svc.get_user_notifications(
        user_id=current_user.id, limit=limit, offset=offset,
        unread_only=unread_only, n_type=n_type,
    )
    return NotificationListOut(**result)


@router.get(
    "/count",
    response_model=NotificationCountOut,
    summary="O'qilmagan notification soni",
)
async def get_notification_count(
    current_user: CurrentUser  = ...,
    db:           AsyncSession = Depends(get_db),
) -> NotificationCountOut:
    svc = InAppNotificationService(db)
    return NotificationCountOut(**(await svc.get_unread_count(current_user.id)))


@router.post(
    "/read/{notification_id}",
    status_code=http_status.HTTP_200_OK,
    summary="Bitta o'qildi",
)
async def mark_read(
    notification_id: int,
    current_user:    CurrentUser  = ...,
    db:              AsyncSession = Depends(get_db),
) -> dict:
    svc = InAppNotificationService(db)
    return {"updated": await svc.mark_as_read(notification_id, current_user.id)}


@router.post(
    "/read-all",
    status_code=http_status.HTTP_200_OK,
    summary="Barcha o'qildi",
)
async def mark_all_read(
    current_user: CurrentUser  = ...,
    db:           AsyncSession = Depends(get_db),
) -> dict:
    svc   = InAppNotificationService(db)
    count = await svc.mark_all_as_read(current_user.id)
    return {"updated_count": count}


@router.post(
    "/dismiss/{notification_id}",
    status_code=http_status.HTTP_200_OK,
    summary="Bitta yashirildi",
)
async def dismiss_one(
    notification_id: int,
    current_user:    CurrentUser  = ...,
    db:              AsyncSession = Depends(get_db),
) -> dict:
    svc = InAppNotificationService(db)
    return {"dismissed": await svc.dismiss(notification_id, current_user.id)}


@router.post(
    "/dismiss-all",
    status_code=http_status.HTTP_200_OK,
    summary="Hammasi yashirildi",
)
async def dismiss_all(
    current_user: CurrentUser  = ...,
    db:           AsyncSession = Depends(get_db),
) -> dict:
    svc   = InAppNotificationService(db)
    count = await svc.dismiss_all(current_user.id)
    return {"dismissed_count": count}


@router.post(
    "",
    response_model=NotificationOut,
    status_code=http_status.HTTP_201_CREATED,
    summary="Notification yaratish [ADMIN]",
)
async def create_notification(
    body:         NotificationCreateRequest,
    current_user: CurrentAdmin = ...,
    db:           AsyncSession = Depends(get_db),
) -> NotificationOut:
    svc = InAppNotificationService(db)
    if body.user_id is None:
        notif = await svc.broadcast(
            n_type=body.n_type, title=body.title, message=body.message,
            entity_type=body.entity_type, entity_id=body.entity_id,
            action_url=body.action_url, extra_data=body.extra_data,
        )
    else:
        notif = await svc.notify_user(
            user_id=body.user_id, n_type=body.n_type,
            title=body.title, message=body.message,
            entity_type=body.entity_type, entity_id=body.entity_id,
            action_url=body.action_url, extra_data=body.extra_data,
        )
    return NotificationOut.model_validate(notif)


# =============================================================================
# EMAIL SOZLAMALARI
# =============================================================================

class TestEmailRequest(PydanticModel):
    recipient: str = Field(..., description="Test email manzili")


class ManualSendRequest(PydanticModel):
    recipients: Optional[list[str]] = None


class SmtpSettingsResponse(PydanticModel):
    configured:       bool
    smtp_host:        str
    smtp_port:        int
    smtp_user:        str
    from_address:     str
    recipients:       list[str]
    total_recipients: int
    severity_rules:   dict = {
        "critical": "✅ Email yuboriladi",
        "high":     "✅ Email yuboriladi",
        "medium":   "✅ Email yuboriladi",
        "low":      "❌ Email yuborilmaydi",
    }


@router.get(
    "/email/settings",
    response_model=SmtpSettingsResponse,
    summary="SMTP sozlamalarini ko'rish",
)
async def get_email_settings(current_user: CurrentUser = ...) -> SmtpSettingsResponse:
    return SmtpSettingsResponse(**get_notification_service().get_settings_info())


@router.post("/email/test", summary="Test email")
async def send_test_email(body: TestEmailRequest, current_user: CurrentManager = ...) -> dict:
    try:
        from workers.tasks.notification_tasks import send_test_email as task
        return task.apply(args=[body.recipient]).get(timeout=30)
    except Exception:
        return await get_notification_service().test_smtp_connection()


@router.post("/email/send/{alert_id}", summary="Alert emaili")
async def send_alert_email(
    alert_id: int,
    body:     ManualSendRequest,
    current_user: CurrentManager = ...,
    db:           AsyncSession   = Depends(get_db),
) -> dict:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert  = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Alert #{alert_id} topilmadi")
    animal_tag = None
    if alert.animal_id:
        r = await db.execute(select(Animal.tag_id).where(Animal.id == alert.animal_id))
        row = r.fetchone()
        animal_tag = row[0] if row else None
    res = await get_notification_service().send_alert_email(alert, animal_tag, body.recipients)
    return {**res, "alert_id": alert_id}


@router.post("/email/send-bulk", summary="Ko'plab alert emaili")
async def send_bulk_emails(
    severity:     Optional[str] = None,
    current_user: CurrentManager = ...,
    db:           AsyncSession   = Depends(get_db),
) -> dict:
    from app.models.alert import AlertStatus
    stmt = select(Alert).where(Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]))
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    alerts = list((await db.execute(stmt.limit(50))).scalars().all())
    queued, ids = 0, []
    try:
        from workers.tasks.notification_tasks import send_alert_email as etask
        for a in alerts:
            etask.delay(alert_id=a.id); queued += 1; ids.append(a.id)
    except Exception as exc:
        logger.warning(f"Celery bulk: {exc}")
    return {"queued": queued, "alert_ids": ids}

# =============================================================================
# TELEGRAM ENDPOINTS
# =============================================================================

class TelegramSettingsResponse(PydanticModel):
    configured:          bool
    bot_token_set:       bool
    bot_token_masked:    str
    chat_ids:            list[str]
    total_chats:         int
    severity_rules:      dict = {
        "critical": "✅ Telegram yuboriladi",
        "high":     "✅ Telegram yuboriladi",
        "medium":   "✅ Telegram yuboriladi",
        "low":      "❌ Telegram yuborilmaydi",
    }


class TelegramTestRequest(PydanticModel):
    chat_id: str = Field(..., description="Test Telegram chat ID")


class TelegramSendRequest(PydanticModel):
    chat_ids: Optional[list[str]] = None


@router.get(
    "/telegram/settings",
    response_model=TelegramSettingsResponse,
    summary="Telegram bot sozlamalarini ko'rish",
)
async def get_telegram_settings(current_user: CurrentUser = ...) -> TelegramSettingsResponse:
    """Hozirgi Telegram bot sozlamalarini qaytaradi."""
    from app.services.telegram_service import get_telegram_service
    return TelegramSettingsResponse(**get_telegram_service().get_settings_info())


@router.post("/telegram/test", summary="Test Telegram xabari yuborish")
async def send_test_telegram(
    body: TelegramTestRequest,
    current_user: CurrentManager = ...,
) -> dict:
    """
    Berilgan chat_id ga test xabari yuboradi.
    Sozlamalarni tekshirish uchun.
    """
    from app.services.telegram_service import get_telegram_service
    svc = get_telegram_service()
    result = await svc.send_test_message(body.chat_id)
    return result


@router.post("/telegram/send/{alert_id}", summary="Alert Telegram xabari")
async def send_telegram_alert(
    alert_id: int,
    body:     TelegramSendRequest,
    current_user: CurrentManager = ...,
    db:           AsyncSession   = Depends(get_db),
) -> dict:
    """
    Berilgan alert uchun Telegram xabari yuboradi.
    chat_ids bo'sh bo'lsa settings dagi chat_ids ishlatiladi.
    """
    from app.services.telegram_service import get_telegram_service
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert  = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Alert #{alert_id} topilmadi")

    animal_tag = None
    if alert.animal_id:
        r = await db.execute(select(Animal.tag_id).where(Animal.id == alert.animal_id))
        row = r.fetchone()
        animal_tag = row[0] if row else None

    svc = get_telegram_service()
    res = await svc.send_alert(
        alert      = alert,
        animal_tag = animal_tag,
        chat_ids   = body.chat_ids,
    )
    return {**res, "alert_id": alert_id}


@router.post("/telegram/send-bulk", summary="Ko'plab alert Telegram xabarlari")
async def send_bulk_telegram(
    severity:     Optional[str] = None,
    current_user: CurrentManager = ...,
    db:           AsyncSession   = Depends(get_db),
) -> dict:
    """
    Ochiq alertlar uchun Telegram xabarlari yuboradi.
    severity filtri: critical, high, medium, low
    """
    from app.models.alert import AlertStatus
    from app.services.telegram_service import get_telegram_service

    stmt = select(Alert).where(Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]))
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    alerts = list((await db.execute(stmt.limit(50))).scalars().all())

    svc = get_telegram_service()
    sent, total = 0, len(alerts)

    for a in alerts:
        try:
            res = await svc.send_alert(a)
            if res.get("sent"):
                sent += 1
        except Exception as exc:
            logger.warning(f"Telegram bulk xato: alert #{a.id}: {exc}")

    return {"total": total, "sent": sent, "skipped": total - sent}


# =============================================================================
# FLAT ROUTE ALIASES (test compatibility)
# Tests use /notifications/settings, /notifications/test-email etc.
# =============================================================================

@router.get("/settings", summary="Sozlamalar (alias for /email/settings)")
async def get_settings_flat(current_user: CurrentUser = ...) -> dict:
    """Flat alias for /email/settings."""
    return SmtpSettingsResponse(**get_notification_service().get_settings_info()).model_dump()


@router.post("/test-email", summary="Test email (alias for /email/test)")
async def send_test_email_flat(
    body: TestEmailRequest,
    current_user: CurrentManager = ...,
) -> dict:
    """Flat alias for /email/test."""
    try:
        from workers.tasks.notification_tasks import send_test_email as task
        return task.apply(args=[body.recipient]).get(timeout=30)
    except Exception:
        return await get_notification_service().test_smtp_connection()


@router.post("/send/{alert_id:int}", summary="Alert emaili (alias for /email/send/{id})")
async def send_alert_email_flat(
    alert_id: int,
    body:     ManualSendRequest,
    current_user: CurrentManager = ...,
    db:           AsyncSession   = Depends(get_db),
) -> dict:
    """Flat alias for /email/send/{alert_id}."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert  = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Alert #{alert_id} topilmadi")
    animal_tag = None
    if alert.animal_id:
        r = await db.execute(select(Animal.tag_id).where(Animal.id == alert.animal_id))
        row = r.fetchone()
        animal_tag = row[0] if row else None
    res = await get_notification_service().send_alert_email(alert, animal_tag, body.recipients)
    return {**res, "alert_id": alert_id, "sent": res.get("sent", False)}


@router.post("/send-bulk", summary="Ko'plab alert emaili (alias for /email/send-bulk)")
async def send_bulk_emails_flat(
    severity:     Optional[str] = None,
    current_user: CurrentManager = ...,
    db:           AsyncSession   = Depends(get_db),
) -> dict:
    """Flat alias for /email/send-bulk."""
    from app.models.alert import AlertStatus
    stmt = select(Alert).where(Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]))
    if severity:
        valid_severities = {"low", "medium", "high", "critical"}
        if severity not in valid_severities:
            raise HTTPException(
                http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Noto'g'ri severity: {severity}. Mumkin: {sorted(valid_severities)}"
            )
        stmt = stmt.where(Alert.severity == severity)
    alerts = list((await db.execute(stmt.limit(50))).scalars().all())
    queued, ids = 0, []
    for a in alerts:
        try:
            res = await get_notification_service().send_alert_email(a)
            if res.get("sent"):
                queued += 1
                ids.append(a.id)
        except Exception as exc:
            logger.warning(f"Bulk email xato: alert #{a.id}: {exc}")
    return {
        "queued": queued,
        "total_alerts": len(alerts),
        "alert_ids": ids,
        "message": f"{queued} ta alert emaili navbatga qo'yildi",
    }