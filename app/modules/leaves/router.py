from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.common.enums import LeaveStatus, Module, UserRole
from app.modules.access.dependencies import require_module
from app.modules.appointments.schemas import AppointmentRead
from app.modules.auth.dependencies import require_roles
from app.modules.auth.models import User
from app.modules.leaves import service
from app.modules.leaves.schemas import (
    LeaveAppointmentsCancel,
    LeaveCreate,
    LeaveRead,
    LeaveReview,
    LeaveScope,
)

doctor = require_roles(UserRole.DOCTOR)
admin = require_roles(UserRole.ADMIN)

# Doctors request and track their own leave under /doctor/leaves.
doctor_router = APIRouter()
# Review and records under /admin/leaves; needs the doctors module.
admin_router = APIRouter(dependencies=[Depends(require_module(Module.DOCTORS))])


# ---------- doctor ----------


@doctor_router.post("", response_model=LeaveRead, status_code=status.HTTP_201_CREATED)
async def request_leave(
    data: LeaveCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(doctor),
) -> LeaveRead:
    return await service.request_leave(session, user, data)


@doctor_router.get("", response_model=list[LeaveRead])
async def my_leaves(
    session: AsyncSession = Depends(get_db_session), user: User = Depends(doctor)
) -> list[LeaveRead]:
    return await service.list_for_doctor_user(session, user.id)


@doctor_router.get("/{leave_id}", response_model=LeaveRead)
async def get_my_leave(
    leave_id: UUID, session: AsyncSession = Depends(get_db_session), user: User = Depends(doctor)
) -> LeaveRead:
    return await service.get_for_user(session, leave_id, user)


@doctor_router.post("/{leave_id}/cancel", response_model=LeaveRead)
async def withdraw_my_leave(
    leave_id: UUID, session: AsyncSession = Depends(get_db_session), user: User = Depends(doctor)
) -> LeaveRead:
    return await service.cancel_leave(session, leave_id, user)


@doctor_router.get("/{leave_id}/appointments", response_model=list[AppointmentRead])
async def my_leave_appointments(
    leave_id: UUID, session: AsyncSession = Depends(get_db_session), user: User = Depends(doctor)
) -> list[AppointmentRead]:
    return await service.affected_appointments(
        session, await service.get_for_user(session, leave_id, user)
    )


# ---------- admin ----------


@admin_router.post("", response_model=LeaveRead, status_code=status.HTTP_201_CREATED)
async def record_leave(
    data: LeaveCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(admin),
) -> LeaveRead:
    if data.doctor_id is None:
        raise HTTPException(
            status_code=422, detail="doctor_id is required when an administrator records leave"
        )
    return await service.request_leave(session, user, data)


@admin_router.get("", response_model=list[LeaveRead])
async def list_leaves(
    doctor_id: UUID | None = None,
    leave_status: LeaveStatus | None = Query(default=None, alias="status"),
    scope: LeaveScope | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> list[LeaveRead]:
    return await service.list_leaves(session, doctor_id, leave_status, scope, offset, limit)


@admin_router.get("/{leave_id}", response_model=LeaveRead)
async def get_leave(
    leave_id: UUID, session: AsyncSession = Depends(get_db_session), user: User = Depends(admin)
) -> LeaveRead:
    return await service.get_for_user(session, leave_id, user)


@admin_router.post("/{leave_id}/cancel", response_model=LeaveRead)
async def revoke_leave(
    leave_id: UUID, session: AsyncSession = Depends(get_db_session), user: User = Depends(admin)
) -> LeaveRead:
    return await service.cancel_leave(session, leave_id, user)


@admin_router.get("/{leave_id}/appointments", response_model=list[AppointmentRead])
async def leave_appointments(
    leave_id: UUID, session: AsyncSession = Depends(get_db_session), user: User = Depends(admin)
) -> list[AppointmentRead]:
    return await service.affected_appointments(
        session, await service.get_for_user(session, leave_id, user)
    )


@admin_router.post("/{leave_id}/approve", response_model=LeaveRead)
async def approve_leave(
    leave_id: UUID,
    data: LeaveReview | None = None,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(admin),
) -> LeaveRead:
    return await service.review_leave(session, leave_id, user, True, data.note if data else None)


@admin_router.post("/{leave_id}/reject", response_model=LeaveRead)
async def reject_leave(
    leave_id: UUID,
    data: LeaveReview | None = None,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(admin),
) -> LeaveRead:
    return await service.review_leave(session, leave_id, user, False, data.note if data else None)


@admin_router.post("/{leave_id}/cancel-appointments", response_model=list[AppointmentRead])
async def cancel_affected_appointments(
    leave_id: UUID,
    data: LeaveAppointmentsCancel,
    session: AsyncSession = Depends(get_db_session),
) -> list[AppointmentRead]:
    return await service.cancel_affected_appointments(session, leave_id, data.reason)
