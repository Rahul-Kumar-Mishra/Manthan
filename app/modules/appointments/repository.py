from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import AppointmentStatus
from app.modules.appointments.models import Appointment


async def has_doctor_conflict(
    session: AsyncSession,
    doctor_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
) -> bool:
    result = await session.scalar(
        select(Appointment.id)
        .where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.starts_at < ends_at,
            Appointment.ends_at > starts_at,
        )
        .limit(1)
    )
    return result is not None


async def list_patient_appointments(session: AsyncSession, patient_id: UUID) -> list[Appointment]:
    result = await session.scalars(
        select(Appointment)
        .where(Appointment.patient_id == patient_id)
        .order_by(Appointment.starts_at)
    )
    return list(result)


async def list_doctor_appointments(session: AsyncSession, doctor_id: UUID) -> list[Appointment]:
    result = await session.scalars(
        select(Appointment)
        .where(Appointment.doctor_id == doctor_id)
        .order_by(Appointment.starts_at)
    )
    return list(result)


async def list_appointments(session: AsyncSession, offset: int, limit: int) -> list[Appointment]:
    result = await session.scalars(
        select(Appointment).order_by(Appointment.starts_at).offset(offset).limit(limit)
    )
    return list(result)


async def get_appointment(session: AsyncSession, appointment_id: UUID) -> Appointment | None:
    return await session.get(Appointment, appointment_id)
