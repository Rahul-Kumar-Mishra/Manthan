from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hospitals.models import Hospital


async def list_hospitals(session: AsyncSession, offset: int, limit: int) -> list[Hospital]:
    result = await session.scalars(
        select(Hospital).order_by(Hospital.name).offset(offset).limit(limit)
    )
    return list(result)


async def get_hospital(session: AsyncSession, hospital_id: UUID) -> Hospital | None:
    return await session.get(Hospital, hospital_id)


async def add_hospital(session: AsyncSession, hospital: Hospital) -> Hospital:
    session.add(hospital)
    await session.flush()
    return hospital
