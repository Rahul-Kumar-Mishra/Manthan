from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.common.enums import Module, StaffStatus
from app.modules.access.dependencies import require_module
from app.modules.auth import service as auth_service
from app.modules.auth.schemas import StaffUserCreate, UserRead
from app.modules.staff import service
from app.modules.staff.schemas import StaffCreate, StaffOffboard, StaffRead, StaffUpdate

# Staff directory and sign-in accounts at /admin/staff; staff module.
admin_router = APIRouter(dependencies=[Depends(require_module(Module.STAFF))])


@admin_router.post("/accounts", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_sign_in_account(
    data: StaffUserCreate, session: AsyncSession = Depends(get_db_session)
) -> UserRead:
    """Create a login for a doctor or admin staff member (admins start with no modules)."""
    return await auth_service.create_staff_user(session, data)


@admin_router.get("", response_model=list[StaffRead])
async def list_staff(
    staff_status: StaffStatus | None = Query(default=None, alias="status"),
    department: str | None = Query(default=None, max_length=120),
    search: str | None = Query(default=None, max_length=80),
    session: AsyncSession = Depends(get_db_session),
) -> list[StaffRead]:
    return await service.list_staff(session, staff_status, department, search)


@admin_router.post("", response_model=StaffRead, status_code=status.HTTP_201_CREATED)
async def create_staff(
    data: StaffCreate,
    session: AsyncSession = Depends(get_db_session),
) -> StaffRead:
    return await service.create_staff(session, data)


@admin_router.get("/{staff_id}", response_model=StaffRead)
async def get_staff(
    staff_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> StaffRead:
    return await service.get_staff(session, staff_id)


@admin_router.patch("/{staff_id}", response_model=StaffRead)
async def update_staff(
    staff_id: UUID,
    data: StaffUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> StaffRead:
    return await service.update_staff(session, staff_id, data)


@admin_router.post("/{staff_id}/offboard", response_model=StaffRead)
async def offboard(
    staff_id: UUID,
    data: StaffOffboard | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> StaffRead:
    return await service.offboard(session, staff_id, data or StaffOffboard())


@admin_router.delete("/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff(
    staff_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await service.delete_staff(session, staff_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
