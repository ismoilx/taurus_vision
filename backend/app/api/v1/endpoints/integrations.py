"""
Taurus Vision — Integration API Endpoints (Q5)

API KEYS:
  GET    /integrations/api-keys              — Ro'yxat [ADMIN]
  POST   /integrations/api-keys              — Yangi kalit [ADMIN]
  GET    /integrations/api-keys/{id}         — Bitta kalit [ADMIN]
  PATCH  /integrations/api-keys/{id}         — Tahrirlash [ADMIN]
  DELETE /integrations/api-keys/{id}         — O'chirish [ADMIN]

WEBHOOKS:
  GET    /integrations/webhooks              — Ro'yxat [MANAGER+]
  POST   /integrations/webhooks              — Yangi webhook [ADMIN]
  GET    /integrations/webhooks/{id}         — Bitta webhook [MANAGER+]
  PATCH  /integrations/webhooks/{id}         — Tahrirlash [ADMIN]
  DELETE /integrations/webhooks/{id}         — O'chirish [ADMIN]
  POST   /integrations/webhooks/{id}/test    — Test ping [ADMIN]
  GET    /integrations/webhooks/{id}/secret  — Secret ko'rish [ADMIN]

META:
  GET    /integrations/meta                  — Scope va event ro'yxati

TASHQI KIRISH (API Key auth):
  GET    /integrations/external/animals      — scope: read:animals
  POST   /integrations/external/sensors      — scope: write:sensors
"""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import (
    get_current_active_user, require_manager, require_admin,
)
from app.core.database import get_db
from app.core.exceptions import PermissionDeniedError
from app.models.user import User
from app.schemas.integration import (
    APIKeyCreate, APIKeyUpdate,
    APIKeyResponse, APIKeyCreatedResponse, APIKeyListResponse,
    WebhookCreate, WebhookUpdate,
    WebhookResponse, WebhookListResponse, WebhookTestResponse,
    IntegrationMeta, SCOPE_META, EVENT_META,
)
from app.services.integration_service import IntegrationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations", tags=["Integrations"])

CurrentUser    = Annotated[User, Depends(get_current_active_user)]
CurrentManager = Annotated[User, Depends(require_manager)]
CurrentAdmin   = Annotated[User, Depends(require_admin)]
DB             = Annotated[AsyncSession, Depends(get_db)]


# =============================================================================
# META
# =============================================================================

@router.get(
    "/meta",
    response_model=IntegrationMeta,
    summary="Mavjud scope va voqealar ro'yxati",
)
async def get_meta(user: CurrentUser) -> IntegrationMeta:
    """Frontend uchun scope va webhook event ro'yxati."""
    return IntegrationMeta(scopes=SCOPE_META, events=EVENT_META)


# =============================================================================
# API KEYS
# =============================================================================

@router.get(
    "/api-keys",
    response_model=APIKeyListResponse,
    summary="API kalitlar ro'yxati",
)
async def list_api_keys(db: DB, user: CurrentAdmin) -> APIKeyListResponse:
    """Barcha API kalitlar. Raw kalit ko'rsatilmaydi."""
    return await IntegrationService(db).list_api_keys()


@router.post(
    "/api-keys",
    response_model=APIKeyCreatedResponse,
    status_code=201,
    summary="Yangi API kalit",
    description=(
        "Yangi API kalit yaratish. **raw_key FAQAT BIR MARTA ko'rsatiladi** — "
        "saqlash zarur, keyingi so'rovlarda qaytarilmaydi."
    ),
)
async def create_api_key(
    db:   DB,
    user: CurrentAdmin,
    data: APIKeyCreate,
) -> APIKeyCreatedResponse:
    """Yangi API kalit. Natijadagi raw_key ni saqlang."""
    return await IntegrationService(db).create_api_key(
        data,
        created_by = user.id,
        is_admin   = user.is_admin,
    )


@router.get(
    "/api-keys/{key_id}",
    response_model=APIKeyResponse,
    summary="Bitta API kalit",
)
async def get_api_key(db: DB, user: CurrentAdmin, key_id: int) -> APIKeyResponse:
    return await IntegrationService(db).get_api_key(key_id)


