from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import AppointmentMode, AppointmentStatus, PaymentStatus, UserRole
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.appointments import booking, repository
from app.modules.appointments.models import Appointment
from app.modules.doctors.service import get_doctor_for_user
from app.modules.patients.service import get_patient_for_user


async def is_available(
    session: AsyncSession, doctor_id: UUID, starts_at: datetime, ends_at: datetime
) -> bool:
    return await booking.is_available(session, doctor_id, starts_at, ends_at)


async def unavailable_reason(
    session: AsyncSession, doctor_id: UUID, starts_at: datetime, ends_at: datetime
) -> str | None:
    return await booking.unavailable_reason(session, doctor_id, starts_at, ends_at)


async def book_for_patient(
    session: AsyncSession,
    user_id: UUID,
    doctor_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    mode: AppointmentMode = AppointmentMode.IN_PERSON,
    contact_phone: str | None = None,
) -> Appointment:
    return await booking.book_appointment(
        session, user_id, doctor_id, starts_at, ends_at, mode, contact_phone
    )


async def list_for_patient(session: AsyncSession, user_id: UUID) -> list[Appointment]:
    await booking.release_unpaid_holds(session)
    patient = await get_patient_for_user(session, user_id)
    return await repository.list_patient_appointments(session, patient.id)


async def list_for_doctor(session: AsyncSession, user_id: UUID) -> list[Appointment]:
    await booking.release_unpaid_holds(session)
    doctor = await get_doctor_for_user(session, user_id)
    return await repository.list_doctor_appointments(session, doctor.id)


async def list_all(session: AsyncSession, offset: int, limit: int) -> list[Appointment]:
    await booking.release_unpaid_holds(session)
    return await repository.list_appointments(session, offset, limit)


async def get_for_user(
    session: AsyncSession, appointment_id: UUID, user_id: UUID, role: UserRole
) -> Appointment:
    appointment = await repository.get_appointment(session, appointment_id)
    if appointment is None:
        raise NotFoundError("Appointment not found")
    if role == UserRole.PATIENT:
        patient = await get_patient_for_user(session, user_id)
        if appointment.patient_id != patient.id:
            raise NotFoundError("Appointment not found")
    elif role == UserRole.DOCTOR:
        doctor = await get_doctor_for_user(session, user_id)
        if appointment.doctor_id != doctor.id:
            raise NotFoundError("Appointment not found")
    return appointment


async def cancel_for_user(
    session: AsyncSession,
    appointment_id: UUID,
    user_id: UUID,
    role: UserRole,
    reason: str | None = None,
) -> Appointment:
    appointment = await get_for_user(session, appointment_id, user_id, role)
    if appointment.status != AppointmentStatus.SCHEDULED:
        raise ConflictError("Only scheduled appointments can be cancelled")
    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancelled_at = datetime.now(UTC)
    appointment.cancelled_by_role = role
    appointment.cancellation_reason = reason.strip() if reason and reason.strip() else None
    await settle_payment_on_cancel(session, appointment)
    await session.commit()
    await session.refresh(appointment)
    return appointment


async def complete_appointment(
    session: AsyncSession, appointment_id: UUID, user_id: UUID, role: UserRole
) -> Appointment:
    appointment = await repository.get_appointment(session, appointment_id)
    if appointment is None:
        raise NotFoundError("Appointment not found")
    if appointment.status != AppointmentStatus.SCHEDULED:
        raise ConflictError("Only scheduled appointments can be completed")
    if role == UserRole.DOCTOR:
        doctor = await get_doctor_for_user(session, user_id)
        if appointment.doctor_id != doctor.id:
            raise NotFoundError("Appointment not found")
    appointment.status = AppointmentStatus.COMPLETED
    await session.commit()
    await session.refresh(appointment)
    return appointment


async def settle_payment_on_cancel(session: AsyncSession, appointment: Appointment) -> None:
    """Refund a paid on-call visit, or void its unpaid payment. Caller commits."""
    from app.modules.payments import service as payments

    if appointment.payment_status == PaymentStatus.PAID:
        await payments.refund_for_reference(session, appointment.id)
        appointment.payment_status = PaymentStatus.REFUNDED
    elif appointment.payment_status == PaymentStatus.PENDING:
        await payments.void_pending(session, appointment.id)
        appointment.payment_status = PaymentStatus.CANCELLED


async def ensure_consultation_payable(session: AsyncSession, appointment_id: UUID) -> None:
    await booking.release_unpaid_holds(session)
    appointment = await repository.get_appointment(session, appointment_id)
    if appointment is None:
        raise NotFoundError("Appointment not found")
    await session.refresh(appointment)
    if appointment.status != AppointmentStatus.SCHEDULED:
        raise ConflictError(
            "This booking was released because payment wasn't completed in time. "
            "Please book the slot again."
        )
    if appointment.payment_status != PaymentStatus.PENDING:
        raise ConflictError("This consultation is already paid")


async def mark_consultation_paid(session: AsyncSession, appointment_id: UUID) -> None:
    appointment = await repository.get_appointment(session, appointment_id)
    if appointment is not None:
        appointment.payment_status = PaymentStatus.PAID


async def cancel_consultation_for_refund(session: AsyncSession, appointment_id: UUID) -> None:
    """Used by admin refunds: cancel the visit if it hasn't happened. Caller commits."""
    appointment = await repository.get_appointment(session, appointment_id)
    if appointment is None:
        return
    if appointment.status == AppointmentStatus.SCHEDULED:
        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancelled_at = datetime.now(UTC)
        appointment.cancelled_by_role = UserRole.ADMIN
        appointment.cancellation_reason = "Refunded by the clinic"
    appointment.payment_status = PaymentStatus.REFUNDED
