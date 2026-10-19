from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.common.enums import Module, UserRole
from app.modules.access.dependencies import require_module
from app.modules.auth.dependencies import require_roles
from app.modules.auth.models import User
from app.modules.patients import service
from app.modules.patients.schemas import PatientCreate, PatientRead, PatientUpdate

# The signed-in patient's own record, at /profile.
router = APIRouter()
# A doctor reading the patients they have appointments with, under /doctor.
doctor_router = APIRouter()
# Patient records under /admin; needs the patients module.
admin_router = APIRouter(dependencies=[Depends(require_module(Module.PATIENTS))])


@router.get("", response_model=PatientRead)
async def get_my_profile(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_roles(UserRole.PATIENT)),
) -> PatientRead:
    return await service.get_patient_for_user(session, user.id)


@router.patch("", response_model=PatientRead)
async def update_my_profile(
    data: PatientUpdate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_roles(UserRole.PATIENT)),
) -> PatientRead:
    patient = await service.get_patient_for_user(session, user.id)
    return await service.update_patient(session, patient.id, data)


@doctor_router.get("/patients/{patient_id}", response_model=PatientRead)
async def get_my_patient(
    patient_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_roles(UserRole.DOCTOR)),
) -> PatientRead:
    patient = await service.get_patient(session, patient_id)
    if not await service.doctor_can_access_patient(session, user.id, patient.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@admin_router.get("", response_model=list[PatientRead])
async def list_patients(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> list[PatientRead]:
    return await service.list_patients(session, offset, limit)


@admin_router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
async def create_patient(
    data: PatientCreate, session: AsyncSession = Depends(get_db_session)
) -> PatientRead:
    return await service.create_patient(session, data)


@admin_router.get("/{patient_id}", response_model=PatientRead)
async def get_patient(
    patient_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> PatientRead:
    return await service.get_patient(session, patient_id)


@admin_router.patch("/{patient_id}", response_model=PatientRead)
async def update_patient(
    patient_id: UUID, data: PatientUpdate, session: AsyncSession = Depends(get_db_session)
) -> PatientRead:
    return await service.update_patient(session, patient_id, data)


@admin_router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> Response:
    await service.delete_patient(session, patient_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
