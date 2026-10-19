from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.common.enums import LabBookingStatus, Module, UserRole
from app.modules.access.dependencies import require_module
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.auth.models import User
from app.modules.lab import service
from app.modules.lab.schemas import (
    LabBookingCancel,
    LabBookingCreate,
    LabBookingRead,
    LabBookingStatusUpdate,
    LabTestCreate,
    LabTestRead,
    LabTestUpdate,
)

patient = require_roles(UserRole.PATIENT)

# Customers: catalogue at /lab-tests, booking at /book/lab-test, own at /my/lab-tests.
catalog_router = APIRouter(dependencies=[Depends(get_current_user)])
book_router = APIRouter()
my_router = APIRouter()
# Catalogue at /admin/lab-tests and bookings at /admin/lab-bookings; lab module.
admin_tests_router = APIRouter(dependencies=[Depends(require_module(Module.LAB))])
admin_bookings_router = APIRouter(dependencies=[Depends(require_module(Module.LAB))])


@catalog_router.get("", response_model=list[LabTestRead])
async def list_tests(session: AsyncSession = Depends(get_db_session)) -> list[LabTestRead]:
    return await service.list_tests(session, include_inactive=False)


@book_router.post("/lab-test", response_model=LabBookingRead, status_code=status.HTTP_201_CREATED)
async def book_lab_test(
    data: LabBookingCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(patient),
) -> LabBookingRead:
    return await service.book(session, user, data)


@my_router.get("", response_model=list[LabBookingRead])
async def my_bookings(
    session: AsyncSession = Depends(get_db_session), user: User = Depends(patient)
) -> list[LabBookingRead]:
    return await service.list_bookings(session, user.id)


@my_router.post("/{booking_id}/cancel", response_model=LabBookingRead)
async def cancel_my_booking(
    booking_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(patient),
) -> LabBookingRead:
    booking = await service.get_booking(session, booking_id)
    if booking.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab booking not found")
    return await service.cancel(session, booking, "Cancelled by patient")


@admin_tests_router.get("", response_model=list[LabTestRead])
async def admin_list_tests(session: AsyncSession = Depends(get_db_session)) -> list[LabTestRead]:
    return await service.list_tests(session, include_inactive=True)


@admin_tests_router.post("", response_model=LabTestRead, status_code=status.HTTP_201_CREATED)
async def create_test(
    data: LabTestCreate, session: AsyncSession = Depends(get_db_session)
) -> LabTestRead:
    return await service.create_test(session, data)


@admin_tests_router.patch("/{test_id}", response_model=LabTestRead)
async def update_test(
    test_id: UUID, data: LabTestUpdate, session: AsyncSession = Depends(get_db_session)
) -> LabTestRead:
    return await service.update_test(session, test_id, data)


@admin_tests_router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test(test_id: UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    await service.delete_test(session, test_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_bookings_router.get("", response_model=list[LabBookingRead])
async def all_bookings(
    booking_status: LabBookingStatus | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db_session),
) -> list[LabBookingRead]:
    return await service.list_bookings(session, None, booking_status)


@admin_bookings_router.post("/{booking_id}/cancel", response_model=LabBookingRead)
async def admin_cancel_booking(
    booking_id: UUID,
    data: LabBookingCancel | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> LabBookingRead:
    reason = (data.reason or "").strip() if data else ""
    if len(reason) < 3:
        raise HTTPException(status_code=422, detail="Give the patient a reason for cancelling")
    return await service.cancel(session, await service.get_booking(session, booking_id), reason)


@admin_bookings_router.post("/{booking_id}/status", response_model=LabBookingRead)
async def advance_booking(
    booking_id: UUID,
    data: LabBookingStatusUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> LabBookingRead:
    return await service.advance(
        session, booking_id, LabBookingStatus(data.status), data.result_note
    )
