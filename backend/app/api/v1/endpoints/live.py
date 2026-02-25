"""
Taurus Vision — Live Feed WebSocket Endpoint

Real-time detection va weight yangilanishlari uchun WebSocket ulanish nuqtasi.

AUTENTIFIKATSIYA:
    HTTP headerda Bearer token yuborish WebSocket protokolida qiyin bo'lgani
    uchun token query parameter orqali uzatiladi:

        ws://host:8000/api/v1/live/ws?token=<access_token>

    Backend:
        1. ?token= parametridan JWT access tokenni o'qiydi
        2. decode_token() orqali tekshiradi (muddati, imzosi, turi)
        3. Foydalanuvchini DB dan oladi va aktiv ekanligini tekshiradi
        4. Muammo bo'lsa — ulanishni 4001 kodi bilan yopadi

XABAR FORMATI (klientga keladi):
    {
        "type": "detection",
        "timestamp": "2026-02-25T10:30:00",
        "camera_id": "CAM-SIM-001",
        "animal_id": 1,
        "animal_tag_id": "JNV-001",
        "estimated_weight_kg": 245.5,
        "confidence_score": 0.92,
        ...
    }

    {
        "type": "heartbeat",
        "timestamp": "2026-02-25T10:30:30",
        "active_connections": 3
    }

KLIENT MISOLI (JavaScript):
    const token = localStorage.getItem('tv_access_token');
    const ws = new WebSocket(`ws://localhost:8000/api/v1/live/ws?token=${token}`);

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'detection') { ... }
    };

    ws.onclose = (event) => {
        if (event.code === 4001) {
            // Token noto'g'ri — login sahifasiga yo'naltirish
            window.location.href = '/login';
        }
    };
"""

import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.websocket import get_ws_manager
from app.api.v1.deps import get_current_active_user, CurrentUser
from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import AuthenticationError
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/live",
    tags=["Live Feed"],
)

# WebSocket close code lar — RFC 6455 extension (4000-4999 ilovaga tegishli)
WS_CLOSE_UNAUTHORIZED = 4001   # Token yo'q, noto'g'ri yoki muddati tugagan
WS_CLOSE_USER_INACTIVE = 4003  # Foydalanuvchi bloklangan


# =============================================================================
# WEBSOCKET AUTH HELPER
# =============================================================================

async def _authenticate_ws(
    token: Optional[str],
    db: AsyncSession,
) -> Optional[object]:
    """
    WebSocket ulanishi uchun JWT tokenni tekshiradi.

    HTTP Dependency tizimidan farqli ravishda, WebSocket da exception raise
    qilish mumkin emas — shuning uchun None qaytaramiz va caller close() chaqiradi.

    Args:
        token: ?token= query parametridan olingan JWT access token
        db:    Async DB session

    Returns:
        User instance — autentifikatsiya muvaffaqiyatli bo'lsa
        None          — token yo'q, noto'g'ri yoki foydalanuvchi topilmasa
    """
    if not token:
        logger.warning("WebSocket auth: token yo'q")
        return None

    # Token decode va tekshirish
    try:
        payload = decode_token(token)
    except AuthenticationError as exc:
        logger.warning(
            "WebSocket auth: token decode xatosi",
            extra={"extra_data": {"error": str(exc)}},
        )
        return None

    # Token turi: faqat access token qabul qilinadi
    if payload.get("type") != "access":
        logger.warning("WebSocket auth: access token emas")
        return None

    # User ID ni olish
    user_id_str = payload.get("sub")
    if not user_id_str:
        logger.warning("WebSocket auth: token payload da sub yo'q")
        return None

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        logger.warning("WebSocket auth: sub noto'g'ri format")
        return None

    # DB dan foydalanuvchini olish
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)

    if not user:
        logger.warning(
            "WebSocket auth: foydalanuvchi topilmadi",
            extra={"extra_data": {"user_id": user_id}},
        )
        return None

    return user


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================

