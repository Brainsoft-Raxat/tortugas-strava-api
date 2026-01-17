"""Cache management - fake implementation for testing."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from src.config import get_settings
from src.core.lifespan import manager

settings = get_settings()


class FakeRedis:
    """Fake Redis client for testing lifespan manager."""

    def __init__(self, url: str):
        self.url = url
        self.connected = False
        self._data = {}

    async def connect(self):
        """Simulate connection delay."""
        await asyncio.sleep(0.1)
        self.connected = True

    async def get(self, key: str) -> str | None:
        """Get value from cache."""
        return self._data.get(key)

    async def set(self, key: str, value: str):
        """Set value in cache."""
        self._data[key] = value

    async def close(self):
        """Simulate disconnection."""
        await asyncio.sleep(0.1)
        self.connected = False
        self._data.clear()


@manager.add
@asynccontextmanager
async def cache_lifespan() -> AsyncIterator[dict]:
    """
    Manage cache connection lifecycle.
    Creates Redis connection on startup, closes on shutdown.
    """
    print("🔵 Starting cache connection...")

    redis = FakeRedis(url=settings.REDIS_URL)
    await redis.connect()

    print("✅ Cache connected")

    yield {"redis": redis}

    print("🔴 Closing cache connection...")
    await redis.close()
    print("✅ Cache disconnected")
