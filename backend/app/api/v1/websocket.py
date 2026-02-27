"""
Taurus Vision — WebSocket Connection Manager

Real-time yangilanishlarni barcha ulangan clientlarga yuborish uchun
markaziy infratuzilma.

DIZAYN PRINSIPLARI:
    - broadcast() xabarni aynan kelgan formatda yuboradi (wrapper YO'Q)
    - Caller (detection_pipeline) to'liq xabar strukturasini o'zi belgilaydi
    - Lock asosida thread-safe ulanish boshqaruvi
    - Nosoz ulanishlar avtomatik tozalanadi

XABAR FORMATI (broadcast qiluvchi tom belgilaydi):
    {
        "type": "detection",       # yoki "heartbeat", "connection", ...
        "timestamp": "...",
        "animal_id": 1,
        ...
    }
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


# =============================================================================
# JSON SERIALIZER — datetime qo'llab-quvvatlash bilan
# =============================================================================

class _DateTimeEncoder(json.JSONEncoder):
    """datetime ob'ektlarini ISO format stringga o'giradi."""

    def default(self, obj: object) -> object:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


# =============================================================================
# CONNECTION MANAGER
# =============================================================================

class ConnectionManager:
    """
    WebSocket ulanishlarini boshqaradi va xabarlarni broadcast qiladi.

    XUSUSIYATLAR:
        - Ko'p simultaneous ulanishlarni qo'llab-quvvatlash
        - asyncio.Lock asosida thread-safe operatsiyalar
        - Broadcast paytida nosoz ulanishlar avtomatik tozalanadi
        - Heartbeat mexanizmi ulanishlarni tirik ushlab turadi

    FOYDALANISH:
        manager = ConnectionManager()
        await manager.connect(websocket)
        await manager.broadcast({"type": "detection", ...})
    """

    def __init__(self) -> None:
        self._active: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._total_connected    = 0
        self._total_disconnected = 0
        self._total_sent         = 0

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def connect(self, websocket: WebSocket) -> None:
        """
        Yangi WebSocket ulanishini qabul qiladi va ro'yxatga oladi.

        Handshake (accept) bu yerda bajariladi — caller ACCEPT QILMAYDI.

        Args:
            websocket: FastAPI WebSocket ob'ekti

        Raises:
            Exception: accept() muvaffaqiyatsiz bo'lsa
        """
        await websocket.accept()

        async with self._lock:
            self._active.add(websocket)
            self._total_connected += 1
            count = len(self._active)

        logger.info(
            "WebSocket connected",
            extra={"extra_data": {"active_connections": count}},
        )

        await self._send_to(websocket, {
            "type":               "connection",
            "status":             "connected",
            "message":            "Taurus Vision live feed ga ulandi",
            "active_connections": count,
            "timestamp":          datetime.utcnow().isoformat(),
        })

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        WebSocket ulanishini ro'yxatdan chiqaradi.

        Args:
            websocket: Chiqariladigan ulanish
        """
        async with self._lock:
            self._active.discard(websocket)
            self._total_disconnected += 1
            count = len(self._active)

        logger.info(
            "WebSocket disconnected",
            extra={"extra_data": {"active_connections": count}},
        )

    async def broadcast(self, message: dict) -> None:
        """
        Xabarni barcha faol clientlarga yuboradi.

        MUHIM: Xabar aynan kelgan formatda yuboriladi — hech qanday
        wrapper qo'shilmaydi. Caller to'liq xabar strukturasini belgilaydi.

        Args:
            message: JSON serializatsiya qilinadigan dict
        """
        async with self._lock:
            if not self._active:
                return
            snapshot = set(self._active)

        try:
            json_str = json.dumps(message, cls=_DateTimeEncoder)
        except (TypeError, ValueError) as exc:
            logger.error(
                "WebSocket broadcast: JSON serialize xatosi",
                extra={"extra_data": {"error": str(exc)}},
            )
            return

        failed: set[WebSocket] = set()

        for ws in snapshot:
            try:
                await ws.send_text(json_str)
                self._total_sent += 1
            except (WebSocketDisconnect, RuntimeError):
                failed.add(ws)
            except Exception as exc:
                failed.add(ws)
                logger.warning(
                    "Broadcast: xabar yuborishda xato",
                    extra={"extra_data": {"error": str(exc)}},
                )

        if failed:
            async with self._lock:
                self._active -= failed
            logger.info(
                "Broadcast: nosoz ulanishlar tozalandi",
                extra={"extra_data": {
                    "removed":   len(failed),
                    "remaining": len(self._active),
                }},
            )

    async def broadcast_alert(self, alert: object) -> None:
        """
        Yangi alert haqida barcha clientlarga real-time xabar yuboradi.

        alert_service._ensure_alert() tomonidan yangi alert yaratilganda
        avtomatik chaqiriladi. Frontend AlertsPage real-time yangilanadi.

        Args:
            alert: Alert ORM instance — id, alert_type, severity,
                   title, description, animal_id, camera_id,
                   triggered_at maydonlari ishlatiladi.
        """
        try:
            triggered_at = getattr(alert, "triggered_at", None)
            await self.broadcast({
                "type":        "alert",
                "alert_id":    getattr(alert, "id",          None),
                "alert_type":  getattr(alert, "alert_type",  None),
                "severity":    getattr(alert, "severity",    None),
                "title":       getattr(alert, "title",       None),
                "description": getattr(alert, "description", None),
                "animal_id":   getattr(alert, "animal_id",   None),
                "camera_id":   getattr(alert, "camera_id",   None),
                "timestamp":   triggered_at.isoformat() if triggered_at else datetime.utcnow().isoformat(),
            })
        except Exception as exc:
            logger.warning(
                "broadcast_alert xatosi — asosiy oqim ta'sirlanmaydi",
                extra={"extra_data": {"error": str(exc)}},
            )

    async def broadcast_health_update(
        self,
        animal_id: int,
        health_score: int,
        health_status: str,
        record_id: int | None = None,
    ) -> None:
        """
        Jonivor sog'liq holati yangilanganda barcha clientlarga xabar beradi.

        HealthRecordService.create_health_record() tomonidan chaqiriladi.
        Frontend AnimalDetailPage va HealthPage real-time yangilanadi.

        Args:
            animal_id:     Jonivor ID
            health_score:  Hozirgi sog'liq bali (0-100)
            health_status: Holat matni (excellent/good/fair/poor/critical)
            record_id:     Yangi health record ID (ixtiyoriy)
        """
        await self.broadcast({
            "type":          "health_update",
            "animal_id":     animal_id,
            "health_score":  health_score,
            "health_status": health_status,
            "record_id":     record_id,
            "timestamp":     datetime.utcnow().isoformat(),
        })

    async def heartbeat(self) -> None:
        """Barcha clientlarga heartbeat xabari yuboradi."""
        await self.broadcast({
            "type":               "heartbeat",
            "timestamp":          datetime.utcnow().isoformat(),
            "active_connections": len(self._active),
        })

    def get_stats(self) -> dict:
        """
        Ulanish statistikasini qaytaradi.

        Returns:
            Dict: faol, jami ulangan, jami uzilgan, jami yuborilgan
        """
        return {
            "active_connections":  len(self._active),
            "total_connected":     self._total_connected,
            "total_disconnected":  self._total_disconnected,
            "total_messages_sent": self._total_sent,
        }

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    async def _send_to(self, websocket: WebSocket, message: dict) -> None:
        """Bitta ulanishga xabar yuborish — ichki yordamchi."""
        try:
            await websocket.send_json(message)
            self._total_sent += 1
        except Exception as exc:
            logger.error(
                "WebSocket: shaxsiy xabar yuborishda xato",
                extra={"extra_data": {"error": str(exc)}},
            )