@router.websocket("/ws")
async def websocket_live_feed(
    websocket: WebSocket,
    token: Optional[str] = Query(
        default=None,
        description="JWT access token (?token=<access_token>)",
    ),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Real-time detection feed WebSocket endpoint.

    Autentifikatsiya:
        ?token=<jwt_access_token> query parametri talab qilinadi.
        Token noto'g'ri bo'lsa — ulanish 4001 kodi bilan yopiladi.

    Args:
        websocket: FastAPI WebSocket ob'ekti
        token:     JWT access token (query param)
        db:        Async DB session

    WebSocket Close Codes:
        4001 — Token noto'g'ri, muddati tugagan yoki yo'q
        4003 — Foydalanuvchi bloklangan
        1000 — Oddiy uzilish (client o'zi yopdi)
        1001 — Server o'chishi (shutdown_ws_manager)
    """
    # --- 1. AUTENTIFIKATSIYA ---
    # WebSocket Upgrade so'rovi kelganda DB session orqali tekshiramiz.
    # Muammo bo'lsa — accept() chaqirmasdan websocket.close() qilamiz.

    user = await _authenticate_ws(token=token, db=db)

    if user is None:
        # RFC 6455: 4xxx kodlar ilovaga tegishli
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Autentifikatsiya talab qilinadi")
        logger.warning(
            "WebSocket: ruxsatsiz ulanish rad etildi",
            extra={"extra_data": {"token_present": token is not None}},
        )
        return

    if not user.is_active:
        await websocket.close(code=WS_CLOSE_USER_INACTIVE, reason="Hisob bloklangan")
        logger.warning(
            "WebSocket: bloklangan foydalanuvchi rad etildi",
            extra={"extra_data": {"user_id": user.id}},
        )
        return

    # --- 2. ULANISHNI QO'LLASH ---
    manager = get_ws_manager()
    await manager.connect(websocket)  # accept() + welcome xabari

    logger.info(
        "WebSocket: foydalanuvchi ulandi",
        extra={"extra_data": {
            "user_id":  user.id,
            "username": user.username,
            "role":     user.role.value,
        }},
    )

    # --- 3. XABARLARNI KUTISH ---
    # Client faqat qabul qiladi (read-only feed).
    # receive_text() ulanishni tirik ushlab turadi va
    # client yopganda WebSocketDisconnect raise qiladi.

    try:
        while True:
            raw = await websocket.receive_text()
            # Kelajakda klient filtrlash so'rovlari yuborishi mumkin
            # Hozircha faqat log qilamiz
            logger.debug(
                "WebSocket: klientdan xabar",
                extra={"extra_data": {
                    "user_id": user.id,
                    "data":    raw[:200],  # Truncate — xavfsizlik
                }},
            )

    except WebSocketDisconnect:
        logger.info(
            "WebSocket: foydalanuvchi uzildi",
            extra={"extra_data": {
                "user_id":  user.id,
                "username": user.username,
            }},
        )

    except Exception as exc:
        logger.error(
            "WebSocket: kutilmagan xato",
            extra={"extra_data": {
                "user_id": user.id,
                "error":   str(exc),
            }},
            exc_info=True,
        )

    finally:
        # Har qanday holda ulanishni ro'yxatdan chiqarish
        await manager.disconnect(websocket)


# =============================================================================
# STATS ENDPOINT — HIMOYALANGAN
# =============================================================================

@router.get(
    "/stats",
    summary="WebSocket ulanish statistikasi",
    description=(
        "Hozir ulangan clientlar soni va jami statistika. "
        "Monitoring va dashboard health check uchun. "
        "Autentifikatsiya talab qilinadi."
    ),
)
async def websocket_stats(
    current_user: CurrentUser,
) -> dict:
    """
    WebSocket ulanish statistikasini qaytaradi.

    Args:
        current_user: Autentifikatsiya qilingan foydalanuvchi (ixtiyoriy rol)

    Returns:
        Dict: active_connections, total_connected, total_disconnected,
              total_messages_sent
    """
    manager = get_ws_manager()
    return manager.get_stats()