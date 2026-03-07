"""
Taurus Vision — In-App Notification Service

In-app bildirishnomalar biznes logikasi.

Bu servis notification_service.py (email) dan ALOHIDA.
Email → notification_service.py
In-app → bu fayl (inapp_notification_service.py)

FOYDALANISH (endpoint yoki boshqa service dan):

    from app.services.inapp_notification_service import InAppNotificationService

    svc = InAppNotificationService(db)

    # Bitta foydalanuvchiga
    await svc.notify_user(
        user_id     = user.id,
        n_type      = NotificationType.ALERT,
        title       = "Jonivor ko'rinmayapti",
        message     = "Buzoq-07 24 soatdan beri kamerada ko'rinmadi.",
        entity_type = NotificationEntityType.ANIMAL,
        entity_id   = 7,
        action_url  = "/animals/7",
    )

    # Barcha foydalanuvchilarga broadcast
    await svc.broadcast(
        n_type  = NotificationType.SYSTEM,
        title   = "Tizim yangilandi",
        message = "Taurus Vision v2.5 yangi funksiyalar bilan ishga tushdi.",
    )

WEBSOCKET INTEGRATSIYA:
    Notification yaratilganda WebSocket orqali real-time push yuboriladi.
    Frontend badge avtomatik yangilanadi.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import (
    Notification,
    NotificationType,
    NotificationEntityType,
)
from app.repositories.notification_repository import NotificationRepository
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class InAppNotificationService:
    """
    In-app bildirishnomalar servis qatlami.

    Barcha metodlar async, try/except bilan himoyalangan.
    Xato chiqsa — log yozadi, tizimni to'xtatmaydi.

    Args:
        db: AsyncSession (FastAPI Depends() orqali)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db   = db
        self.repo = NotificationRepository(db)

    # =========================================================================
    # NOTIFICATION YARATISH
    # =========================================================================

    async def notify_user(
        self,
        *,
        user_id:     int,
        n_type:      NotificationType,
        title:       str,
        message:     str,
        entity_type: Optional[NotificationEntityType] = None,
        entity_id:   Optional[int]                    = None,
        action_url:  Optional[str]                    = None,
        extra_data:  Optional[dict]                   = None,
    ) -> Notification:
        """
        Bitta foydalanuvchiga notification yuborish.

        DB ga yozilgandan so'ng WebSocket orqali real-time push.

        Args:
            user_id:     Manzil foydalanuvchi ID
            n_type:      Notification turi
            title:       Sarlavha
            message:     To'liq xabar
            entity_type: Bog'liq entity turi (ixtiyoriy)
            entity_id:   Bog'liq entity ID (ixtiyoriy)
            action_url:  Frontend havolasi (ixtiyoriy)
            extra_data:  Qo'shimcha JSON (ixtiyoriy)

        Returns:
            Yaratilgan Notification

        Raises:
            DatabaseError: DB xatosi
        """
        notif = await self.repo.create(
            user_id     = user_id,
            n_type      = n_type,
            title       = title,
            message     = message,
            entity_type = entity_type,
            entity_id   = entity_id,
            action_url  = action_url,
            extra_data  = extra_data,
        )
        await self.db.commit()
        await self.db.refresh(notif)

        # WebSocket push — xato chiqsa tizimni to'xtatmaymiz
        await self._push_ws(user_id=user_id, notification=notif)

        logger.info(
            f"In-app notification yaratildi",
            extra={"extra_data": {
                "notif_id": notif.id,
                "user_id":  user_id,
                "type":     n_type.value,
                "title":    title,
            }},
        )
        return notif

    async def broadcast(
        self,
        *,
        n_type:      NotificationType,
        title:       str,
        message:     str,
        entity_type: Optional[NotificationEntityType] = None,
        entity_id:   Optional[int]                    = None,
        action_url:  Optional[str]                    = None,
        extra_data:  Optional[dict]                   = None,
    ) -> Notification:
        """
        Barcha foydalanuvchilarga broadcast notification yuborish.

        user_id = NULL — barcha foydalanuvchilar ko'radi.

        Args:
            n_type:   Notification turi
            title:    Sarlavha
            message:  To'liq xabar
            (boshqalar ixtiyoriy)

        Returns:
            Yaratilgan broadcast Notification
        """
        notif = await self.repo.create(
            user_id     = None,          # NULL = broadcast
            n_type      = n_type,
            title       = title,
            message     = message,
            entity_type = entity_type,
            entity_id   = entity_id,
            action_url  = action_url,
            extra_data  = extra_data,
        )
        await self.db.commit()
        await self.db.refresh(notif)

        # Barcha ulangan clientlarga WebSocket push
        await self._broadcast_ws(notification=notif)

        logger.info(
            f"Broadcast notification yaratildi: {title}",
            extra={"extra_data": {
                "notif_id": notif.id,
                "type":     n_type.value,
            }},
        )
        return notif

    # =========================================================================
    # NOTIFICATION O'QISH
    # =========================================================================

    async def get_user_notifications(
        self,
        user_id:     int,
        *,
        limit:       int           = 30,
        offset:      int           = 0,
        unread_only: bool          = False,
        n_type:      Optional[NotificationType] = None,
    ) -> dict:
        """
        Foydalanuvchi notificationlarini pagination bilan qaytarish.

        Args:
            user_id:     Foydalanuvchi ID
            limit:       Sahifadagi elementlar soni
            offset:      Sahifalash offset
            unread_only: Faqat o'qilmaganlar
            n_type:      Tur bo'yicha filtr

        Returns:
            {items, total, unread_count, page, limit, has_more}
        """
        items        = await self.repo.get_for_user(
            user_id, limit=limit, offset=offset,
            unread_only=unread_only, n_type=n_type,
        )
        total        = await self.repo.count_total(user_id)
        unread_count = await self.repo.count_unread(user_id)

        return {
            "items":        items,
            "total":        total,
            "unread_count": unread_count,
            "page":         offset // limit + 1,
            "limit":        limit,
            "has_more":     (offset + limit) < total,
        }

    async def get_unread_count(self, user_id: int) -> dict:
        """
        Badge uchun o'qilmagan notification soni.

        Args:
            user_id: Foydalanuvchi ID

        Returns:
            {"unread_count": int, "total": int}
        """
        return {
            "unread_count": await self.repo.count_unread(user_id),
            "total":        await self.repo.count_total(user_id),
        }

    # =========================================================================
    # NOTIFICATION YANGILASH
    # =========================================================================

    async def mark_as_read(self, notification_id: int, user_id: int) -> bool:
        """
        Bitta notificationni o'qilgan deb belgilash.

        Args:
            notification_id: Notification ID
            user_id:         Foydalanuvchi ID

        Returns:
            True — yangilandi, False — topilmadi yoki allaqachon o'qilgan
        """
        updated = await self.repo.mark_as_read(notification_id, user_id)
        if updated:
            await self.db.commit()
        return updated

    async def mark_all_as_read(self, user_id: int) -> int:
        """
        Foydalanuvchining barcha notificationlarini o'qilgan deb belgilash.

        Args:
            user_id: Foydalanuvchi ID

        Returns:
            Yangilangan yozuvlar soni
        """
        count = await self.repo.mark_all_as_read(user_id)
        if count:
            await self.db.commit()
        logger.info(f"User {user_id} barcha {count} ta notification o'qildi")
        return count

    async def dismiss(self, notification_id: int, user_id: int) -> bool:
        """
        Notificationni yashirish.

        Args:
            notification_id: Notification ID
            user_id:         Foydalanuvchi ID

        Returns:
            True — yashirildi
        """
        dismissed = await self.repo.dismiss(notification_id, user_id)
        if dismissed:
            await self.db.commit()
        return dismissed

    async def dismiss_all(self, user_id: int) -> int:
        """
        Foydalanuvchining barcha notificationlarini yashirish.

        Args:
            user_id: Foydalanuvchi ID

        Returns:
            Yashirilgan yozuvlar soni
        """
        count = await self.repo.dismiss_all(user_id)
        if count:
            await self.db.commit()
        return count

    # =========================================================================
    # WEBSOCKET PUSH (ICHKI YORDAMCHI)
    # =========================================================================

    async def _push_ws(self, user_id: int, notification: Notification) -> None:
        """
        Bitta foydalanuvchiga WebSocket orqali real-time push.

        Xato chiqsa — faqat log, tizimni to'xtatmaydi.

        Args:
            user_id:      Manzil foydalanuvchi ID
            notification: Notification instance
        """
        try:
            from app.api.v1.websocket import get_ws_manager
            ws_manager = get_ws_manager()
            if ws_manager is None:
                return

            await ws_manager.send_to_all({
                "type":            "notification",
                "notification_id": notification.id,
                "n_type":          notification.n_type.value,
                "title":           notification.title,
                "message":         notification.message,
                "entity_type":     notification.entity_type.value if notification.entity_type else None,
                "entity_id":       notification.entity_id,
                "action_url":      notification.action_url,
                "created_at":      notification.created_at.isoformat() if notification.created_at else None,
            })
        except Exception as exc:
            logger.warning(f"WebSocket push xatosi (tizimga ta'sir qilmaydi): {exc}")

    async def _broadcast_ws(self, notification: Notification) -> None:
        """
        Barcha ulangan clientlarga WebSocket push.

        Args:
            notification: Broadcast Notification instance
        """
        try:
            from app.api.v1.websocket import get_ws_manager
            ws_manager = get_ws_manager()
            if ws_manager is None:
                return

            await ws_manager.send_to_all({
                "type":            "notification",
                "broadcast":       True,
                "notification_id": notification.id,
                "n_type":          notification.n_type.value,
                "title":           notification.title,
                "message":         notification.message,
                "entity_type":     notification.entity_type.value if notification.entity_type else None,
                "entity_id":       notification.entity_id,
                "action_url":      notification.action_url,
                "created_at":      notification.created_at.isoformat() if notification.created_at else None,
            })
        except Exception as exc:
            logger.warning(f"Broadcast WebSocket push xatosi: {exc}")

    # =========================================================================
    # TIZIM YORDAMCHI METODLAR
    # =========================================================================

    async def notify_alert_created(
        self,
        user_id:    int,
        alert_id:   int,
        title:      str,
        message:    str,
        severity:   str,
        animal_id:  Optional[int] = None,
    ) -> None:
        """
        Yangi alert yaratilganda in-app notification yuborish.

        AlertService dan chaqiriladi.

        Args:
            user_id:   Manzil foydalanuvchi
            alert_id:  Alert ID
            title:     Alert sarlavhasi
            message:   Alert xabari
            severity:  Alert darajasi (critical/high/medium/low)
            animal_id: Bog'liq jonivor ID
        """
        n_type_map = {
            "critical": NotificationType.ALERT,
            "high":     NotificationType.ALERT,
            "medium":   NotificationType.WARNING,
            "low":      NotificationType.INFO,
        }
        await self.notify_user(
            user_id     = user_id,
            n_type      = n_type_map.get(severity, NotificationType.WARNING),
            title       = title,
            message     = message,
            entity_type = NotificationEntityType.ALERT,
            entity_id   = alert_id,
            action_url  = f"/alerts",
            extra_data  = {
                "alert_id":  alert_id,
                "severity":  severity,
                "animal_id": animal_id,
            },
        )