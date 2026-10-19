from redis.asyncio import Redis


class CacheService:
    def __init__(self, client: Redis) -> None:
        self.client = client

    async def get(self, key: str) -> str | None:
        return await self.client.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        await self.client.set(key, value, ex=ttl_seconds)
