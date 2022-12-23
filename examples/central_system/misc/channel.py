import asyncio
import os
from datetime import datetime, timedelta

from pydantic import BaseModel
from redis import asyncio as redis


class Envelope(BaseModel):
    charging_station_id: str
    message: str


class RedisConstruct:
    """Base class for Redis based constructs"""

    def __init__(self):
        endpoint = os.getenv("CENTRAL_SYSTEM_REDIS_ENDPOINT")
        if endpoint is None:
            raise ValueError("CENTRAL_SYSTEM_REDIS_ENDPOINT not set")
        self.redis = redis.from_url(endpoint)


class Pipe(RedisConstruct):
    """Pipe enables two-way communication between two ends.

    In practice (for our use case) the other end is always fixed: Central System.
    The opposite end represents the entity communicating with it: Client API.
    Client API uses unique message id as a **key** value.

    Instead of using redis pubsub the implementation uses redis key/value approach
    which is more efficient in this case.
    """

    async def listen(self, key, timeout: int = 15) -> str:
        await self.redis.set(f"listen:{key}", f"{key}", ex=timeout)
        start = datetime.utcnow()
        while datetime.utcnow() < start + timedelta(seconds=timeout):
            value = await self.redis.getdel(key)
            if value is not None:
                await self.redis.delete(f"listen:{key}")
                return value.decode()
            await asyncio.sleep(0.5)
        raise TimeoutError

    async def send(self, key: str, value: str, expire: int = 30):
        await self.redis.set(key, value, ex=expire)

    async def get(self, key: str) -> str or None:
        value = await self.redis.get(key)
        if value is not None:
            return value.decode()


class PubSub(RedisConstruct):
    """Publish/Subscribe enables many-to-many communication.

    In practice (for our use case) the other end is always fixed: central system.
    The opposite end represents the entity communicating with it:
    client api, with specific message id, which is the **key** value for that end.

    We use redis pubsub here.
    """

    async def publish(self, key: str, message: str):
        async with self.redis.pubsub():
            await self.redis.publish(key, message)

    async def subscribe(self, key: str):
        async with self.redis.pubsub() as pubsub:
            await pubsub.subscribe(key)
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message is not None:
                    return message["data"].decode()
                await asyncio.sleep(1)
