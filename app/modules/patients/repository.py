from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.patients.models import Patient


async def list_patients(session: AsyncSession, offset: int, limit: int) -> list[Patient]:
    result = await session.scalars(
        select(Patient).order_by(Patient.full_name).offset(offset).limit(limit)
    )
    return list(result)


async def get_patient(session: AsyncSession, patient_id: UUID) -> Patient | None:
    return await session.get(Patient, patient_id)


async def add_patient(session: AsyncSession, patient: Patient) -> Patient:
    session.add(patient)
    await session.flush()
    return patient
