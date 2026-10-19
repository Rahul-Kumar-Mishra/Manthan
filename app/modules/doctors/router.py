from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.common.enums import Module, UserRole
from app.modules.access.dependencies import require_module
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.auth.models import User
from app.modules.doctors import service
from app.modules.doctors.schemas import DoctorCreate, DoctorRead, DoctorUpdate
from app.modules.leaves import service as leave_service
from app.modules.leaves.schemas import LeaveWindow

# Browsing doctors (any signed-in user).
router = APIRouter(dependencies=[Depends(get_current_user)])
# The signed-in doctor's own profile, under /doctor.
doctor_router = APIRouter()
admin_router = APIRouter()
# Any admin may read the directory (names show up across every module); changes need doctors.
manage = [Depends(require_module(Module.DOCTORS))]


@router.get("", response_model=list[DoctorRead])
@admin_router.get("", response_model=list[DoctorRead])
async def list_doctors(
    branch_id: UUID | None = None,
    specialization: str | None = Query(default=None, min_length=2, max_length=120),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> list[DoctorRead]:
    return await service.list_doctors(session, branch_id, specialization, offset, limit)


@router.get("/{doctor_id}", response_model=DoctorRead)
@admin_router.get("/{doctor_id}", response_model=DoctorRead)
async def get_doctor(
    doctor_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> DoctorRead:
    return await service.get_doctor(session, doctor_id)


@router.get("/{doctor_id}/unavailability", response_model=list[LeaveWindow])
async def doctor_unavailability(
    doctor_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> list[LeaveWindow]:
    """Approved leave still to come, without the reason, so patients can plan bookings."""
    return await leave_service.list_blocked_windows(session, doctor_id)


@doctor_router.get("/profile", response_model=DoctorRead)
async def get_my_doctor_profile(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_roles(UserRole.DOCTOR)),
) -> DoctorRead:
    return await service.get_doctor_for_user(session, user.id)


@admin_router.post(
    "", response_model=DoctorRead, status_code=status.HTTP_201_CREATED, dependencies=manage
)
async def create_doctor(
    data: DoctorCreate, session: AsyncSession = Depends(get_db_session)
) -> DoctorRead:
    return await service.create_doctor(session, data)


@admin_router.patch("/{doctor_id}", response_model=DoctorRead, dependencies=manage)
async def update_doctor(
    doctor_id: UUID, data: DoctorUpdate, session: AsyncSession = Depends(get_db_session)
) -> DoctorRead:
    return await service.update_doctor(session, doctor_id, data)


@admin_router.delete("/{doctor_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=manage)
async def delete_doctor(
    doctor_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> Response:
    await service.delete_doctor(session, doctor_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
