from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.common.enums import Module, PaymentStatus, UserRole
from app.core.exceptions import NotFoundError
from app.modules.access.dependencies import require_module
from app.modules.auth.dependencies import require_roles
from app.modules.auth.models import User
from app.modules.payments import service
from app.modules.payments.models import Payment
from app.modules.payments.schemas import PaymentRead, PayRequest

patient = require_roles(UserRole.PATIENT)

# Customer payments at /my/payments.
my_router = APIRouter()
# All payments and refunds at /admin/payments; payments module.
admin_router = APIRouter(dependencies=[Depends(require_module(Module.PAYMENTS))])


@my_router.get("", response_model=list[PaymentRead])
async def my_payments(
    session: AsyncSession = Depends(get_db_session), user: User = Depends(patient)
) -> list[PaymentRead]:
    return await service.list_for_user(session, user.id)


@my_router.get("/{payment_id}", response_model=PaymentRead)
async def my_payment(
    payment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(patient),
) -> PaymentRead:
    payment = await session.get(Payment, payment_id)
    if payment is None or payment.user_id != user.id:
        raise NotFoundError("Payment not found")
    return payment


@my_router.post("/{payment_id}/pay", response_model=PaymentRead)
async def pay(
    payment_id: UUID,
    data: PayRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(patient),
) -> PaymentRead:
    return await service.pay(session, user, payment_id, data)


@admin_router.get("", response_model=list[PaymentRead])
async def list_payments(
    payment_status: PaymentStatus | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> list[PaymentRead]:
    return await service.list_all(session, payment_status, offset, limit)


@admin_router.get("/{payment_id}", response_model=PaymentRead)
async def get_payment(
    payment_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> PaymentRead:
    payment = await session.get(Payment, payment_id)
    if payment is None:
        raise NotFoundError("Payment not found")
    return payment


@admin_router.post("/{payment_id}/refund", response_model=PaymentRead)
async def refund(payment_id: UUID, session: AsyncSession = Depends(get_db_session)) -> PaymentRead:
    return await service.admin_refund(session, payment_id)
