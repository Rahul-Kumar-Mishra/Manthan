from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import UserRole
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.auth.models import User
from app.modules.branches import repository as branch_repository
from app.modules.doctors import repository
from app.modules.doctors.models import Doctor
from app.modules.doctors.schemas import DoctorCreate, DoctorUpdate


async def list_doctors(
    session: AsyncSession,
    branch_id: UUID | None,
    specialization: str | None,
    offset: int,
    limit: int,
) -> list[Doctor]:
    return await repository.list_doctors(session, branch_id, specialization, offset, limit)


async def get_doctor(session: AsyncSession, doctor_id: UUID) -> Doctor:
    doctor = await repository.get_doctor(session, doctor_id)
    if doctor is None:
        raise NotFoundError("Doctor not found")
    return doctor


async def get_doctor_for_user(session: AsyncSession, user_id: UUID) -> Doctor:
    doctor = await session.scalar(select(Doctor).where(Doctor.user_id == user_id))
    if doctor is None:
        raise NotFoundError("Doctor profile not found")
    return doctor


async def validate_user_link(session: AsyncSession, user_id: UUID | None) -> None:
    if user_id is None:
        return
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError("Doctor account not found")
    if user.role != UserRole.DOCTOR:
        raise ConflictError("Linked account must have the doctor role")


async def create_doctor(session: AsyncSession, data: DoctorCreate) -> Doctor:
    if await branch_repository.get_branch(session, data.branch_id) is None:
        raise NotFoundError("Branch not found")
    await validate_user_link(session, data.user_id)
    doctor = Doctor(**data.model_dump())
    try:
        await repository.add_doctor(session, doctor)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("A doctor with that email already exists") from exc
    await session.refresh(doctor)
    return doctor


async def update_doctor(session: AsyncSession, doctor_id: UUID, data: DoctorUpdate) -> Doctor:
    doctor = await get_doctor(session, doctor_id)
    changes = data.model_dump(exclude_unset=True)
    if "user_id" in changes:
        await validate_user_link(session, changes["user_id"])
    branch_id = changes.get("branch_id")
    if branch_id is not None and await branch_repository.get_branch(session, branch_id) is None:
        raise NotFoundError("Branch not found")
    for field, value in changes.items():
        setattr(doctor, field, value)
    if doctor.available_online and not doctor.online_fee_paise:
        raise ConflictError("Set an online consultation fee to offer on-call appointments")
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("A doctor with that email already exists") from exc
    await session.refresh(doctor)
    return doctor


async def delete_doctor(session: AsyncSession, doctor_id: UUID) -> None:
    doctor = await get_doctor(session, doctor_id)
    await session.delete(doctor)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("Cannot delete a doctor with appointment history") from exc
