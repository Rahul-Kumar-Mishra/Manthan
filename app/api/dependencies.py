from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
