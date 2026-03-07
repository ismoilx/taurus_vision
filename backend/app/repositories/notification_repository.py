"""
Taurus Vision — Notification Repository

Faqat DB operatsiyalari. Biznes logika YO'Q.

JAVOBGARLIK:
    SELECT / INSERT / UPDATE / DELETE — Notification jadvali uchun.

PATTERN:
    NotificationService → NotificationRepository → SQLAlchemy → PostgreSQL
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType, NotificationEntityType
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class NotificationRepository:
    """
    Notification entity uchun DB operatsiyalar qatlami.

    Barcha metodlar async, to'liq type-annotated.
    Xatolar DatabaseError ga wrap qilinadi.

    Args:
        db: AsyncSession injected via FastAPI Depends()
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create(
        self,
        *,
        user_id:     Optional[int],
        n_type:      NotificationType,
        title:       str,
        message:     str,
        entity_type: Optional[NotificationEntityType] = None,
        entity_id:   Optional[int]                    = None,
        action_url:  Optional[str]                    = None,
        extra_data:  Optional[dict]                   = None,
    ) -> Notification:
        """
        Yangi notification yaratish.

        Args:
            user_id:     Manzil foydalanuvchi (None = broadcast)
            n_type:      Notification turi
            title:       Sarlavha
            message:     To'liq xabar
            entity_type: Bog'liq entity turi
            entity_id:   Bog'liq entity ID
            action_url:  Frontend havolasi
            extra_data:  Qo'shimcha JSON

        Returns:
            Yaratilgan Notification instance

        Raises:
            DatabaseError: DB xatosi
        """
        try:
            notif = Notification(
                user_id     = user_id,
                n_type      = n_type,
                title       = title,
                message     = message,
                entity_type = entity_type,
                entity_id   = entity_id,
                action_url  = action_url,
                extra_data  = extra_data,
                is_read     = False,
                is_dismissed= False,
            )
            self.db.add(notif)
            await self.db.flush()
            await self.db.refresh(notif)
            return notif
        except Exception as exc:
            logger.error(f"Notification yaratishda xato: {exc}", exc_info=True)
            raise DatabaseError(message="Notification yaratib bo'lmadi.") from exc

    async def bulk_create(
        self,
        notifications: list[dict],
    ) -> list[Notification]:
        """
        Bir vaqtda bir nechta notification yaratish.

        Broadcast xabarlar uchun ishlatiladi.

        Args:
            notifications: Har biri {user_id, n_type, title, message, ...}

        Returns:
            Yaratilgan Notification list

        Raises:
            DatabaseError: DB xatosi
        """
        try:
            created = []
            for data in notifications:
                notif = Notification(**data)
                self.db.add(notif)
                created.append(notif)
            await self.db.flush()
            return created
        except Exception as exc:
            logger.error(f"Bulk notification yaratishda xato: {exc}", exc_info=True)
            raise DatabaseError(message="Bulk notification yaratib bo'lmadi.") from exc

    # =========================================================================
    # READ
    # =========================================================================

    async def get_by_id(self, notification_id: int) -> Optional[Notification]:
        """
        ID bo'yicha notification olish.

        Args:
            notification_id: Notification ID

        Returns:
            Notification yoki None
        """
        result = await self.db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.is_dismissed == False,
            )
        )
        return result.scalar_one_or_none()

    async def get_for_user(
        self,
        user_id:      int,
        *,
        limit:        int           = 30,
        offset:       int           = 0,
        unread_only:  bool          = False,
        n_type:       Optional[NotificationType] = None,
    ) -> list[Notification]:
        """
        Foydalanuvchi uchun notificationlar (shaxsiy + broadcast).

        Args:
            user_id:     Foydalanuvchi ID
            limit:       Sahifadagi natijalar soni
            offset:      Sahifalash offset
            unread_only: Faqat o'qilmaganlarni qaytarish
            n_type:      Tur bo'yicha filtr

        Returns:
            Notification list, yangi → eski tartibda
        """
        # Shaxsiy + broadcast (user_id=NULL) notificationlar
        cond = and_(
            or_(
                Notification.user_id == user_id,
                Notification.user_id.is_(None),
            ),
            Notification.is_dismissed == False,
        )

        if unread_only:
            cond = and_(cond, Notification.is_read == False)

        if n_type:
            cond = and_(cond, Notification.n_type == n_type)

        result = await self.db.execute(
            select(Notification)
            .where(cond)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_unread(self, user_id: int) -> int:
        """
        Foydalanuvchining o'qilmagan notificationlar soni.

        WebSocket va badge uchun ishlatiladi.

        Args:
            user_id: Foydalanuvchi ID

        Returns:
            O'qilmagan notification soni
        """
        result = await self.db.execute(
            select(func.count(Notification.id)).where(
                or_(
                    Notification.user_id == user_id,
                    Notification.user_id.is_(None),
                ),
                Notification.is_read      == False,
                Notification.is_dismissed == False,
            )
        )
        return result.scalar_one() or 0

    async def count_total(self, user_id: int) -> int:
        """
        Foydalanuvchi notificationlari umumiy soni.

        Args:
            user_id: Foydalanuvchi ID

        Returns:
            Umumiy son
        """
        result = await self.db.execute(
            select(func.count(Notification.id)).where(
                or_(
                    Notification.user_id == user_id,
                    Notification.user_id.is_(None),
                ),
                Notification.is_dismissed == False,
            )
        )
        return result.scalar_one() or 0

    # =========================================================================
    # UPDATE
    # =========================================================================

    async def mark_as_read(
        self,
        notification_id: int,
        user_id:         int,
    ) -> bool:
        """
        Bitta notificationni o'qilgan deb belgilash.

        Args:
            notification_id: Notification ID
            user_id:         Foydalanuvchi ID (xavfsizlik uchun)

        Returns:
            True — yangilandi, False — topilmadi
        """
        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.id       == notification_id,
                or_(
                    Notification.user_id == user_id,
                    Notification.user_id.is_(None),
                ),
                Notification.is_read  == False,
            )
            .values(
                is_read = True,
                read_at = datetime.now(timezone.utc),
            )
        )
        return (result.rowcount or 0) > 0

    async def mark_all_as_read(self, user_id: int) -> int:
        """
        Foydalanuvchining barcha notificationlarini o'qilgan deb belgilash.

        Args:
            user_id: Foydalanuvchi ID

        Returns:
            Yangilangan yozuvlar soni
        """
        result = await self.db.execute(
            update(Notification)
            .where(
                or_(
                    Notification.user_id == user_id,
                    Notification.user_id.is_(None),
                ),
                Notification.is_read      == False,
                Notification.is_dismissed == False,
            )
            .values(
                is_read = True,
                read_at = datetime.now(timezone.utc),
            )
        )
        return result.rowcount or 0

    async def dismiss(
        self,
        notification_id: int,
        user_id:         int,
    ) -> bool:
        """
        Notificationni yashirish (arxivlash).

        Args:
            notification_id: Notification ID
            user_id:         Foydalanuvchi ID

        Returns:
            True — arxivlandi
        """
        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                or_(
                    Notification.user_id == user_id,
                    Notification.user_id.is_(None),
                ),
            )
            .values(is_dismissed=True)
        )
        return (result.rowcount or 0) > 0

    async def dismiss_all(self, user_id: int) -> int:
        """
        Foydalanuvchining barcha notificationlarini yashirish.

        Args:
            user_id: Foydalanuvchi ID

        Returns:
            Arxivlangan yozuvlar soni
        """
        result = await self.db.execute(
            update(Notification)
            .where(
                or_(
                    Notification.user_id == user_id,
                    Notification.user_id.is_(None),
                ),
                Notification.is_dismissed == False,
            )
            .values(is_dismissed=True)
        )
        return result.rowcount or 0

    # =========================================================================
    # CLEANUP
    # =========================================================================

    async def delete_old(self, days: int = 30) -> int:
        """
        30 kundan eski arxivlangan notificationlarni o'chirish.

        Celery Beat task tomonidan chaqiriladi.

        Args:
            days: Necha kundan eski yozuvlar o'chirilsin

        Returns:
            O'chirilgan yozuvlar soni
        """
        from sqlalchemy import delete
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            delete(Notification).where(
                Notification.is_dismissed == True,
                Notification.created_at   < cutoff,
            )
        )
        return result.rowcount or 0