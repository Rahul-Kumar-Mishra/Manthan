from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import OrderStatus, PaymentPurpose, StockMovementReason
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.auth.models import User
from app.modules.payments import service as payments
from app.modules.pharmacy.models import CartItem, Medicine, MedicineOrder, OrderItem, StockMovement
from app.modules.pharmacy.schemas import (
    CartLine,
    CartRead,
    CheckoutRequest,
    MedicineAdminRead,
    MedicineCatalogRead,
    MedicineCreate,
    MedicineUpdate,
    RestockRequest,
    StockAdjustRequest,
)

# Stock is reserved at checkout; an order left unpaid this long is released.
PAYMENT_WINDOW = timedelta(minutes=30)
NOT_ENOUGH_STOCK = "{name} doesn't have enough stock for that quantity. Try fewer."

# Admin may move a paid order forward one step at a time.
NEXT_STATUS = {
    OrderStatus.PAID: OrderStatus.PACKED,
    OrderStatus.PACKED: OrderStatus.DISPATCHED,
    OrderStatus.DISPATCHED: OrderStatus.DELIVERED,
}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def in_stock(medicine: Medicine) -> bool:
    return medicine.is_active and medicine.stock_quantity > 0


def to_catalog(medicine: Medicine) -> MedicineCatalogRead:
    return MedicineCatalogRead.model_validate(
        {**_columns(medicine), "in_stock": in_stock(medicine)}
    )


def to_admin(medicine: Medicine) -> MedicineAdminRead:
    return MedicineAdminRead.model_validate(
        {
            **_columns(medicine),
            "in_stock": in_stock(medicine),
            "low_stock": medicine.stock_quantity <= medicine.reorder_level,
        }
    )


def _columns(medicine: Medicine) -> dict:
    return {c.key: getattr(medicine, c.key) for c in Medicine.__table__.columns}


# ---------- catalogue & inventory ----------


async def list_medicines(
    session: AsyncSession,
    *,
    search: str | None,
    category: str | None,
    include_inactive: bool,
    offset: int,
    limit: int,
) -> list[Medicine]:
    statement = select(Medicine).order_by(Medicine.name)
    if not include_inactive:
        statement = statement.where(Medicine.is_active.is_(True))
    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            or_(Medicine.name.ilike(pattern), Medicine.generic_name.ilike(pattern))
        )
    if category:
        statement = statement.where(Medicine.category == category)
    return list(await session.scalars(statement.offset(offset).limit(limit)))


async def get_medicine(session: AsyncSession, medicine_id: UUID) -> Medicine:
    medicine = await session.get(Medicine, medicine_id)
    if medicine is None:
        raise NotFoundError("Medicine not found")
    return medicine


async def create_medicine(session: AsyncSession, data: MedicineCreate, user: User) -> Medicine:
    medicine = Medicine(**data.model_dump())
    session.add(medicine)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("A medicine with that name, strength and form already exists") from exc
    if medicine.stock_quantity:
        session.add(
            StockMovement(
                medicine_id=medicine.id,
                change=medicine.stock_quantity,
                quantity_after=medicine.stock_quantity,
                reason=StockMovementReason.RESTOCK,
                note="Opening stock",
                performed_by=user.id,
            )
        )
    await session.commit()
    await session.refresh(medicine)
    return medicine


