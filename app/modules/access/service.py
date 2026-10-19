from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import Module, UserRole
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.access.models import ModuleGrant
from app.modules.auth.models import User

MODULE_DESCRIPTIONS: dict[Module, str] = {
    Module.DOCTORS: "Add, edit and remove doctors and their profiles; manage doctor leave.",
    Module.PATIENTS: "View and manage patient records.",
    Module.APPOINTMENTS: "See every appointment, cancel on a patient's behalf, mark completed.",
    Module.PHARMACY: "Medicine catalogue, stock levels, restocking and medicine orders.",
    Module.LAB: "Lab test catalogue and lab bookings.",
    Module.STAFF: "Staff directory and staff sign-in accounts.",
    Module.PAYMENTS: "View payments and issue refunds.",
    Module.NETWORK: "Hospitals and branches.",
}


async def modules_for(session: AsyncSession, user: User) -> set[Module]:
    if user.is_md:
        return set(Module)
    if user.role != UserRole.ADMIN:
        return set()
    rows = await session.scalars(select(ModuleGrant.module).where(ModuleGrant.user_id == user.id))
    return set(rows)


async def has_module(session: AsyncSession, user: User, module: Module) -> bool:
    return module in await modules_for(session, user)


async def ensure_module(session: AsyncSession, user: User, module: Module) -> None:
    if not await has_module(session, user, module):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This action needs access to the {module.value} module",
        )


async def list_staff_accounts(session: AsyncSession) -> list[tuple[User, list[ModuleGrant]]]:
    users = list(
        await session.scalars(
            select(User).where(User.role == UserRole.ADMIN).order_by(User.is_md.desc(), User.email)
        )
    )
    grants = list(await session.scalars(select(ModuleGrant).order_by(ModuleGrant.created_at)))
    by_user: dict[UUID, list[ModuleGrant]] = {}
    for grant in grants:
        by_user.setdefault(grant.user_id, []).append(grant)
    return [(user, by_user.get(user.id, [])) for user in users]


async def grant(session: AsyncSession, grantor: User, user_id: UUID, module: Module) -> ModuleGrant:
    await ensure_module(session, grantor, module)
    target = await session.get(User, user_id)
    if target is None:
        raise NotFoundError("User not found")
    if target.role != UserRole.ADMIN:
        raise ConflictError("Module access can only be given to staff (admin) accounts")
    if target.is_md:
        raise ConflictError("The managing director already has every module")
    if target.id == grantor.id:
        raise ConflictError("You cannot grant access to yourself")
    record = ModuleGrant(user_id=target.id, module=module, granted_by=grantor.id)
    session.add(record)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("That user already has this module") from exc
    await session.refresh(record)
    return record


async def _descends_from(session: AsyncSession, grant: ModuleGrant, ancestor_id: UUID) -> bool:
    """True when `grant` was handed down (directly or via others) from `ancestor_id`."""
    seen: set[UUID] = set()
    current: ModuleGrant | None = grant
    while current is not None and current.granted_by is not None:
        if current.granted_by == ancestor_id:
            return True
        if current.granted_by in seen:
            return False
        seen.add(current.granted_by)
        current = await session.scalar(
            select(ModuleGrant).where(
                ModuleGrant.user_id == current.granted_by, ModuleGrant.module == grant.module
            )
        )
    return False


async def _revoke_subtree(session: AsyncSession, user_id: UUID, module: Module) -> int:
    """Remove `module` from `user_id` and from everyone they passed it to, recursively."""
    removed = 0
    frontier = [user_id]
    while frontier:
        holder = frontier.pop()
        held = list(
            await session.scalars(
                select(ModuleGrant).where(
                    ModuleGrant.user_id == holder, ModuleGrant.module == module
                )
            )
        )
        for row in held:
            await session.delete(row)
        removed += len(held)
        children = await session.scalars(
            select(ModuleGrant.user_id).where(
                ModuleGrant.granted_by == holder, ModuleGrant.module == module
            )
        )
        frontier.extend(children)
    return removed


async def revoke(session: AsyncSession, revoker: User, grant_id: UUID) -> int:
    record = await session.get(ModuleGrant, grant_id)
    if record is None:
        raise NotFoundError("Grant not found")
    await ensure_module(session, revoker, record.module)
    # The MD may revoke anything; everyone else only within the branch they delegated.
    if not revoker.is_md and not await _descends_from(session, record, revoker.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only revoke access that you (or people you granted) handed out",
        )
    removed = await _revoke_subtree(session, record.user_id, record.module)
    await session.commit()
    return removed
