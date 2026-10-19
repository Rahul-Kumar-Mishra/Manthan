from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import Module, PaymentPurpose, PaymentStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.access.service import has_module
from app.modules.auth.models import User
from app.modules.payments.models import Payment
from app.modules.payments.provider import get_provider
from app.modules.payments.schemas import PayRequest


async def create_payment(
    session: AsyncSession,
    user_id: UUID,
    purpose: PaymentPurpose,
    reference_id: UUID,
    amount_paise: int,
) -> Payment:
    """Add a pending payment to the session; the caller commits with its own changes."""
    payment = Payment(
        user_id=user_id,
        purpose=purpose,
        reference_id=reference_id,
        amount_paise=amount_paise,
        provider=get_provider().name,
    )
    session.add(payment)
    await session.flush()
    return payment


async def get_for_user(session: AsyncSession, payment_id: UUID, user: User) -> Payment:
    payment = await session.get(Payment, payment_id)
    if payment is None:
        raise NotFoundError("Payment not found")
    if payment.user_id != user.id and not await has_module(session, user, Module.PAYMENTS):
        raise NotFoundError("Payment not found")
    return payment


async def _check_payable(session: AsyncSession, payment: Payment) -> None:
    # Imported here: those modules create payments, so importing them at module
    # load would be circular.
    if payment.purpose == PaymentPurpose.MEDICINE_ORDER:
        from app.modules.pharmacy.service import ensure_order_payable

        await ensure_order_payable(session, payment.reference_id)
    else:
        from app.modules.appointments.service import ensure_consultation_payable

        await ensure_consultation_payable(session, payment.reference_id)


async def _on_paid(session: AsyncSession, payment: Payment) -> None:
    if payment.purpose == PaymentPurpose.MEDICINE_ORDER:
        from app.modules.pharmacy.service import mark_order_paid

        await mark_order_paid(session, payment.reference_id)
    else:
        from app.modules.appointments.service import mark_consultation_paid

        await mark_consultation_paid(session, payment.reference_id)


async def pay(session: AsyncSession, user: User, payment_id: UUID, request: PayRequest) -> Payment:
    payment = await session.get(Payment, payment_id)
    if payment is None or payment.user_id != user.id:
        raise NotFoundError("Payment not found")
    if payment.status == PaymentStatus.PAID:
        raise ConflictError("This payment has already been completed")
    if payment.status not in (PaymentStatus.PENDING, PaymentStatus.FAILED):
        raise ConflictError("This payment can no longer be made")
    await _check_payable(session, payment)

    result = await get_provider().charge(payment.amount_paise, request)
    payment.method = request.method
    payment.method_detail = result.method_detail
    payment.provider_reference = result.reference
    if result.success:
        payment.status = PaymentStatus.PAID
        payment.paid_at = datetime.now(UTC)
        payment.failure_reason = None
        await _on_paid(session, payment)
    else:
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = result.failure_reason
    await session.commit()
    await session.refresh(payment)
    return payment


async def refund_for_reference(session: AsyncSession, reference_id: UUID) -> Payment | None:
    """Refund the paid payment behind an order/appointment, if any. Caller commits."""
    payment = await session.scalar(
        select(Payment).where(
            Payment.reference_id == reference_id, Payment.status == PaymentStatus.PAID
        )
    )
    if payment is None:
        return None
    payment.provider_reference = await get_provider().refund(
        payment.provider_reference or "", payment.amount_paise
    )
    payment.status = PaymentStatus.REFUNDED
    payment.refunded_at = datetime.now(UTC)
    return payment


async def void_pending(session: AsyncSession, reference_id: UUID) -> None:
    """Stop an unpaid payment from being completed later. Caller commits."""
    pending = await session.scalars(
        select(Payment).where(
            Payment.reference_id == reference_id,
            Payment.status.in_((PaymentStatus.PENDING, PaymentStatus.FAILED)),
        )
    )
    for payment in pending:
        payment.status = PaymentStatus.CANCELLED
        payment.failure_reason = "Cancelled before payment"


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[Payment]:
    result = await session.scalars(
        select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc())
    )
    return list(result)


async def list_all(
    session: AsyncSession, status_filter: PaymentStatus | None, offset: int, limit: int
) -> list[Payment]:
    statement = select(Payment).order_by(Payment.created_at.desc())
    if status_filter is not None:
        statement = statement.where(Payment.status == status_filter)
    return list(await session.scalars(statement.offset(offset).limit(limit)))


async def admin_refund(session: AsyncSession, payment_id: UUID) -> Payment:
    payment = await session.get(Payment, payment_id)
    if payment is None:
        raise NotFoundError("Payment not found")
    if payment.status != PaymentStatus.PAID:
        raise ConflictError("Only completed payments can be refunded")
    # Refunding cancels what was paid for, so stock and slots are released too.
    if payment.purpose == PaymentPurpose.MEDICINE_ORDER:
        from app.modules.pharmacy.service import cancel_order_for_refund

        await cancel_order_for_refund(session, payment.reference_id)
    else:
        from app.modules.appointments.service import cancel_consultation_for_refund

        await cancel_consultation_for_refund(session, payment.reference_id)
    await refund_for_reference(session, payment.reference_id)
    await session.commit()
    await session.refresh(payment)
    return payment
