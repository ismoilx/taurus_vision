"""
redis.asyncio stub — test muhiti uchun.
"""
from typing import Optional, Any


class Redis:
    """Async Redis stub."""

    async def ping(self):
        raise ConnectionError("Redis stub: real Redis yo'q")

    async def get(self, key: str) -> Optional[str]:
        return None

    async def set(self, key: str, value: Any, ex: int = None) -> bool:
        return True

    async def setex(self, key: str, ttl: int, value: Any) -> bool:
        return True

    async def delete(self, *keys: str) -> int:
        return 0

    async def keys(self, pattern: str) -> list:
        return []

    async def aclose(self) -> None:
        pass


def from_url(url: str, **kwargs) -> Redis:
    """Redis klientini yaratish (stub)."""
    return Redis()