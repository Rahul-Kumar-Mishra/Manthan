from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.branches.models import Branch


async def list_branches(
    session: AsyncSession, hospital_id: UUID | None, offset: int, limit: int
) -> list[Branch]:
    statement = select(Branch).order_by(Branch.name).offset(offset).limit(limit)
    if hospital_id is not None:
        statement = statement.where(Branch.hospital_id == hospital_id)
    return list(await session.scalars(statement))


async def get_branch(session: AsyncSession, branch_id: UUID) -> Branch | None:
    return await session.get(Branch, branch_id)


async def add_branch(session: AsyncSession, branch: Branch) -> Branch:
    session.add(branch)
    await session.flush()
    return branch
