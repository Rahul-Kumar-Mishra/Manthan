from datetime import date
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import StaffStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.access.models import ModuleGrant
from app.modules.auth.models import User
from app.modules.staff.models import StaffMember
from app.modules.staff.schemas import StaffCreate, StaffOffboard, StaffUpdate

DUPLICATE = "A staff member with that email or sign-in account already exists"


async def list_staff(
    session: AsyncSession,
    status: StaffStatus | None,
    department: str | None,
    search: str | None,
) -> list[StaffMember]:
    statement = select(StaffMember).order_by(StaffMember.full_name)
    if status is not None:
        statement = statement.where(StaffMember.status == status)
    if department:
        statement = statement.where(StaffMember.department == department)
    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            or_(StaffMember.full_name.ilike(pattern), StaffMember.designation.ilike(pattern))
        )
    return list(await session.scalars(statement))


async def get_staff(session: AsyncSession, staff_id: UUID) -> StaffMember:
    member = await session.get(StaffMember, staff_id)
    if member is None:
        raise NotFoundError("Staff member not found")
    return member


async def _check_user(session: AsyncSession, user_id: UUID | None) -> None:
    if user_id is not None and await session.get(User, user_id) is None:
        raise NotFoundError("Sign-in account not found")


async def create_staff(session: AsyncSession, data: StaffCreate) -> StaffMember:
    await _check_user(session, data.user_id)
    member = StaffMember(**data.model_dump())
    if member.email:
        member.email = member.email.lower()
    session.add(member)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(DUPLICATE) from exc
    await session.refresh(member)
    return member


async def update_staff(session: AsyncSession, staff_id: UUID, data: StaffUpdate) -> StaffMember:
    member = await get_staff(session, staff_id)
    changes = data.model_dump(exclude_unset=True)
    if "user_id" in changes:
        await _check_user(session, changes["user_id"])
    for field, value in changes.items():
        setattr(member, field, value)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(DUPLICATE) from exc
    await session.refresh(member)
    return member


async def offboard(session: AsyncSession, staff_id: UUID, data: StaffOffboard) -> StaffMember:
    """Mark someone as having left. Their sign-in is disabled and module access removed."""
    member = await get_staff(session, staff_id)
    if member.status == StaffStatus.LEFT:
        raise ConflictError("This staff member has already left")
    member.status = StaffStatus.LEFT
    member.left_on = data.left_on or date.today()
    if data.note:
        member.notes = f"{member.notes}\n{data.note}".strip() if member.notes else data.note
    if member.user_id is not None:
        account = await session.get(User, member.user_id)
        if account is not None and account.is_md:
            raise ConflictError("The managing director's account cannot be offboarded here")
        if account is not None:
            account.is_active = False
        await session.execute(delete(ModuleGrant).where(ModuleGrant.user_id == member.user_id))
    await session.commit()
    await session.refresh(member)
    return member


async def delete_staff(session: AsyncSession, staff_id: UUID) -> None:
    await session.delete(await get_staff(session, staff_id))
    await session.commit()
