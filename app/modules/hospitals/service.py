from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.hospitals import repository
from app.modules.hospitals.models import Hospital
from app.modules.hospitals.schemas import HospitalCreate, HospitalUpdate


async def list_hospitals(session: AsyncSession, offset: int, limit: int) -> list[Hospital]:
    return await repository.list_hospitals(session, offset, limit)


async def get_hospital(session: AsyncSession, hospital_id: UUID) -> Hospital:
    hospital = await repository.get_hospital(session, hospital_id)
    if hospital is None:
        raise NotFoundError("Hospital not found")
    return hospital


async def create_hospital(session: AsyncSession, data: HospitalCreate) -> Hospital:
    hospital = Hospital(**data.model_dump())
    try:
        await repository.add_hospital(session, hospital)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("A hospital with that name already exists") from exc
    await session.refresh(hospital)
    return hospital


async def update_hospital(
    session: AsyncSession, hospital_id: UUID, data: HospitalUpdate
) -> Hospital:
    hospital = await get_hospital(session, hospital_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(hospital, field, value)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("A hospital with that name already exists") from exc
    await session.refresh(hospital)
    return hospital


async def delete_hospital(session: AsyncSession, hospital_id: UUID) -> None:
    hospital = await get_hospital(session, hospital_id)
    await session.delete(hospital)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("Cannot delete a hospital with dependent records") from exc
