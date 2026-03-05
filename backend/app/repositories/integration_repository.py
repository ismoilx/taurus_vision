"""
Taurus Vision — Integration Repository

Faqat DB operatsiyalari. Biznes logika IntegrationService da.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.integration import APIKey, Webhook
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


# =============================================================================
# API KEY REPOSITORY
# =============================================================================

class APIKeyRepository:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, key: APIKey) -> APIKey:
        try:
            self.db.add(key)
            await self.db.flush()
            await self.db.refresh(key)
            return key
        except Exception as exc:
            raise DatabaseError(f"APIKey yaratishda xato: {exc}") from exc

    async def get_by_id(self, key_id: int) -> Optional[APIKey]:
        result = await self.db.execute(
            select(APIKey)
            .options(selectinload(APIKey.creator))
            .where(APIKey.id == key_id)
        )
        return result.scalar_one_or_none()

    async def get_by_prefix(self, prefix: str) -> Optional[APIKey]:
        """
        Prefix bo'yicha kalit topish (autentifikatsiya uchun).
        Faqat aktiv kalitlar qaytariladi.
        """
        result = await self.db.execute(
            select(APIKey).where(
                and_(
                    APIKey.key_prefix == prefix,
                    APIKey.is_active   == True,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_all(self, *, active_only: bool = False) -> list[APIKey]:
        q = select(APIKey).options(selectinload(APIKey.creator))
        if active_only:
            q = q.where(APIKey.is_active == True)
        q = q.order_by(APIKey.created_at.desc())
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def update(self, key: APIKey, fields: dict) -> APIKey:
        try:
            for k, v in fields.items():
                setattr(key, k, v)
            await self.db.flush()
            await self.db.refresh(key)
            return key
        except Exception as exc:
            raise DatabaseError(f"APIKey yangilashda xato: {exc}") from exc

    async def touch(self, key_id: int) -> None:
        """last_used_at va request_count ni atomik yangilash."""
        await self.db.execute(
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(
                last_used_at  = datetime.now(timezone.utc),
                request_count = APIKey.request_count + 1,
            )
        )

    async def delete(self, key: APIKey) -> None:
        try:
            await self.db.delete(key)
            await self.db.flush()
        except Exception as exc:
            raise DatabaseError(f"APIKey o'chirishda xato: {exc}") from exc


# =============================================================================
# WEBHOOK REPOSITORY
# =============================================================================

class WebhookRepository:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, wh: Webhook) -> Webhook:
        try:
            self.db.add(wh)
            await self.db.flush()
            await self.db.refresh(wh)
            return wh
        except Exception as exc:
            raise DatabaseError(f"Webhook yaratishda xato: {exc}") from exc

    async def get_by_id(self, wh_id: int) -> Optional[Webhook]:
        result = await self.db.execute(
            select(Webhook)
            .options(selectinload(Webhook.creator))
            .where(Webhook.id == wh_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, *, active_only: bool = False) -> list[Webhook]:
        q = select(Webhook).options(selectinload(Webhook.creator))
        if active_only:
            q = q.where(Webhook.is_active == True)
        q = q.order_by(Webhook.created_at.desc())
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_active_for_event(self, event: str) -> list[Webhook]:
        """
        Berilgan voqeani tinglayotgan barcha aktiv webhooklar.
        Webhook dispatch uchun ishlatiladi.
        """
        result = await self.db.execute(
            select(Webhook).where(Webhook.is_active == True)
        )
        all_wh = list(result.scalars().all())
        return [w for w in all_wh if event in (w.events or [])]

    async def update(self, wh: Webhook, fields: dict) -> Webhook:
        try:
            for k, v in fields.items():
                setattr(wh, k, v)
            await self.db.flush()
            await self.db.refresh(wh)
            return wh
        except Exception as exc:
            raise DatabaseError(f"Webhook yangilashda xato: {exc}") from exc

    async def record_delivery(
        self,
        wh_id:       int,
        success:     bool,
        status_code: Optional[int],
        error:       Optional[str],
    ) -> None:
        """
        Webhook yuborish natijasini yozish.
        Muvaffaqiyatsiz bo'lsa failure_count oshadi va
        5 dan oshsa avtomatik o'chiriladi.
        """
        wh = await self.get_by_id(wh_id)
        if not wh:
            return

        wh.last_triggered_at = datetime.now(timezone.utc)
        wh.last_status_code  = status_code
        wh.last_error        = error

        if success:
            wh.success_count  += 1
            wh.failure_count   = 0          # muvaffaqiyatda reset
        else:
            wh.failure_count  += 1
            if wh.failure_count >= 5:
                wh.is_active = False
                logger.warning(
                    f"Webhook #{wh_id} '{wh.name}' — 5 marta muvaffaqiyatsiz, "
                    f"avtomatik o'chirildi."
                )

        await self.db.flush()

    async def delete(self, wh: Webhook) -> None:
        try:
            await self.db.delete(wh)
            await self.db.flush()
        except Exception as exc:
            raise DatabaseError(f"Webhook o'chirishda xato: {exc}") from exc