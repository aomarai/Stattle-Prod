import asyncio
import os
from typing import Optional, Union

import redis.asyncio as redis


class RedisClient:
    _instance: Optional[redis.Redis] = None
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def get_client(cls) -> redis.Redis:
        """
        Return the currently running Redis instance.
        If no instance is running, create a new instance.
        :return: redis.Redis instance
        """
        async with cls._lock:
            if cls._instance is None:
                cls._instance = await redis.from_url(
                    f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}",
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                )
        return cls._instance

    @classmethod
    async def get(cls, key: str) -> Optional[str]:
        client = await cls.get_client()
        return await client.get(key)

    @classmethod
    async def set(cls, key: str, value: Union[str, int, float, bytes], ex: Optional[int] = None) -> None:
        client = await cls.get_client()
        return await client.set(key, value, ex)

    @classmethod
    async def close(cls) -> None:
        """
        Closes the redis connection.
        """
        if cls._instance is not None:
            await cls._instance.close()