@router.patch(
    "/api-keys/{key_id}",
    response_model=APIKeyResponse,
    summary="API kalitni tahrirlash",
)
async def update_api_key(
    db:     DB,
    user:   CurrentAdmin,
    key_id: int,
    data:   APIKeyUpdate,
) -> APIKeyResponse:
    return await IntegrationService(db).update_api_key(key_id, data)


@router.delete(
    "/api-keys/{key_id}",
    status_code=204,
    summary="API kalitni o'chirish",
)
async def revoke_api_key(db: DB, user: CurrentAdmin, key_id: int) -> None:
    await IntegrationService(db).revoke_api_key(key_id)


# =============================================================================
# WEBHOOKS
# =============================================================================

@router.get(
    "/webhooks",
    response_model=WebhookListResponse,
    summary="Webhooklar ro'yxati",
)
async def list_webhooks(db: DB, user: CurrentManager) -> WebhookListResponse:
    return await IntegrationService(db).list_webhooks()


@router.post(
    "/webhooks",
    response_model=WebhookResponse,
    status_code=201,
    summary="Yangi webhook",
)
async def create_webhook(
    db:   DB,
    user: CurrentAdmin,
    data: WebhookCreate,
) -> WebhookResponse:
    return await IntegrationService(db).create_webhook(data, created_by=user.id)


@router.get(
    "/webhooks/{wh_id}",
    response_model=WebhookResponse,
    summary="Bitta webhook",
)
async def get_webhook(db: DB, user: CurrentManager, wh_id: int) -> WebhookResponse:
    return await IntegrationService(db).get_webhook(wh_id)


@router.get(
    "/webhooks/{wh_id}/secret",
    summary="Webhook HMAC secretini ko'rish",
    description="HMAC imzolash uchun secret. Faqat ADMIN ko'rishi mumkin.",
    response_model=dict,
)
async def get_webhook_secret(db: DB, user: CurrentAdmin, wh_id: int) -> dict:
    secret = await IntegrationService(db).get_webhook_secret(wh_id)
    return {"webhook_id": wh_id, "secret": secret}


@router.patch(
    "/webhooks/{wh_id}",
    response_model=WebhookResponse,
    summary="Webhookni tahrirlash",
)
async def update_webhook(
    db:    DB,
    user:  CurrentAdmin,
    wh_id: int,
    data:  WebhookUpdate,
) -> WebhookResponse:
    return await IntegrationService(db).update_webhook(wh_id, data)


@router.delete(
    "/webhooks/{wh_id}",
    status_code=204,
    summary="Webhookni o'chirish",
)
async def delete_webhook(db: DB, user: CurrentAdmin, wh_id: int) -> None:
    await IntegrationService(db).delete_webhook(wh_id)


@router.post(
    "/webhooks/{wh_id}/test",
    response_model=WebhookTestResponse,
    summary="Webhook test ping",
    description=(
        "Webhookga sinov so'rovi yuborish. "
        "Muvaffaqiyatsiz bo'lsa failure_count oshMaydi."
    ),
)
async def test_webhook(db: DB, user: CurrentAdmin, wh_id: int) -> WebhookTestResponse:
    return await IntegrationService(db).test_webhook(wh_id)


# =============================================================================
# TASHQI KIRISH — API Key autentifikatsiyasi
# =============================================================================

async def _get_api_key_auth(
    db:          AsyncSession,
    x_api_key:   Optional[str],
    required_scope: str,
):
    """
    X-API-Key header orqali tashqi autentifikatsiya.
    Header yo'q yoki noto'g'ri bo'lsa 403 qaytaradi.
    """
    if not x_api_key:
        raise PermissionDeniedError(
            "X-API-Key header talab qilinadi. "
            "Format: tv_live_<prefix>_<secret>"
        )
    return await IntegrationService(db).authenticate_key(x_api_key, required_scope)


