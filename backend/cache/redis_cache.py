import time
from dataclasses import dataclass
from typing import Optional

import redis.asyncio as aioredis

from backend.config import get_settings

settings = get_settings()


@dataclass
class _MemoryValue:
    value: str
    expires_at: float | None


class RedisCache:
    def __init__(self) -> None:
        self.client: aioredis.Redis | None = None
        self._memory: dict[str, _MemoryValue] = {}
        self._use_memory = False

    async def connect(self) -> None:
        try:
            self.client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await self.client.ping()
        except Exception:
            self.client = None
            self._use_memory = True

    async def disconnect(self) -> None:
        if self.client is not None:
            await self.client.aclose()
        self._memory.clear()

    async def get(self, key: str) -> Optional[str]:
        if self.client is not None and not self._use_memory:
            return await self.client.get(key)
        value = self._memory.get(key)
        if value is None:
            return None
        if value.expires_at is not None and value.expires_at <= time.time():
            self._memory.pop(key, None)
            return None
        return value.value

    async def set(self, key: str, value: str, ttl: int = 3600) -> None:
        if self.client is not None and not self._use_memory:
            await self.client.set(key, value, ex=ttl)
            return
        expires_at = time.time() + ttl if ttl else None
        self._memory[key] = _MemoryValue(value=value, expires_at=expires_at)

    async def delete(self, key: str) -> None:
        if self.client is not None and not self._use_memory:
            await self.client.delete(key)
            return
        self._memory.pop(key, None)

    async def invalidate_pattern(self, pattern: str) -> None:
        if self.client is not None and not self._use_memory:
            keys = await self.client.keys(pattern)
            if keys:
                await self.client.delete(*keys)
            return
        prefix = pattern.rstrip("*")
        for key in [key for key in self._memory if key.startswith(prefix)]:
            self._memory.pop(key, None)
