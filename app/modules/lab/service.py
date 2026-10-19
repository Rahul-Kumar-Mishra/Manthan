from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import CollectionType, LabBookingStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.auth.models import User
from app.modules.lab.models import LabBooking, LabTest
from app.modules.lab.schemas import LabBookingCreate, LabTestCreate, LabTestUpdate

NEXT_STATUS = {
    LabBookingStatus.BOOKED: LabBookingStatus.SAMPLE_COLLECTED,
    LabBookingStatus.SAMPLE_COLLECTED: LabBookingStatus.COMPLETED,
}


async def list_tests(session: AsyncSession, include_inactive: bool) -> list[LabTest]:
    statement = select(LabTest).order_by(LabTest.category, LabTest.name)
    if not include_inactive:
        statement = statement.where(LabTest.is_active.is_(True))
    return list(await session.scalars(statement))


async def get_test(session: AsyncSession, test_id: UUID) -> LabTest:
    test = await session.get(LabTest, test_id)
    if test is None:
        raise NotFoundError("Lab test not found")
    return test


async def create_test(session: AsyncSession, data: LabTestCreate) -> LabTest:
    test = LabTest(**data.model_dump())
    test.code = test.code.upper()
    session.add(test)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("A lab test with that code already exists") from exc
    await session.refresh(test)
    return test


async def update_test(session: AsyncSession, test_id: UUID, data: LabTestUpdate) -> LabTest:
    test = await get_test(session, test_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(test, field, value)
    await session.commit()
    await session.refresh(test)
    return test


async def delete_test(session: AsyncSession, test_id: UUID) -> None:
    await session.delete(await get_test(session, test_id))
    await session.commit()


async def book(session: AsyncSession, user: User, data: LabBookingCreate) -> LabBooking:
    test = await get_test(session, data.lab_test_id)
    if not test.is_active:
        raise ConflictError("This lab test is not currently offered")
    address = (data.address or "").strip() or None
    if data.collection_type == CollectionType.HOME:
        if not test.home_collection:
            raise ConflictError("Home sample collection is not available for this test")
        if address is None or len(address) < 10:
            raise ConflictError("Enter the full address for home collection")
    booking = LabBooking(
        user_id=user.id,
        lab_test_id=test.id,
        test_name=test.name,
        price_paise=test.price_paise,
        scheduled_at=data.scheduled_at,
        collection_type=data.collection_type,
        address=address if data.collection_type == CollectionType.HOME else None,
        contact_phone=data.contact_phone.strip(),
    )
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    return booking


async def list_bookings(
    session: AsyncSession, user_id: UUID | None, status: LabBookingStatus | None = None
) -> list[LabBooking]:
    statement = select(LabBooking).order_by(LabBooking.scheduled_at.desc())
    if user_id is not None:
        statement = statement.where(LabBooking.user_id == user_id)
    if status is not None:
        statement = statement.where(LabBooking.status == status)
    return list(await session.scalars(statement.limit(500)))


async def get_booking(session: AsyncSession, booking_id: UUID) -> LabBooking:
    booking = await session.get(LabBooking, booking_id)
    if booking is None:
        raise NotFoundError("Lab booking not found")
    return booking


async def cancel(session: AsyncSession, booking: LabBooking, reason: str) -> LabBooking:
    if booking.status != LabBookingStatus.BOOKED:
        raise ConflictError("Only bookings whose sample hasn't been collected can be cancelled")
    booking.status = LabBookingStatus.CANCELLED
    booking.cancellation_reason = reason
    await session.commit()
    await session.refresh(booking)
    return booking


async def advance(
    session: AsyncSession, booking_id: UUID, target: LabBookingStatus, note: str | None
) -> LabBooking:
    booking = await get_booking(session, booking_id)
    if NEXT_STATUS.get(booking.status) != target:
        raise ConflictError(
            f"A booking that is {booking.status.value} cannot move to {target.value}"
        )
    booking.status = target
    if note:
        booking.result_note = note.strip()
    await session.commit()
    await session.refresh(booking)
    return booking
