from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.doctors.models import Doctor


async def list_doctors(
    session: AsyncSession,
    branch_id: UUID | None,
    specialization: str | None,
    offset: int,
    limit: int,
) -> list[Doctor]:
    statement = select(Doctor).order_by(Doctor.full_name).offset(offset).limit(limit)
    if branch_id is not None:
        statement = statement.where(Doctor.branch_id == branch_id)
    if specialization is not None:
        statement = statement.where(Doctor.specialization.ilike(f"%{specialization}%"))
    return list(await session.scalars(statement))


async def get_doctor(session: AsyncSession, doctor_id: UUID) -> Doctor | None:
    return await session.get(Doctor, doctor_id)


async def add_doctor(session: AsyncSession, doctor: Doctor) -> Doctor:
    session.add(doctor)
    await session.flush()
    return doctor
