from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.common.enums import Module
from app.modules.access.dependencies import require_module
from app.modules.branches import service
from app.modules.branches.schemas import BranchCreate, BranchRead, BranchUpdate

# Public browsing for customers.
router = APIRouter()
admin_router = APIRouter()
# Any admin may read the directory (names show up across every module); changes need network.
manage = [Depends(require_module(Module.NETWORK))]


@router.get("/hospitals/{hospital_id}/branches", response_model=list[BranchRead])
@admin_router.get("/hospitals/{hospital_id}/branches", response_model=list[BranchRead])
async def list_hospital_branches(
    hospital_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> list[BranchRead]:
    return await service.list_branches(session, hospital_id, offset, limit)


@router.get("/branches", response_model=list[BranchRead])
@admin_router.get("/branches", response_model=list[BranchRead])
async def list_branches(
    hospital_id: UUID | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> list[BranchRead]:
    return await service.list_branches(session, hospital_id, offset, limit)


@router.get("/branches/{branch_id}", response_model=BranchRead)
@admin_router.get("/branches/{branch_id}", response_model=BranchRead)
async def get_branch(
    branch_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> BranchRead:
    return await service.get_branch(session, branch_id)


@admin_router.post(
    "/hospitals/{hospital_id}/branches",
    response_model=BranchRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=manage,
)
async def create_branch(
    hospital_id: UUID, data: BranchCreate, session: AsyncSession = Depends(get_db_session)
) -> BranchRead:
    return await service.create_branch(session, hospital_id, data)


@admin_router.patch("/branches/{branch_id}", response_model=BranchRead, dependencies=manage)
async def update_branch(
    branch_id: UUID, data: BranchUpdate, session: AsyncSession = Depends(get_db_session)
) -> BranchRead:
    return await service.update_branch(session, branch_id, data)


@admin_router.delete(
    "/branches/{branch_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=manage
)
async def delete_branch(
    branch_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> Response:
    await service.delete_branch(session, branch_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
