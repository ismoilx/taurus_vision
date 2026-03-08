"""
Redis stub module — test muhiti uchun.
Haqiqiy redis o'rnatilmaganda testlar ishlashi uchun mock.
"""
from redis.asyncio import Redis, from_url


class StubRedis:
    """Redis operatsiyalarini mock qiladigan stub klass."""

    async def ping(self):
        raise ConnectionError("Redis stub: real Redis yo'q")

    async def get(self, key):
        return None

    async def set(self, key, value, ex=None):
        return True

    async def setex(self, key, ttl, value):
        return True

    async def delete(self, *keys):
        return 0

    async def keys(self, pattern):
        return []

    async def aclose(self):
        pass


def from_url(url, **kwargs):
    return StubRedis()