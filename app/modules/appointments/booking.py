from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import AppointmentMode, AppointmentStatus, PaymentPurpose, PaymentStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.appointments import repository
from app.modules.appointments.models import Appointment
from app.modules.doctors.models import Doctor
from app.modules.leaves import repository as leave_repository
from app.modules.patients.service import get_patient_for_user

ON_LEAVE = "Doctor is on leave during this time"
BOOKED = "Doctor already has an appointment during this time"
# An on-call slot is held while the patient pays; unpaid holds are released after this.
PAYMENT_HOLD = timedelta(minutes=15)


async def release_unpaid_holds(session: AsyncSession) -> int:
    from app.modules.payments import service as payments

    cutoff = datetime.now(UTC) - PAYMENT_HOLD
    stale = list(
        await session.scalars(
            select(Appointment).where(
                Appointment.status == AppointmentStatus.SCHEDULED,
                Appointment.payment_status == PaymentStatus.PENDING,
                Appointment.created_at < cutoff,
            )
        )
    )
    for appointment in stale:
        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancelled_at = datetime.now(UTC)
        appointment.cancellation_reason = "Payment was not completed in time"
        appointment.payment_status = PaymentStatus.CANCELLED
        await payments.void_pending(session, appointment.id)
    if stale:
        await session.commit()
    return len(stale)


async def unavailable_reason(
    session: AsyncSession, doctor_id: UUID, starts_at: datetime, ends_at: datetime
) -> str | None:
    doctor = await session.get(Doctor, doctor_id)
    if doctor is None or not doctor.is_active:
        raise NotFoundError("Active doctor not found")
    await release_unpaid_holds(session)
    if await leave_repository.has_approved_leave(session, doctor_id, starts_at, ends_at):
        return ON_LEAVE
    if await repository.has_doctor_conflict(session, doctor_id, starts_at, ends_at):
        return BOOKED
    return None


async def is_available(
    session: AsyncSession, doctor_id: UUID, starts_at: datetime, ends_at: datetime
) -> bool:
    return await unavailable_reason(session, doctor_id, starts_at, ends_at) is None


async def book_appointment(
    session: AsyncSession,
    patient_user_id: UUID,
    doctor_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    mode: AppointmentMode = AppointmentMode.IN_PERSON,
    contact_phone: str | None = None,
) -> Appointment:
    from app.modules.payments import service as payments

    await release_unpaid_holds(session)
    doctor = await session.scalar(select(Doctor).where(Doctor.id == doctor_id).with_for_update())
    if doctor is None or not doctor.is_active:
        raise NotFoundError("Active doctor not found")
    patient = await get_patient_for_user(session, patient_user_id)
    phone = (contact_phone or patient.phone or "").strip() or None
    if mode == AppointmentMode.ONLINE:
        if not doctor.available_online or not doctor.online_fee_paise:
            raise ConflictError("This doctor does not take on-call appointments")
        if phone is None:
            raise ConflictError("Add a phone number so the doctor can call you")
    if await leave_repository.has_approved_leave(session, doctor_id, starts_at, ends_at):
        raise ConflictError(ON_LEAVE)
    if await repository.has_doctor_conflict(session, doctor_id, starts_at, ends_at):
        raise ConflictError(BOOKED)

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor_id,
        starts_at=starts_at,
        ends_at=ends_at,
        status=AppointmentStatus.SCHEDULED,
        mode=mode,
        contact_phone=phone,
        fee_paise=doctor.online_fee_paise
        if mode == AppointmentMode.ONLINE
        else doctor.consultation_fee_paise,
        # In-clinic visits are paid at the desk; on-call visits are paid online up front.
        payment_status=PaymentStatus.PENDING
        if mode == AppointmentMode.ONLINE
        else PaymentStatus.NOT_REQUIRED,
    )
    try:
        session.add(appointment)
        await session.flush()
        if mode == AppointmentMode.ONLINE:
            payment = await payments.create_payment(
                session,
                patient_user_id,
                PaymentPurpose.ONLINE_CONSULTATION,
                appointment.id,
                doctor.online_fee_paise,
            )
            appointment.payment_id = payment.id
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(BOOKED) from exc
    await session.refresh(appointment)
    return appointment
