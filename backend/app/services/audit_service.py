"""
Taurus Vision — Security Audit Service

IKKI VAZIFA:
    1. Audit Log     — barcha xavfsizlik voqealarini DB ga yozish
    2. Brute Force   — Redis orqali login urinishlarini kuzatish va bloklash

BRUTE FORCE HIMOYA ALGORITMI:
    ┌─────────────────────────────────────────────────────────────────┐
    │  Har muvaffaqiyatsiz login:                                     │
    │    → Redis kalit: "bf:email:{email}" va "bf:ip:{ip}"           │
    │    → TTL bilan inkrementlash                                    │
    │                                                                 │
    │  Chegara:                                                       │
    │    5  muvaffaqiyatsiz → 15 daqiqa bloklash                     │
    │    15 muvaffaqiyatsiz → 1 soat bloklash                        │
    │                                                                 │
    │  Muvaffaqiyatli login:                                          │
    │    → Barcha counter va lock lar tozalanadi                      │
    └─────────────────────────────────────────────────────────────────┘

REDIS KALIT FORMATI:
    bf:email:{email}     — email bo'yicha muvaffaqiyatsiz urinishlar
    bf:ip:{ip}           — IP bo'yicha muvaffaqiyatsiz urinishlar
    bf:lock:email:{email}— email uchun bloklash (TTL = blok muddati)
    bf:lock:ip:{ip}      — IP uchun bloklash

MUHIM:
    Redis mavjud bo'lmasa — brute force himoya o'chiriladi (log yoziladi).
    Audit log har doim DB ga yoziladi (Redis ga bog'liq emas).
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.models.audit_log import AuditLog, AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)


# =============================================================================
# BRUTE FORCE KONFIGURATSIYA
# =============================================================================

# Muvaffaqiyatsiz loginlar soni → blok muddati (soniyada)
_LOCKOUT_TIERS: list[tuple[int, int]] = [
    (5,  15 * 60),   # 5  urinish → 15 daqiqa
    (15, 60 * 60),   # 15 urinish → 1 soat
]
_ATTEMPT_TTL     = 30 * 60   # Counterlar 30 daqiqada avtomatik o'chadi
_BF_EMAIL_PREFIX = "bf:email:"
_BF_IP_PREFIX    = "bf:ip:"
_LOCK_PREFIX     = "bf:lock:"


# =============================================================================
# AUDIT SERVICE
# =============================================================================

class AuditService:
    """
    Xavfsizlik audit va brute force himoya servisi.

    USAGE (auth_service.py ichida):
        audit = AuditService(db)

        # Muvaffaqiyatli login
        await audit.log_login_success(user_id=1, username="ali", ip="1.2.3.4")

        # Muvaffaqiyatsiz login
        locked = await audit.log_login_failed(identifier="ali@farm.uz", ip="1.2.3.4")
        if locked:
            raise AuthenticationError("Hisob vaqtincha bloklandi")

        # Bloklashni tekshirish
        lock_info = await audit.check_lockout(identifier="ali@farm.uz", ip="1.2.3.4")
        if lock_info["locked"]:
            raise AuthenticationError(lock_info["message"])
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # BRUTE FORCE — PUBLIC INTERFACE
    # =========================================================================

    async def check_lockout(
        self,
        identifier: str,    # email yoki username
        ip: str,
    ) -> dict:
        """
        Login urinishidan OLDIN bloklashni tekshirish.

        Args:
            identifier: Email yoki username
            ip:         So'rov IP manzili

        Returns:
            {
                "locked": bool,
                "reason": "email" | "ip" | None,
                "retry_after": int | None,   # soniyada
                "message": str,
            }
        """
        redis = await get_redis()
        if redis is None:
            return {"locked": False, "reason": None, "retry_after": None, "message": ""}

        # Email uchun tekshirish
        email_key = f"{_LOCK_PREFIX}email:{identifier.lower()}"
        email_ttl = await redis.ttl(email_key)
        if email_ttl > 0:
            return {
                "locked":      True,
                "reason":      "email",
                "retry_after": email_ttl,
                "message":     (
                    f"Juda ko'p muvaffaqiyatsiz urinish. "
                    f"Iltimos {email_ttl // 60} daqiqa {email_ttl % 60} soniyadan keyin qayta urinib ko'ring."
                ),
            }

        # IP uchun tekshirish
        ip_key = f"{_LOCK_PREFIX}ip:{ip}"
        ip_ttl = await redis.ttl(ip_key)
        if ip_ttl > 0:
            return {
                "locked":      True,
                "reason":      "ip",
                "retry_after": ip_ttl,
                "message":     (
                    f"Bu IP manzilidan juda ko'p urinish. "
                    f"Iltimos {ip_ttl // 60} daqiqa {ip_ttl % 60} soniyadan keyin qayta urinib ko'ring."
                ),
            }

        return {"locked": False, "reason": None, "retry_after": None, "message": ""}

    async def record_failed_attempt(
        self,
        identifier: str,
        ip: str,
    ) -> dict:
        """
        Muvaffaqiyatsiz login urinishini qayd qilish va bloklash kerakligini aniqlash.

        Args:
            identifier: Email yoki username
            ip:         So'rov IP manzili

        Returns:
            {
                "email_attempts": int,
                "ip_attempts": int,
                "locked": bool,
                "lock_duration": int | None,   # soniyada
            }
        """
        redis = await get_redis()
        if redis is None:
            logger.warning("[brute_force] Redis yo'q — brute force himoya o'chirilgan")
            return {"email_attempts": 0, "ip_attempts": 0, "locked": False, "lock_duration": None}

        email_key   = f"{_BF_EMAIL_PREFIX}{identifier.lower()}"
        ip_key      = f"{_BF_IP_PREFIX}{ip}"

        # Inkrementlash + TTL o'rnatish (pipe — atomic)
        pipe = redis.pipeline()
        pipe.incr(email_key)
        pipe.expire(email_key, _ATTEMPT_TTL)
        pipe.incr(ip_key)
        pipe.expire(ip_key, _ATTEMPT_TTL)
        results = await pipe.execute()

        email_attempts = int(results[0])
        ip_attempts    = int(results[2])

        # Bloklash kerakmi?
        locked        = False
        lock_duration = None

        # Email bo'yicha bloklash
        for threshold, duration in sorted(_LOCKOUT_TIERS, reverse=True):
            if email_attempts >= threshold:
                lock_key = f"{_LOCK_PREFIX}email:{identifier.lower()}"
                await redis.setex(lock_key, duration, "1")
                locked        = True
                lock_duration = duration
                logger.warning(
                    f"[brute_force] Email bloklandi: {identifier!r} "
                    f"({email_attempts} urinish, {duration // 60} daqiqa)"
                )
                break

        # IP bo'yicha bloklash (yuqori tier)
        for threshold, duration in sorted(_LOCKOUT_TIERS, reverse=True):
            if ip_attempts >= threshold:
                lock_key = f"{_LOCK_PREFIX}ip:{ip}"
                await redis.setex(lock_key, duration, "1")
                locked        = True
                lock_duration = max(lock_duration or 0, duration)
                logger.warning(
                    f"[brute_force] IP bloklandi: {ip} "
                    f"({ip_attempts} urinish, {duration // 60} daqiqa)"
                )
                break

        return {
            "email_attempts": email_attempts,
            "ip_attempts":    ip_attempts,
            "locked":         locked,
            "lock_duration":  lock_duration,
        }

    async def clear_failed_attempts(self, identifier: str, ip: str) -> None:
        """
        Muvaffaqiyatli logindan keyin counterlarni tozalash.

        Args:
            identifier: Email yoki username
            ip:         So'rov IP manzili
        """
        redis = await get_redis()
        if redis is None:
            return

        keys = [
            f"{_BF_EMAIL_PREFIX}{identifier.lower()}",
            f"{_LOCK_PREFIX}email:{identifier.lower()}",
            f"{_BF_IP_PREFIX}{ip}",
            # IP lock tozalanmaydi — boshqa identifierlar uchun saqlanadi
        ]
        await redis.delete(*keys)

    # =========================================================================
    # AUDIT LOG — DB ga yozish
    # =========================================================================

    async def log(
        self,
        event_type: AuditEventType,
        ip:         str,
        severity:   AuditSeverity    = AuditSeverity.INFO,
        user_id:    Optional[int]    = None,
        username:   Optional[str]    = None,
        endpoint:   Optional[str]    = None,
        http_method: Optional[str]   = None,
        details:    Optional[dict]   = None,
        user_agent: Optional[str]    = None,
    ) -> None:
        """
        Audit log yozuvini DB ga saqlash.

        Fire-and-forget: xato bo'lsa log yoziladi, exception ko'tarilmaydi.
        """
        try:
            stmt = insert(AuditLog).values(
                event_type  = event_type.value,
                severity    = severity.value,
                user_id     = user_id,
                username    = username,
                ip_address  = ip,
                user_agent  = user_agent,
                endpoint    = endpoint,
                http_method = http_method,
                details     = details,
                occurred_at = datetime.now(timezone.utc),
            )
            await self.db.execute(stmt)
            await self.db.flush()   # commit auth_service.login() da qiladi
        except Exception as exc:
            # Audit log muvaffaqiyatsizligi asosiy jarayonni to'xtatmasin
            logger.error(f"[audit] Log yozish xatosi: {exc}", exc_info=True)

    # ─── Convenience metodlar ────────────────────────────────────────────────

    async def log_login_success(
        self,
        user_id:    int,
        username:   str,
        ip:         str,
        user_agent: Optional[str] = None,
    ) -> None:
        await self.log(
            event_type  = AuditEventType.LOGIN_SUCCESS,
            severity    = AuditSeverity.INFO,
            user_id     = user_id,
            username    = username,
            ip          = ip,
            user_agent  = user_agent,
            endpoint    = "/api/v1/auth/login",
            http_method = "POST",
            details     = {"result": "success"},
        )

    async def log_login_failed(
        self,
        identifier: str,        # email yoki username (DB da bo'lmasligi mumkin)
        ip:         str,
        reason:     str = "invalid_credentials",
        user_agent: Optional[str] = None,
    ) -> None:
        await self.log(
            event_type  = AuditEventType.LOGIN_FAILED,
            severity    = AuditSeverity.WARNING,
            ip          = ip,
            user_agent  = user_agent,
            endpoint    = "/api/v1/auth/login",
            http_method = "POST",
            details     = {"identifier": identifier, "reason": reason},
        )

    async def log_login_locked(
        self,
        identifier:    str,
        ip:            str,
        lock_duration: int,
        user_agent:    Optional[str] = None,
    ) -> None:
        await self.log(
            event_type  = AuditEventType.LOGIN_LOCKED,
            severity    = AuditSeverity.CRITICAL,
            ip          = ip,
            user_agent  = user_agent,
            endpoint    = "/api/v1/auth/login",
            http_method = "POST",
            details     = {
                "identifier":    identifier,
                "lock_duration": lock_duration,
                "message":       "Brute force himoya ishga tushdi",
            },
        )

    async def log_logout(
        self,
        user_id:  int,
        username: str,
        ip:       str,
    ) -> None:
        await self.log(
            event_type  = AuditEventType.LOGOUT,
            severity    = AuditSeverity.INFO,
            user_id     = user_id,
            username    = username,
            ip          = ip,
            endpoint    = "/api/v1/auth/logout",
            http_method = "POST",
        )

    async def log_password_changed(
        self,
        user_id:  int,
        username: str,
        ip:       str,
        by_admin: bool = False,
    ) -> None:
        await self.log(
            event_type  = AuditEventType.PASSWORD_CHANGED,
            severity    = AuditSeverity.WARNING,
            user_id     = user_id,
            username    = username,
            ip          = ip,
            endpoint    = "/api/v1/auth/change-password",
            http_method = "POST",
            details     = {"changed_by_admin": by_admin},
        )

    async def log_user_created(
        self,
        new_user_id:   int,
        new_username:  str,
        created_by_id: int,
        created_by:    str,
        ip:            str,
        role:          str,
    ) -> None:
        await self.log(
            event_type  = AuditEventType.USER_CREATED,
            severity    = AuditSeverity.WARNING,
            user_id     = created_by_id,
            username    = created_by,
            ip          = ip,
            endpoint    = "/api/v1/auth/users",
            http_method = "POST",
            details     = {
                "new_user_id":  new_user_id,
                "new_username": new_username,
                "role":         role,
            },
        )

    async def log_permission_denied(
        self,
        user_id:  Optional[int],
        username: Optional[str],
        ip:       str,
        endpoint: str,
        required_role: str,
    ) -> None:
        await self.log(
            event_type  = AuditEventType.PERMISSION_DENIED,
            severity    = AuditSeverity.WARNING,
            user_id     = user_id,
            username    = username,
            ip          = ip,
            endpoint    = endpoint,
            details     = {"required_role": required_role},
        )