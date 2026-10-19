from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import LeaveStatus
from app.modules.leaves.models import DoctorLeave
from app.modules.leaves.schemas import LeaveScope

ACTIVE_STATUSES = (LeaveStatus.PENDING, LeaveStatus.APPROVED)


async def has_approved_leave(
    session: AsyncSession, doctor_id: UUID, starts_at: datetime, ends_at: datetime
) -> bool:
    result = await session.scalar(
        select(DoctorLeave.id)
        .where(
            DoctorLeave.doctor_id == doctor_id,
            DoctorLeave.status == LeaveStatus.APPROVED,
            DoctorLeave.starts_at < ends_at,
            DoctorLeave.ends_at > starts_at,
        )
        .limit(1)
    )
    return result is not None


async def has_overlapping_request(
    session: AsyncSession,
    doctor_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_id: UUID | None = None,
) -> bool:
    statement = select(DoctorLeave.id).where(
        DoctorLeave.doctor_id == doctor_id,
        DoctorLeave.status.in_(ACTIVE_STATUSES),
        DoctorLeave.starts_at < ends_at,
        DoctorLeave.ends_at > starts_at,
    )
    if exclude_id is not None:
        statement = statement.where(DoctorLeave.id != exclude_id)
    return await session.scalar(statement.limit(1)) is not None


async def list_leaves(
    session: AsyncSession,
    *,
    doctor_id: UUID | None = None,
    status: LeaveStatus | None = None,
    scope: LeaveScope | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[DoctorLeave]:
    now = datetime.now(UTC)
    statement = select(DoctorLeave)
    if doctor_id is not None:
        statement = statement.where(DoctorLeave.doctor_id == doctor_id)
    if status is not None:
        statement = statement.where(DoctorLeave.status == status)
    if scope == LeaveScope.CURRENT:
        statement = statement.where(DoctorLeave.starts_at <= now, DoctorLeave.ends_at > now)
    elif scope == LeaveScope.UPCOMING:
        statement = statement.where(DoctorLeave.starts_at > now)
    elif scope == LeaveScope.PAST:
        statement = statement.where(DoctorLeave.ends_at <= now)
    # Past leave reads most-recent first; everything else chronologically.
    order = DoctorLeave.starts_at.desc() if scope == LeaveScope.PAST else DoctorLeave.starts_at
    return list(await session.scalars(statement.order_by(order).offset(offset).limit(limit)))


async def get_leave(session: AsyncSession, leave_id: UUID) -> DoctorLeave | None:
    return await session.get(DoctorLeave, leave_id)
