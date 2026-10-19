from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.appointments.models import Appointment
from app.modules.doctors.models import Doctor
from app.modules.patients import repository
from app.modules.patients.models import Patient
from app.modules.patients.schemas import PatientCreate, PatientUpdate


async def list_patients(session: AsyncSession, offset: int, limit: int) -> list[Patient]:
    return await repository.list_patients(session, offset, limit)


async def get_patient(session: AsyncSession, patient_id: UUID) -> Patient:
    patient = await repository.get_patient(session, patient_id)
    if patient is None:
        raise NotFoundError("Patient not found")
    return patient


async def get_patient_for_user(session: AsyncSession, user_id: UUID) -> Patient:
    patient = await session.scalar(select(Patient).where(Patient.user_id == user_id))
    if patient is None:
        raise NotFoundError("Patient record not found")
    return patient


async def doctor_can_access_patient(
    session: AsyncSession, doctor_user_id: UUID, patient_id: UUID
) -> bool:
    doctor_id = await session.scalar(select(Doctor.id).where(Doctor.user_id == doctor_user_id))
    if doctor_id is None:
        return False
    appointment_id = await session.scalar(
        select(Appointment.id)
        .where(
            Appointment.doctor_id == doctor_id,
            Appointment.patient_id == patient_id,
        )
        .limit(1)
    )
    return appointment_id is not None


async def create_patient(session: AsyncSession, data: PatientCreate) -> Patient:
    patient = Patient(**data.model_dump())
    await repository.add_patient(session, patient)
    await session.commit()
    await session.refresh(patient)
    return patient


async def update_patient(session: AsyncSession, patient_id: UUID, data: PatientUpdate) -> Patient:
    patient = await get_patient(session, patient_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    await session.commit()
    await session.refresh(patient)
    return patient


async def delete_patient(session: AsyncSession, patient_id: UUID) -> None:
    patient = await get_patient(session, patient_id)
    await session.delete(patient)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("Cannot delete a patient with appointment history") from exc
