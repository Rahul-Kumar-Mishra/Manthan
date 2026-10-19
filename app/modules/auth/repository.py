from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def add_user(session: AsyncSession, user: User) -> User:
    session.add(user)
    await session.flush()
    return user
