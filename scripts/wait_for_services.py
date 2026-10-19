import asyncio
import os

from redis.asyncio import from_url


async def main() -> None:
    redis = from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    await redis.ping()
    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