async def update_medicine(
    session: AsyncSession, medicine_id: UUID, data: MedicineUpdate
) -> Medicine:
    medicine = await get_medicine(session, medicine_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(medicine, field, value)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("A medicine with that name, strength and form already exists") from exc
    await session.refresh(medicine)
    return medicine


async def delete_medicine(session: AsyncSession, medicine_id: UUID) -> None:
    medicine = await get_medicine(session, medicine_id)
    await session.delete(medicine)
    await session.commit()


async def _move_stock(
    session: AsyncSession,
    medicine: Medicine,
    change: int,
    reason: StockMovementReason,
    *,
    user_id: UUID | None = None,
    order_id: UUID | None = None,
    note: str | None = None,
    batch_number: str | None = None,
    expiry_date: str | None = None,
) -> None:
    if medicine.stock_quantity + change < 0:
        raise ConflictError("Stock cannot go below zero")
    medicine.stock_quantity += change
    session.add(
        StockMovement(
            medicine_id=medicine.id,
            change=change,
            quantity_after=medicine.stock_quantity,
            reason=reason,
            note=note,
            order_id=order_id,
            performed_by=user_id,
            batch_number=batch_number,
            expiry_date=expiry_date,
        )
    )


async def _locked(session: AsyncSession, medicine_id: UUID) -> Medicine | None:
    return await session.scalar(
        select(Medicine).where(Medicine.id == medicine_id).with_for_update()
    )


async def restock(
    session: AsyncSession, medicine_id: UUID, data: RestockRequest, user: User
) -> Medicine:
    medicine = await _locked(session, medicine_id)
    if medicine is None:
        raise NotFoundError("Medicine not found")
    await _move_stock(
        session,
        medicine,
        data.quantity,
        StockMovementReason.RESTOCK,
        user_id=user.id,
        note=data.note,
        batch_number=data.batch_number,
        expiry_date=data.expiry_date.isoformat() if data.expiry_date else None,
    )
    await session.commit()
    await session.refresh(medicine)
    return medicine


async def adjust(
    session: AsyncSession, medicine_id: UUID, data: StockAdjustRequest, user: User
) -> Medicine:
    medicine = await _locked(session, medicine_id)
    if medicine is None:
        raise NotFoundError("Medicine not found")
    await _move_stock(
        session,
        medicine,
        data.change,
        StockMovementReason(data.reason),
        user_id=user.id,
        note=data.note,
    )
    await session.commit()
    await session.refresh(medicine)
    return medicine


async def list_movements(session: AsyncSession, medicine_id: UUID) -> list[StockMovement]:
    await get_medicine(session, medicine_id)
    result = await session.scalars(
        select(StockMovement)
        .where(StockMovement.medicine_id == medicine_id)
        .order_by(StockMovement.created_at.desc())
        .limit(200)
    )
    return list(result)


# ---------- cart ----------


async def get_cart(session: AsyncSession, user_id: UUID) -> CartRead:
    rows = (
        await session.execute(
            select(CartItem, Medicine)
            .join(Medicine, Medicine.id == CartItem.medicine_id)
            .where(CartItem.user_id == user_id)
            .order_by(CartItem.added_at)
        )
    ).all()
    lines = [
        CartLine(
            medicine=to_catalog(medicine),
            quantity=item.quantity,
            line_total_paise=item.quantity * medicine.price_paise,
            # Checked here so a cart that went stale since it was filled shows it.
            available=in_stock(medicine) and medicine.stock_quantity >= item.quantity,
        )
        for item, medicine in rows
    ]
    return CartRead(
        items=lines,
        total_paise=sum(line.line_total_paise for line in lines),
        all_available=all(line.available for line in lines),
    )


async def set_cart_item(
    session: AsyncSession, user_id: UUID, medicine_id: UUID, quantity: int
) -> CartRead:
    medicine = await get_medicine(session, medicine_id)
    if not in_stock(medicine):
        raise ConflictError(f"{medicine.name} is out of stock")
    if quantity > medicine.stock_quantity:
        raise ConflictError(NOT_ENOUGH_STOCK.format(name=medicine.name))
    item = await session.scalar(
        select(CartItem).where(CartItem.user_id == user_id, CartItem.medicine_id == medicine_id)
    )
    if item is None:
        session.add(CartItem(user_id=user_id, medicine_id=medicine_id, quantity=quantity))
    else:
        item.quantity = quantity
    await session.commit()
    return await get_cart(session, user_id)


async def remove_cart_item(session: AsyncSession, user_id: UUID, medicine_id: UUID) -> CartRead:
    item = await session.scalar(
        select(CartItem).where(CartItem.user_id == user_id, CartItem.medicine_id == medicine_id)
    )
    if item is not None:
        await session.delete(item)
        await session.commit()
    return await get_cart(session, user_id)


# ---------- orders ----------


async def _release(session: AsyncSession, order: MedicineOrder, reason: str) -> None:
    """Cancel an order: return its stock and stop or refund its payment. Caller commits."""
    for item in order.items:
        if item.medicine_id is None:
            continue
        medicine = await _locked(session, item.medicine_id)
        if medicine is not None:
            await _move_stock(
                session,
                medicine,
                item.quantity,
                StockMovementReason.ORDER_CANCELLED,
                order_id=order.id,
            )
    if order.status == OrderStatus.PENDING_PAYMENT:
        await payments.void_pending(session, order.id)
    else:
        await payments.refund_for_reference(session, order.id)
    order.status = OrderStatus.CANCELLED
    order.cancellation_reason = reason


async def expire_unpaid_orders(session: AsyncSession) -> int:
    cutoff = datetime.now(UTC) - PAYMENT_WINDOW
    stale = list(
        await session.scalars(
            select(MedicineOrder).where(
                MedicineOrder.status == OrderStatus.PENDING_PAYMENT,
                MedicineOrder.created_at < cutoff,
            )
        )
    )
    for order in stale:
        await _release(session, order, "Payment was not completed in time")
    if stale:
        await session.commit()
    return len(stale)


async def checkout(session: AsyncSession, user: User, data: CheckoutRequest) -> MedicineOrder:
    await expire_unpaid_orders(session)
    cart = list(await session.scalars(select(CartItem).where(CartItem.user_id == user.id)))
    if not cart:
        raise ConflictError("Your cart is empty")

    order = MedicineOrder(
        user_id=user.id,
        total_paise=0,
        delivery_address=data.delivery_address.strip(),
        contact_phone=data.contact_phone.strip(),
    )
    session.add(order)
    await session.flush()
    total = 0
    # Lock in a stable order so concurrent checkouts can't deadlock on each other.
    for item in sorted(cart, key=lambda i: str(i.medicine_id)):
        medicine = await _locked(session, item.medicine_id)
        if medicine is None or not in_stock(medicine):
            await session.rollback()
            name = medicine.name if medicine else "An item"
            raise ConflictError(f"{name} is out of stock. Remove it from your cart to continue.")
        if item.quantity > medicine.stock_quantity:
            await session.rollback()
            raise ConflictError(NOT_ENOUGH_STOCK.format(name=medicine.name))
        await _move_stock(
            session, medicine, -item.quantity, StockMovementReason.SALE, order_id=order.id
        )
        label = " ".join(filter(None, [medicine.name, medicine.strength, medicine.form]))
        session.add(
            OrderItem(
                order_id=order.id,
                medicine_id=medicine.id,
                medicine_name=label,
                unit_price_paise=medicine.price_paise,
                quantity=item.quantity,
            )
        )
        total += medicine.price_paise * item.quantity
        await session.delete(item)

    order.total_paise = total
    payment = await payments.create_payment(
        session, user.id, PaymentPurpose.MEDICINE_ORDER, order.id, total
    )
    order.payment_id = payment.id
    await session.commit()
    return await get_order(session, order.id)


async def get_order(session: AsyncSession, order_id: UUID) -> MedicineOrder:
    order = await session.scalar(
        select(MedicineOrder)
        .where(MedicineOrder.id == order_id)
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise NotFoundError("Order not found")
    return order


async def list_orders(
    session: AsyncSession, user_id: UUID | None, status: OrderStatus | None = None
) -> list[MedicineOrder]:
    await expire_unpaid_orders(session)
    statement = select(MedicineOrder).order_by(MedicineOrder.created_at.desc())
    if user_id is not None:
        statement = statement.where(MedicineOrder.user_id == user_id)
    if status is not None:
        statement = statement.where(MedicineOrder.status == status)
    return list(await session.scalars(statement.limit(500)))


async def ensure_order_payable(session: AsyncSession, order_id: UUID) -> None:
    await expire_unpaid_orders(session)
    order = await get_order(session, order_id)
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise ConflictError(
            "This order expired before payment. Your cart items were released; please order again."
            if order.status == OrderStatus.CANCELLED
            else "This order is already paid"
        )
    if datetime.now(UTC) - _aware(order.created_at) > PAYMENT_WINDOW:
        raise ConflictError("This order expired before payment")


async def mark_order_paid(session: AsyncSession, order_id: UUID) -> None:
    order = await get_order(session, order_id)
    order.status = OrderStatus.PAID


async def cancel_by_customer(
    session: AsyncSession, order_id: UUID, user: User, reason: str | None
) -> MedicineOrder:
    order = await get_order(session, order_id)
    if order.user_id != user.id:
        raise NotFoundError("Order not found")
    if order.status not in (OrderStatus.PENDING_PAYMENT, OrderStatus.PAID):
        raise ConflictError("This order is already being packed and can no longer be cancelled")
    await _release(session, order, reason or "Cancelled by customer")
    await session.commit()
    return await get_order(session, order.id)


async def cancel_by_admin(session: AsyncSession, order_id: UUID, reason: str) -> MedicineOrder:
    order = await get_order(session, order_id)
    if order.status in (OrderStatus.DISPATCHED, OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        raise ConflictError("Dispatched, delivered or cancelled orders cannot be cancelled")
    await _release(session, order, reason)
    await session.commit()
    return await get_order(session, order.id)


async def cancel_order_for_refund(session: AsyncSession, order_id: UUID) -> None:
    """Used by payment refunds. Undelivered stock goes back on the shelf. Caller commits."""
    order = await get_order(session, order_id)
    if order.status in (OrderStatus.PAID, OrderStatus.PACKED):
        for item in order.items:
            medicine = await _locked(session, item.medicine_id) if item.medicine_id else None
            if medicine is not None:
                await _move_stock(
                    session,
                    medicine,
                    item.quantity,
                    StockMovementReason.ORDER_CANCELLED,
                    order_id=order.id,
                )
    if order.status != OrderStatus.CANCELLED:
        order.status = OrderStatus.CANCELLED
        order.cancellation_reason = "Refunded"


async def advance_status(
    session: AsyncSession, order_id: UUID, target: OrderStatus
) -> MedicineOrder:
    order = await get_order(session, order_id)
    if NEXT_STATUS.get(order.status) != target:
        raise ConflictError(f"An order that is {order.status.value} cannot move to {target.value}")
    order.status = target
    await session.commit()
    return await get_order(session, order.id)
