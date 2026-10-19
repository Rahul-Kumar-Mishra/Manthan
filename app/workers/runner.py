import asyncio
import logging

logger = logging.getLogger(__name__)


async def run() -> None:
    logger.info("Worker runner started")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(run())
