from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.branches import repository
from app.modules.branches.models import Branch
from app.modules.branches.schemas import BranchCreate, BranchUpdate
from app.modules.hospitals import repository as hospital_repository


async def list_branches(
    session: AsyncSession, hospital_id: UUID | None, offset: int, limit: int
) -> list[Branch]:
    return await repository.list_branches(session, hospital_id, offset, limit)


async def get_branch(session: AsyncSession, branch_id: UUID) -> Branch:
    branch = await repository.get_branch(session, branch_id)
    if branch is None:
        raise NotFoundError("Branch not found")
    return branch


async def create_branch(session: AsyncSession, hospital_id: UUID, data: BranchCreate) -> Branch:
    if await hospital_repository.get_hospital(session, hospital_id) is None:
        raise NotFoundError("Hospital not found")
    branch = Branch(hospital_id=hospital_id, **data.model_dump())
    try:
        await repository.add_branch(session, branch)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("A branch with that name already exists for this hospital") from exc
    await session.refresh(branch)
    return branch


async def update_branch(session: AsyncSession, branch_id: UUID, data: BranchUpdate) -> Branch:
    branch = await get_branch(session, branch_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(branch, field, value)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("A branch with that name already exists for this hospital") from exc
    await session.refresh(branch)
    return branch


async def delete_branch(session: AsyncSession, branch_id: UUID) -> None:
    branch = await get_branch(session, branch_id)
    await session.delete(branch)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("Cannot delete a branch with dependent doctors") from exc