@router.get(
    "/external/animals",
    summary="[Tashqi] Jonivorlar ro'yxati",
    description="API Key autentifikatsiya. Scope: `read:animals`",
    tags=["External API"],
)
async def external_list_animals(
    db:        DB,
    x_api_key: Annotated[Optional[str], Header()] = None,
):
    """
    Tashqi tizimlar uchun jonivorlar ro'yxati.
    JWT token o'rniga X-API-Key header ishlatiladi.
    """
    await _get_api_key_auth(db, x_api_key, "read:animals")

    from app.repositories.animal_repository import AnimalRepository
    from app.schemas.animal import AnimalListResponse
    animals = await AnimalRepository(db).get_all(active_only=True)
    return {
        "count":   len(animals),
        "animals": [
            {
                "id":      a.id,
                "tag_id":  a.tag_id,
                "species": a.species,
                "gender":  a.gender,
                "status":  a.status,
            }
            for a in animals
        ],
    }


@router.post(
    "/external/sensors",
    status_code=202,
    summary="[Tashqi] Sensor ma'lumot yuborish",
    description="IoT qurilmalar uchun. API Key scope: `write:sensors`",
    tags=["External API"],
)
async def external_push_sensor(
    db:        DB,
    payload:   dict,
    x_api_key: Annotated[Optional[str], Header()] = None,
):
    """
    IoT sensor qurilmasi ma'lumot yuborishi uchun endpoint.
    Payload: {camera_id, temperature, humidity, ...}
    """
    await _get_api_key_auth(db, x_api_key, "write:sensors")

    from workers.tasks.sensor_tasks import process_external_sensor_push
    process_external_sensor_push.delay(payload)

    return {"status": "accepted", "message": "Sensor ma'lumoti qabul qilindi"}


@router.get(
    "/external/alerts",
    summary="[Tashqi] Alertlar ro'yxati",
    description="API Key autentifikatsiya. Scope: `read:alerts`",
    tags=["External API"],
)
async def external_list_alerts(
    db:        DB,
    limit:     int = Query(20, ge=1, le=100),
    x_api_key: Annotated[Optional[str], Header()] = None,
):
    """Tashqi tizimlar uchun oxirgi alertlar."""
    await _get_api_key_auth(db, x_api_key, "read:alerts")

    from app.repositories.alert_repository import AlertRepository
    from app.models.alert import AlertStatus
    alerts = await AlertRepository(db).get_recent(limit=limit)
    return {
        "count":  len(alerts),
        "alerts": [
            {
                "id":        a.id,
                "type":      a.alert_type,
                "severity":  a.severity,
                "message":   a.message,
                "status":    a.status,
                "created_at":str(a.created_at),
            }
            for a in alerts
        ],
    }

# =============================================================================
# WEBHOOK DELIVERY LOGS
# =============================================================================

@router.get(
    "/webhooks/{webhook_id}/deliveries",
    summary="Webhook delivery tarixi",
)
async def get_webhook_deliveries(
    webhook_id: int,
    limit:      int = Query(50, ge=1, le=200),
    offset:     int = Query(0, ge=0),
    success:    Optional[bool] = Query(None, description="None=hammasi, true=muvaffaqiyatli, false=xato"),
    user:       CurrentManager = ...,
    db:         DB = ...,
) -> dict:
    """
    Webhook delivery loglarini qaytaradi.

    Oxirgi 200 ta yozuv saqlanadi.
    """
    from app.repositories.integration_repository import IntegrationRepository
    repo = IntegrationRepository(db)

    wh = await repo.get_webhook_by_id(webhook_id)
    if not wh:
        from fastapi import HTTPException
        from fastapi import status as http_status
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Webhook #{webhook_id} topilmadi")

    logs, total = await repo.get_delivery_logs(
        webhook_id = webhook_id,
        limit      = limit,
        offset     = offset,
        success    = success,
    )
    stats = await repo.get_delivery_stats(webhook_id)

    return {
        "webhook_id":   webhook_id,
        "webhook_name": wh.name,
        "stats":        stats,
        "total":        total,
        "items": [
            {
                "id":              log.id,
                "event_type":      log.event_type,
                "success":         log.success,
                "status_code":     log.status_code,
                "latency_ms":      log.latency_ms,
                "error_message":   log.error_message,
                "payload_preview": log.payload_preview,
                "delivery_id":     log.delivery_id,
                "created_at":      str(log.created_at),
            }
            for log in logs
        ],
    }