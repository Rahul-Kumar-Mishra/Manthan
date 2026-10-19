from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.common.enums import Module
from app.modules.access.dependencies import require_module
from app.modules.hospitals import service
from app.modules.hospitals.schemas import HospitalCreate, HospitalRead, HospitalUpdate

# Public browsing for customers.
router = APIRouter()
admin_router = APIRouter()
# Any admin may read the directory (names show up across every module); changes need network.
manage = [Depends(require_module(Module.NETWORK))]


@router.get("", response_model=list[HospitalRead])
@admin_router.get("", response_model=list[HospitalRead])
async def list_hospitals(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> list[HospitalRead]:
    return await service.list_hospitals(session, offset, limit)


@router.get("/{hospital_id}", response_model=HospitalRead)
@admin_router.get("/{hospital_id}", response_model=HospitalRead)
async def get_hospital(
    hospital_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> HospitalRead:
    return await service.get_hospital(session, hospital_id)


@admin_router.post(
    "", response_model=HospitalRead, status_code=status.HTTP_201_CREATED, dependencies=manage
)
async def create_hospital(
    data: HospitalCreate, session: AsyncSession = Depends(get_db_session)
) -> HospitalRead:
    return await service.create_hospital(session, data)


@admin_router.patch("/{hospital_id}", response_model=HospitalRead, dependencies=manage)
async def update_hospital(
    hospital_id: UUID, data: HospitalUpdate, session: AsyncSession = Depends(get_db_session)
) -> HospitalRead:
    return await service.update_hospital(session, hospital_id, data)


@admin_router.delete("/{hospital_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=manage)
async def delete_hospital(
    hospital_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> Response:
    await service.delete_hospital(session, hospital_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
