from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import AppointmentStatus, LeaveStatus, UserRole
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.appointments.models import Appointment
from app.modules.appointments.service import settle_payment_on_cancel
from app.modules.auth.models import User
from app.modules.doctors.models import Doctor
from app.modules.doctors.service import get_doctor, get_doctor_for_user
from app.modules.leaves import repository
from app.modules.leaves.models import DoctorLeave
from app.modules.leaves.schemas import LeaveCreate, LeaveScope


async def request_leave(session: AsyncSession, user: User, data: LeaveCreate) -> DoctorLeave:
    """Doctors file a pending request for themselves; admins record approved leave directly."""
    if user.role == UserRole.ADMIN:
        if data.doctor_id is None:
            raise ConflictError("doctor_id is required when an administrator records leave")
        doctor = await get_doctor(session, data.doctor_id)
        status = LeaveStatus.APPROVED
    else:
        doctor = await get_doctor_for_user(session, user.id)
        status = LeaveStatus.PENDING
    if await repository.has_overlapping_request(session, doctor.id, data.starts_at, data.ends_at):
        raise ConflictError("Leave overlaps an existing pending or approved leave")

    now = datetime.now(UTC)
    leave = DoctorLeave(
        doctor_id=doctor.id,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        reason=data.reason.strip(),
        status=status,
        requested_by=user.id,
        reviewed_by=user.id if status == LeaveStatus.APPROVED else None,
        reviewed_at=now if status == LeaveStatus.APPROVED else None,
    )
    session.add(leave)
    await session.commit()
    await session.refresh(leave)
    return leave


async def list_leaves(
    session: AsyncSession,
    doctor_id: UUID | None,
    status: LeaveStatus | None,
    scope: LeaveScope | None,
    offset: int,
    limit: int,
) -> list[DoctorLeave]:
    return await repository.list_leaves(
        session, doctor_id=doctor_id, status=status, scope=scope, offset=offset, limit=limit
    )


async def list_for_doctor_user(session: AsyncSession, user_id: UUID) -> list[DoctorLeave]:
    doctor = await get_doctor_for_user(session, user_id)
    return await repository.list_leaves(session, doctor_id=doctor.id, limit=500)


async def list_blocked_windows(session: AsyncSession, doctor_id: UUID) -> list[DoctorLeave]:
    """Approved leave that has not ended yet, used to grey out booking calendars."""
    await get_doctor(session, doctor_id)
    leaves = await repository.list_leaves(
        session, doctor_id=doctor_id, status=LeaveStatus.APPROVED, limit=500
    )
    now = datetime.now(UTC)
    return [leave for leave in leaves if _aware(leave.ends_at) > now]


async def get_for_user(session: AsyncSession, leave_id: UUID, user: User) -> DoctorLeave:
    leave = await repository.get_leave(session, leave_id)
    if leave is None:
        raise NotFoundError("Leave not found")
    if user.role == UserRole.DOCTOR:
        doctor = await session.scalar(select(Doctor).where(Doctor.user_id == user.id))
        if doctor is None or leave.doctor_id != doctor.id:
            raise NotFoundError("Leave not found")
    elif user.role != UserRole.ADMIN:
        raise NotFoundError("Leave not found")
    return leave


async def review_leave(
    session: AsyncSession,
    leave_id: UUID,
    reviewer: User,
    approve: bool,
    note: str | None,
) -> DoctorLeave:
    leave = await repository.get_leave(session, leave_id)
    if leave is None:
        raise NotFoundError("Leave not found")
    if leave.status != LeaveStatus.PENDING:
        raise ConflictError("Only pending leave requests can be reviewed")
    if approve and await repository.has_overlapping_request(
        session, leave.doctor_id, leave.starts_at, leave.ends_at, exclude_id=leave.id
    ):
        raise ConflictError("Leave overlaps another approved or pending leave")
    leave.status = LeaveStatus.APPROVED if approve else LeaveStatus.REJECTED
    leave.reviewed_by = reviewer.id
    leave.reviewed_at = datetime.now(UTC)
    leave.review_note = note.strip() if note and note.strip() else None
    await session.commit()
    await session.refresh(leave)
    return leave


async def cancel_leave(session: AsyncSession, leave_id: UUID, user: User) -> DoctorLeave:
    leave = await get_for_user(session, leave_id, user)
    if leave.status not in repository.ACTIVE_STATUSES:
        raise ConflictError("Only pending or approved leave can be cancelled")
    if _aware(leave.ends_at) <= datetime.now(UTC):
        raise ConflictError("Leave that has already ended cannot be cancelled")
    leave.status = LeaveStatus.CANCELLED
    await session.commit()
    await session.refresh(leave)
    return leave


async def affected_appointments(session: AsyncSession, leave: DoctorLeave) -> list[Appointment]:
    result = await session.scalars(
        select(Appointment)
        .where(
            Appointment.doctor_id == leave.doctor_id,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.starts_at < leave.ends_at,
            Appointment.ends_at > leave.starts_at,
        )
        .order_by(Appointment.starts_at)
    )
    return list(result)


async def cancel_affected_appointments(
    session: AsyncSession, leave_id: UUID, reason: str
) -> list[Appointment]:
    leave = await repository.get_leave(session, leave_id)
    if leave is None:
        raise NotFoundError("Leave not found")
    if leave.status != LeaveStatus.APPROVED:
        raise ConflictError("Appointments can only be cleared for approved leave")
    appointments = await affected_appointments(session, leave)
    now = datetime.now(UTC)
    for appointment in appointments:
        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancelled_at = now
        appointment.cancelled_by_role = UserRole.ADMIN
        appointment.cancellation_reason = reason.strip()
        await settle_payment_on_cancel(session, appointment)
    await session.commit()
    for appointment in appointments:
        await session.refresh(appointment)
    return appointments


def _aware(value: datetime) -> datetime:
    # SQLite (used in tests) returns naive datetimes for timezone-aware columns.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
