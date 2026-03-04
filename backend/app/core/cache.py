"""
Taurus Vision — Redis Cache Utility

Analytics endpointlari uchun Redis asosidagi kesh.

STRATEGIYA:
  - Dashboard overview:    60 soniya kesh (har daqiqada yangilanishi etarli)
  - Weight trend:          5 daqiqa kesh (real-time emas, tarixiy ma'lumot)
  - Hourly detection:      5 daqiqa kesh
  - Health metrics:        2 daqiqa kesh

FOYDALANISH:
    from app.core.cache import cache_get, cache_set, cache_invalidate

    # O'qish
    cached = await cache_get("analytics:overview")
    if cached:
        return cached

    # Hisoblash va saqlash
    result = await expensive_computation()
    await cache_set("analytics:overview", result, ttl=60)
    return result

KESH KALITLARI (namespace:subkey formatida):
    analytics:overview
    analytics:weight_trend:{days}
    analytics:hourly:{date_from}:{date_to}
    analytics:health
"""

import json
import logging
from typing import Any, Optional
from datetime import datetime

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

# ─── Singleton Redis klient ───────────────────────────────────────────────────
# Connection pool bilan — har so'rovda yangi ulanish ochilmaydi

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> Optional[aioredis.Redis]:
    """
    Redis klientini qaytaradi (singleton pattern).
    Redis mavjud bo'lmasa — None qaytaradi (kesh o'chirilgan rejim).
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    try:
        client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,        # Connection pool
            socket_connect_timeout=2,  # 2 soniyadan ko'p kutmaymiz
            socket_timeout=2,
        )
        # Ulanish tekshirish
        await client.ping()
        _redis_client = client
        logger.info("Redis cache connected successfully")
        return _redis_client

    except Exception as e:
        logger.warning(f"Redis unavailable, caching disabled: {e}")
        return None


async def close_redis() -> None:
    """Dastur o'chganda Redis ulanishini yopish."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed")


# ─── Cache operatsiyalari ─────────────────────────────────────────────────────

async def cache_get(key: str) -> Optional[Any]:
    """
    Redis dan kesh ma'lumotini o'qish.

    Args:
        key: Kesh kaliti

    Returns:
        Deserialized ma'lumot yoki None (kesh yo'q / muddati o'tgan)
    """
    redis = await get_redis()
    if redis is None:
        return None

    try:
        raw = await redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Cache GET error for key={key}: {e}")
        return None


async def cache_set(key: str, value: Any, ttl: int = 60) -> bool:
    """
    Redis ga kesh ma'lumotini yozish.

    Args:
        key:   Kesh kaliti
        value: Saqlanadigan ma'lumot (JSON serializable bo'lishi kerak)
        ttl:   Soniyalarda yashash vaqti (default: 60s)

    Returns:
        True — muvaffaqiyatli saqlandi, False — xato
    """
    redis = await get_redis()
    if redis is None:
        return False

    try:
        serialized = json.dumps(value, default=_json_serializer)
        await redis.setex(key, ttl, serialized)
        return True
    except Exception as e:
        logger.warning(f"Cache SET error for key={key}: {e}")
        return False


async def cache_invalidate(pattern: str) -> int:
    """
    Pattern bo'yicha kesh kalitlarini o'chirish.

    Args:
        pattern: Redis glob pattern, masalan "analytics:*"

    Returns:
        O'chirilgan kalitlar soni
    """
    redis = await get_redis()
    if redis is None:
        return 0

    try:
        keys = await redis.keys(pattern)
        if not keys:
            return 0
        deleted = await redis.delete(*keys)
        logger.info(f"Cache invalidated {deleted} keys matching '{pattern}'")
        return deleted
    except Exception as e:
        logger.warning(f"Cache INVALIDATE error for pattern={pattern}: {e}")
        return 0


# ─── JSON serializer ──────────────────────────────────────────────────────────

def _json_serializer(obj: Any) -> str:
    """date/datetime obyektlarini JSON ga aylantirishga yordam beradi."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# ─── Cache key helpers ────────────────────────────────────────────────────────

class CacheKeys:
    """
    Kesh kalit konstantalari — typo xatolarini oldini oladi.

    SPRINT 21-24 QO'SHIMCHALAR:
        HERD_STATISTICS      — poda statistikasi (3 daqiqa)
        adi_trend()          — ADI trend (5 daqiqa)
        growth_trend()       — O'sish trendi (5 daqiqa)
        behavior_trend()     — Xatti-harakat trendi (5 daqiqa)
        insights()           — Avtomatik tushunchalar (10 daqiqa)
    """

    OVERVIEW          = "analytics:overview"
    HEALTH_METRICS    = "analytics:health"
    HERD_STATISTICS   = "analytics:herd_statistics"   # Sprint 23

    @staticmethod
    def weight_trend(days: int) -> str:
        return f"analytics:weight_trend:{days}"

    @staticmethod
    def hourly_detection(date_from: str, date_to: str) -> str:
        return f"analytics:hourly:{date_from}:{date_to}"

    @staticmethod
    def animals_overview() -> str:
        return "analytics:animals_overview"

    # ------------------------------------------------------------------
    # Sprint 21-24 yangi kalit metodlari
    # ------------------------------------------------------------------

    @staticmethod
    def adi_trend(animal_id: Optional[int], days: int) -> str:
        """ADI trend kesh kaliti — animal_id=None bo'lsa herd-wide."""
        aid = animal_id if animal_id is not None else "herd"
        return f"analytics:adi_trend:{aid}:{days}"

    @staticmethod
    def growth_trend(animal_id: Optional[int], days: int) -> str:
        """O'sish trendi kesh kaliti."""
        aid = animal_id if animal_id is not None else "herd"
        return f"analytics:growth_trend:{aid}:{days}"

    @staticmethod
    def behavior_trend(animal_id: Optional[int], days: int) -> str:
        """Xatti-harakat trendi kesh kaliti."""
        aid = animal_id if animal_id is not None else "herd"
        return f"analytics:behavior_trend:{aid}:{days}"

    @staticmethod
    def insights(days: int) -> str:
        """Avtomatik tushunchalar kesh kaliti."""
        return f"analytics:insights:{days}"