# =============================================================================
# GLOBAL INSTANCE MANAGEMENT
# =============================================================================

_ws_manager: Optional[ConnectionManager] = None


def initialize_ws_manager() -> ConnectionManager:
    """
    Global WebSocket managerini yaratadi.

    main.py startup_event da bir marta chaqiriladi.

    Returns:
        Yangi ConnectionManager instance
    """
    global _ws_manager
    _ws_manager = ConnectionManager()
    logger.info("WebSocket manager initialized")
    return _ws_manager


def get_ws_manager() -> ConnectionManager:
    """
    Global WebSocket managerini qaytaradi.

    Returns:
        ConnectionManager instance

    Raises:
        RuntimeError: Manager hali ishga tushirilmagan bo'lsa
    """
    if _ws_manager is None:
        raise RuntimeError(
            "WebSocket manager ishga tushirilmagan. "
            "initialize_ws_manager() ni startup_event da chaqiring."
        )
    return _ws_manager


async def shutdown_ws_manager() -> None:
    """
    Barcha ulanishlarni yopadi va managerni tozalaydi.

    main.py shutdown_event da chaqiriladi.
    """
    global _ws_manager

    if _ws_manager is None:
        return

    logger.info("WebSocket manager yopilmoqda...")

    for ws in list(_ws_manager._active):
        try:
            await ws.close(code=1001, reason="Server shutting down")
        except Exception:
            pass

    _ws_manager._active.clear()
    _ws_manager = None
    logger.info("WebSocket manager yopildi")