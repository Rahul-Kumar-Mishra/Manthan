from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.common.enums import AppointmentMode, Module, UserRole
from app.modules.access.dependencies import require_module
from app.modules.appointments import service
from app.modules.appointments.schemas import (
    AppointmentAvailability,
    AppointmentCancel,
    AppointmentCreate,
    AppointmentRead,
)
from app.modules.auth.dependencies import require_roles
from app.modules.auth.models import User

patient = require_roles(UserRole.PATIENT)
doctor = require_roles(UserRole.DOCTOR)

# Customers: booking under /book, their own visits under /my/appointments.
book_router = APIRouter()
my_router = APIRouter()
# Doctors: their schedule under /doctor/appointments.
doctor_router = APIRouter()
# Operations under /admin/appointments; needs the appointments module.
admin_router = APIRouter(dependencies=[Depends(require_module(Module.APPOINTMENTS))])


async def _availability(
    session: AsyncSession, doctor_id: UUID, starts_at: datetime, ends_at: datetime
) -> AppointmentAvailability:
    request = AppointmentCreate(doctor_id=doctor_id, starts_at=starts_at, ends_at=ends_at)
    reason = await service.unavailable_reason(
        session, request.doctor_id, request.starts_at, request.ends_at
    )
    return AppointmentAvailability(
        doctor_id=doctor_id,
        starts_at=request.starts_at,
        ends_at=request.ends_at,
        available=reason is None,
        reason=reason,
    )


# ---------- customer ----------


@book_router.get("/appointment/availability", response_model=AppointmentAvailability)
async def check_availability(
    doctor_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(patient),
) -> AppointmentAvailability:
    return await _availability(session, doctor_id, starts_at, ends_at)


@book_router.post(
    "/appointment", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED
)
async def book_appointment(
    data: AppointmentCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(patient),
) -> AppointmentRead:
    return await service.book_for_patient(
        session,
        user.id,
        data.doctor_id,
        data.starts_at,
        data.ends_at,
        data.mode,
        data.contact_phone,
    )


@book_router.post(
    "/online-consultation", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED
)
async def book_online_consultation(
    data: AppointmentCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(patient),
) -> AppointmentRead:
    """An on-call (phone) consultation, paid online. Same as /book/appointment with mode=online."""
    return await service.book_for_patient(
        session,
        user.id,
        data.doctor_id,
        data.starts_at,
        data.ends_at,
        AppointmentMode.ONLINE,
        data.contact_phone,
    )


@my_router.get("", response_model=list[AppointmentRead])
async def my_appointments(
    session: AsyncSession = Depends(get_db_session), user: User = Depends(patient)
) -> list[AppointmentRead]:
    return await service.list_for_patient(session, user.id)


@my_router.get("/{appointment_id}", response_model=AppointmentRead)
async def my_appointment(
    appointment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(patient),
) -> AppointmentRead:
    return await service.get_for_user(session, appointment_id, user.id, UserRole.PATIENT)


@my_router.post("/{appointment_id}/cancel", response_model=AppointmentRead)
async def cancel_my_appointment(
    appointment_id: UUID,
    data: AppointmentCancel | None = None,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(patient),
) -> AppointmentRead:
    reason = data.reason if data else None
    return await service.cancel_for_user(session, appointment_id, user.id, UserRole.PATIENT, reason)


# ---------- doctor ----------


@doctor_router.get("", response_model=list[AppointmentRead])
async def doctor_schedule(
    session: AsyncSession = Depends(get_db_session), user: User = Depends(doctor)
) -> list[AppointmentRead]:
    return await service.list_for_doctor(session, user.id)


@doctor_router.get("/{appointment_id}", response_model=AppointmentRead)
async def doctor_appointment(
    appointment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(doctor),
) -> AppointmentRead:
    return await service.get_for_user(session, appointment_id, user.id, UserRole.DOCTOR)


@doctor_router.post("/{appointment_id}/complete", response_model=AppointmentRead)
async def doctor_complete(
    appointment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(doctor),
) -> AppointmentRead:
    return await service.complete_appointment(session, appointment_id, user.id, UserRole.DOCTOR)


# ---------- admin ----------


@admin_router.get("", response_model=list[AppointmentRead])
async def list_all_appointments(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> list[AppointmentRead]:
    return await service.list_all(session, offset, limit)


@admin_router.get("/availability", response_model=AppointmentAvailability)
async def admin_availability(
    doctor_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    session: AsyncSession = Depends(get_db_session),
) -> AppointmentAvailability:
    return await _availability(session, doctor_id, starts_at, ends_at)


@admin_router.get("/{appointment_id}", response_model=AppointmentRead)
async def admin_get_appointment(
    appointment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_roles(UserRole.ADMIN)),
) -> AppointmentRead:
    return await service.get_for_user(session, appointment_id, user.id, UserRole.ADMIN)


@admin_router.post("/{appointment_id}/cancel", response_model=AppointmentRead)
async def admin_cancel(
    appointment_id: UUID,
    data: AppointmentCancel | None = None,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_roles(UserRole.ADMIN)),
) -> AppointmentRead:
    reason = data.reason.strip() if data and data.reason else ""
    # Cancelling on a patient's behalf must say why; the patient sees the reason.
    if len(reason) < 3:
        raise HTTPException(
            status_code=422,
            detail="Administrators must give a cancellation reason (at least 3 characters)",
        )
    return await service.cancel_for_user(session, appointment_id, user.id, UserRole.ADMIN, reason)


@admin_router.post("/{appointment_id}/complete", response_model=AppointmentRead)
async def admin_complete(
    appointment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_roles(UserRole.ADMIN)),
) -> AppointmentRead:
    return await service.complete_appointment(session, appointment_id, user.id, UserRole.ADMIN)
