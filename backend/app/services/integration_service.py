"""
Taurus Vision — Integration Service

JAVOBGARLIK:
  - APIKey CRUD + autentifikatsiya
  - Webhook CRUD + test ping + dispatch trigger
  - HMAC-SHA256 imzolash

XAVFSIZLIK:
  - API kalitlar hech qachon DB da oddiy text saqlanmaydi
  - HMAC imzo constant-time taqqoslash bilan tekshiriladi
  - Webhook URL faqat HTTPS qabul qilinadi
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import APIKey, Webhook
from app.repositories.integration_repository import (
    APIKeyRepository, WebhookRepository,
)
from app.schemas.integration import (
    APIKeyCreate, APIKeyUpdate,
    APIKeyResponse, APIKeyCreatedResponse, APIKeyListResponse,
    WebhookCreate, WebhookUpdate,
    WebhookResponse, WebhookListResponse, WebhookTestResponse,
)
from app.core.exceptions import (
    EntityNotFoundError, PermissionDeniedError, BusinessRuleViolationError,
)

logger = logging.getLogger(__name__)

# Webhook HTTP timeout
_WEBHOOK_TIMEOUT = 10.0  # soniya


# =============================================================================
# HELPERS
# =============================================================================

def _key_to_response(key: APIKey) -> APIKeyResponse:
    return APIKeyResponse(
        id            = key.id,
        name          = key.name,
        description   = key.description,
        key_prefix    = key.key_prefix,
        display_key   = key.display_key,
        scopes        = key.scopes or [],
        is_active     = key.is_active,
        expires_at    = key.expires_at,
        last_used_at  = key.last_used_at,
        request_count = key.request_count,
        created_by    = key.created_by,
        creator_name  = key.creator.full_name if key.creator else None,
        created_at    = key.created_at,
        updated_at    = key.updated_at,
    )


def _wh_to_response(wh: Webhook) -> WebhookResponse:
    return WebhookResponse(
        id                = wh.id,
        name              = wh.name,
        description       = wh.description,
        url               = wh.url,
        events            = wh.events or [],
        is_active         = wh.is_active,
        failure_count     = wh.failure_count,
        success_count     = wh.success_count,
        last_triggered_at = wh.last_triggered_at,
        last_status_code  = wh.last_status_code,
        last_error        = wh.last_error,
        health_status     = wh.health_status,
        created_by        = wh.created_by,
        creator_name      = wh.creator.full_name if wh.creator else None,
        created_at        = wh.created_at,
        updated_at        = wh.updated_at,
    )


def _sign_payload(secret: str, timestamp: int, body: str) -> str:
    """
    HMAC-SHA256 imzo yaratish.

    Imzo: sha256=<hex>
    Ma'lumot: f"{timestamp}.{body}"
    """
    message = f"{timestamp}.{body}".encode("utf-8")
    sig     = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


# =============================================================================
# INTEGRATION SERVICE
# =============================================================================

class IntegrationService:
    """
    APIKey va Webhook boshqaruvi uchun asosiy servis.

    Usage:
        svc = IntegrationService(db)
        created = await svc.create_api_key(data, admin_user.id, is_admin=True)
        await svc.dispatch_webhook("alert.created", payload)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db       = db
        self.keys     = APIKeyRepository(db)
        self.webhooks = WebhookRepository(db)

    # =========================================================================
    # API KEY — CRUD
    # =========================================================================

    async def create_api_key(
        self,
        data:       APIKeyCreate,
        created_by: int,
        is_admin:   bool = False,
    ) -> APIKeyCreatedResponse:
        """
        Yangi API kalit yaratish.

        "admin" scope faqat is_admin=True bo'lganda ruxsat etiladi.
        Raw kalit faqat shu methodda bir marta qaytariladi.

        Returns:
            APIKeyCreatedResponse (raw_key maydoni bilan)

        Raises:
            PermissionDeniedError: admin scope ni admin bo'lmagan yaratmoqchi
        """
        if "admin" in data.scopes and not is_admin:
            raise PermissionDeniedError(
                message="'admin' scope faqat ADMIN tomonidan yaratilishi mumkin."
            )

        raw_key = APIKey.generate_raw()
        prefix, key_hash = APIKey.parse_raw(raw_key)

        key = APIKey(
            name        = data.name,
            description = data.description,
            key_prefix  = prefix,
            key_hash    = key_hash,
            scopes      = data.scopes,
            expires_at  = data.expires_at,
            created_by  = created_by,
        )
        saved = await self.keys.create(key)
        saved = await self.keys.get_by_id(saved.id)

        logger.info(
            f"APIKey yaratildi: '{saved.name}' (prefix={prefix})",
            extra={"extra_data": {"id": saved.id, "by": created_by, "scopes": data.scopes}},
        )

        resp = _key_to_response(saved)
        return APIKeyCreatedResponse(**resp.model_dump(), raw_key=raw_key)

    async def list_api_keys(self) -> APIKeyListResponse:
        keys = await self.keys.list_all()
        return APIKeyListResponse(
            items=[_key_to_response(k) for k in keys],
            total=len(keys),
        )

    async def get_api_key(self, key_id: int) -> APIKeyResponse:
        key = await self.keys.get_by_id(key_id)
        if not key:
            raise EntityNotFoundError(f"APIKey #{key_id} topilmadi")
        return _key_to_response(key)

    async def update_api_key(
        self,
        key_id: int,
        data:   APIKeyUpdate,
    ) -> APIKeyResponse:
        key = await self.keys.get_by_id(key_id)
        if not key:
            raise EntityNotFoundError(f"APIKey #{key_id} topilmadi")
        fields = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
        updated = await self.keys.update(key, fields)
        updated = await self.keys.get_by_id(updated.id)
        return _key_to_response(updated)

    async def revoke_api_key(self, key_id: int) -> None:
        key = await self.keys.get_by_id(key_id)
        if not key:
            raise EntityNotFoundError(f"APIKey #{key_id} topilmadi")
        await self.keys.delete(key)
        logger.info(f"APIKey #{key_id} o'chirildi")

    # =========================================================================
    # API KEY — AUTENTIFIKATSIYA
    # =========================================================================

    async def authenticate_key(
        self,
        raw_key: str,
        required_scope: Optional[str] = None,
    ) -> APIKey:
        """
        Tashqi so'rov autentifikatsiyasi.

        Oqim:
          1. Prefix ajratib olish
          2. DB dan prefix bo'yicha topish
          3. SHA-256 hash solishtirish (constant-time)
          4. Muddatni tekshirish
          5. Scope tekshirish
          6. last_used_at yangilash (background, xato bo'lsa e'tibor bermaslik)

        Args:
            raw_key:        "tv_live_<prefix>_<secret>" formatidagi kalit
            required_scope: agar berilsa, kalit shu scopeга ega bo'lishi kerak

        Returns:
            Tekshirilgan APIKey instance

        Raises:
            PermissionDeniedError: kalit noto'g'ri, muddati tugagan yoki scope yo'q
        """
        try:
            prefix = APIKey.extract_prefix(raw_key)
        except ValueError:
            raise PermissionDeniedError("Noto'g'ri API kalit formati")

        key = await self.keys.get_by_prefix(prefix)

        # Constant-time taqqoslash (timing attack dan himoya)
        expected_hash = APIKey.hash_key(raw_key)
        if not key or not hmac.compare_digest(key.key_hash, expected_hash):
            raise PermissionDeniedError("API kalit noto'g'ri yoki faol emas")

        # Muddatni tekshirish
        if key.expires_at and datetime.now(timezone.utc) > key.expires_at:
            raise PermissionDeniedError("API kalit muddati tugagan")

        # Scope tekshirish
        if required_scope and not key.has_scope(required_scope):
            raise PermissionDeniedError(
                f"Bu amal uchun '{required_scope}' scope talab qilinadi"
            )

        # Statistikani background da yangilash
        try:
            await self.keys.touch(key.id)
        except Exception:
            pass  # statistika xatosi asosiy javobni bloklamasin

        return key

    # =========================================================================
    # WEBHOOK — CRUD
    # =========================================================================

    async def create_webhook(
        self,
        data:       WebhookCreate,
        created_by: int,
    ) -> WebhookResponse:
        """
        Yangi webhook yaratish.
        Secret avtomatik generatsiya qilinadi (foydalanuvchi bermaydi).
        """
        secret = secrets.token_hex(32)  # 64 belgilik hex

        wh = Webhook(
            name        = data.name,
            description = data.description,
            url         = data.url,
            secret      = secret,
            events      = data.events,
            created_by  = created_by,
        )
        saved = await self.webhooks.create(wh)
        saved = await self.webhooks.get_by_id(saved.id)

        logger.info(
            f"Webhook yaratildi: '{saved.name}' → {saved.url[:40]}",
            extra={"extra_data": {"id": saved.id, "events": data.events}},
        )
        return _wh_to_response(saved)

    async def list_webhooks(self) -> WebhookListResponse:
        whs = await self.webhooks.list_all()
        return WebhookListResponse(
            items=[_wh_to_response(w) for w in whs],
            total=len(whs),
        )

    async def get_webhook(self, wh_id: int) -> WebhookResponse:
        wh = await self.webhooks.get_by_id(wh_id)
        if not wh:
            raise EntityNotFoundError(f"Webhook #{wh_id} topilmadi")
        return _wh_to_response(wh)

    async def get_webhook_secret(self, wh_id: int) -> str:
        """HMAC secret ni qaytarish (faqat ADMIN ko'rishi mumkin)."""
        wh = await self.webhooks.get_by_id(wh_id)
        if not wh:
            raise EntityNotFoundError(f"Webhook #{wh_id} topilmadi")
        return wh.secret

    async def update_webhook(
        self,
        wh_id: int,
        data:  WebhookUpdate,
    ) -> WebhookResponse:
        wh = await self.webhooks.get_by_id(wh_id)
        if not wh:
            raise EntityNotFoundError(f"Webhook #{wh_id} topilmadi")
        fields = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
        updated = await self.webhooks.update(wh, fields)
        updated = await self.webhooks.get_by_id(updated.id)
        return _wh_to_response(updated)

    async def delete_webhook(self, wh_id: int) -> None:
        wh = await self.webhooks.get_by_id(wh_id)
        if not wh:
            raise EntityNotFoundError(f"Webhook #{wh_id} topilmadi")
        await self.webhooks.delete(wh)
        logger.info(f"Webhook #{wh_id} o'chirildi")

    # =========================================================================
    # WEBHOOK — TEST PING
    # =========================================================================

    async def test_webhook(self, wh_id: int) -> WebhookTestResponse:
        """
        Webhookni sinov ping bilan tekshirish.

        Test payload yuboriladi, natija WebhookTestResponse da qaytariladi.
        Muvaffaqiyatsiz bo'lsa failure_count oshMaydi (sinov, haqiqiy emas).
        """
        wh = await self.webhooks.get_by_id(wh_id)
        if not wh:
            raise EntityNotFoundError(f"Webhook #{wh_id} topilmadi")

        payload = {
            "event":    "ping",
            "delivery": str(uuid.uuid4()),
            "timestamp": int(time.time()),
            "data":     {"message": "Taurus Vision webhook test ping"},
        }

        start_ms = int(time.time() * 1000)

        try:
            body_str  = json.dumps(payload, ensure_ascii=False)
            ts        = payload["timestamp"]
            signature = _sign_payload(wh.secret, ts, body_str)

            async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT) as client:
                resp = await client.post(
                    wh.url,
                    content=body_str.encode("utf-8"),
                    headers={
                        "Content-Type":       "application/json",
                        "X-Taurus-Event":     "ping",
                        "X-Taurus-Signature": signature,
                        "X-Taurus-Delivery":  payload["delivery"],
                        "X-Taurus-Timestamp": str(ts),
                        "User-Agent":         "TaurusVision-Webhook/1.0",
                    },
                )
            latency = int(time.time() * 1000) - start_ms
            success = 200 <= resp.status_code < 300

            return WebhookTestResponse(
                success     = success,
                status_code = resp.status_code,
                latency_ms  = latency,
                error       = None if success else f"HTTP {resp.status_code}",
            )

        except httpx.TimeoutException:
            return WebhookTestResponse(
                success=False, status_code=None,
                latency_ms=int(time.time() * 1000) - start_ms,
                error=f"Timeout ({_WEBHOOK_TIMEOUT}s dan oshdi)",
            )
        except httpx.ConnectError as e:
            return WebhookTestResponse(
                success=False, status_code=None, latency_ms=None,
                error=f"Ulanib bo'lmadi: {e}",
            )
        except Exception as e:
            return WebhookTestResponse(
                success=False, status_code=None, latency_ms=None,
                error=str(e),
            )

    # =========================================================================
    # WEBHOOK — DISPATCH (tashqi chaqiruvlar uchun)
    # =========================================================================

    @staticmethod
    async def dispatch_event(event: str, payload: dict) -> None:
        """
        Voqeani barcha aktiv webhooklarga yuborish.

        Bu method Celery task dan chaqiriladi.
        Har bir webhook uchun alohida HTTP so'rov yuboriladi.

        Args:
            event:   WebhookEvent qiymati (masalan: "alert.created")
            payload: Voqea ma'lumotlari
        """
        from app.core.database import AsyncSessionFactory
        async with AsyncSessionFactory() as db:
            repo = WebhookRepository(db)
            whs  = await repo.get_active_for_event(event)

            if not whs:
                return

            logger.info(f"Webhook dispatch: event={event}, webhooks={len(whs)}")

            for wh in whs:
                try:
                    await _send_webhook(wh, event, payload)
                    await repo.record_delivery(wh.id, True, 200, None)
                    await db.commit()
                except Exception as exc:
                    err_msg = str(exc)[:480]
                    logger.warning(f"Webhook #{wh.id} xatosi: {err_msg}")
                    status = getattr(exc, "status_code", None)
                    await repo.record_delivery(wh.id, False, status, err_msg)
                    await db.commit()


async def _send_webhook(wh: Webhook, event: str, data: dict) -> None:
    """Bitta webhookga HTTP POST yuborish."""
    delivery_id = str(uuid.uuid4())
    timestamp   = int(time.time())
    envelope    = {
        "event":    event,
        "delivery": delivery_id,
        "timestamp": timestamp,
        "data":     data,
    }

    body_str  = json.dumps(envelope, ensure_ascii=False, default=str)
    signature = _sign_payload(wh.secret, timestamp, body_str)

    async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT) as client:
        resp = await client.post(
            wh.url,
            content=body_str.encode("utf-8"),
            headers={
                "Content-Type":       "application/json",
                "X-Taurus-Event":     event,
                "X-Taurus-Signature": signature,
                "X-Taurus-Delivery":  delivery_id,
                "X-Taurus-Timestamp": str(timestamp),
                "User-Agent":         "TaurusVision-Webhook/1.0",
            },
        )

    if not (200 <= resp.status_code < 300):
        err = httpx.HTTPStatusError(
            f"HTTP {resp.status_code}",
            request=resp.request,
            response=resp,
        )
        err.status_code = resp.status_code  # type: ignore[attr-defined]
        raise err