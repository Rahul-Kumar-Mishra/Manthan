from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.common.enums import Module, OrderStatus, UserRole
from app.modules.access.dependencies import require_module
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.auth.models import User
from app.modules.pharmacy import service
from app.modules.pharmacy.schemas import (
    CartItemSet,
    CartRead,
    CheckoutRequest,
    MedicineAdminRead,
    MedicineCatalogRead,
    MedicineCreate,
    MedicineUpdate,
    OrderCancel,
    OrderRead,
    OrderStatusUpdate,
    RestockRequest,
    StockAdjustRequest,
    StockMovementRead,
)

customer = require_roles(UserRole.PATIENT)

# Customer catalogue at /medicines: availability only, never the stock count.
catalog_router = APIRouter(dependencies=[Depends(get_current_user)])
# Customer cart at /cart, checkout at /book/medicines, orders at /my/orders.
cart_router = APIRouter()
book_router = APIRouter()
my_orders_router = APIRouter()
# Inventory at /admin/medicines and orders at /admin/medicine-orders; pharmacy module.
admin_medicines_router = APIRouter(dependencies=[Depends(require_module(Module.PHARMACY))])
admin_orders_router = APIRouter(dependencies=[Depends(require_module(Module.PHARMACY))])


# ---------- customer ----------


@catalog_router.get("", response_model=list[MedicineCatalogRead])
async def browse_medicines(
    search: str | None = Query(default=None, max_length=80),
    category: str | None = Query(default=None, max_length=80),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> list[MedicineCatalogRead]:
    rows = await service.list_medicines(
        session,
        search=search,
        category=category,
        include_inactive=False,
        offset=offset,
        limit=limit,
    )
    return [service.to_catalog(m) for m in rows]


@catalog_router.get("/{medicine_id}", response_model=MedicineCatalogRead)
async def get_catalog_medicine(
    medicine_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> MedicineCatalogRead:
    medicine = await service.get_medicine(session, medicine_id)
    if not medicine.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found")
    return service.to_catalog(medicine)


@cart_router.get("", response_model=CartRead)
async def get_cart(
    session: AsyncSession = Depends(get_db_session), user: User = Depends(customer)
) -> CartRead:
    return await service.get_cart(session, user.id)


@cart_router.put("/items/{medicine_id}", response_model=CartRead)
async def set_cart_item(
    medicine_id: UUID,
    data: CartItemSet,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(customer),
) -> CartRead:
    return await service.set_cart_item(session, user.id, medicine_id, data.quantity)


@cart_router.delete("/items/{medicine_id}", response_model=CartRead)
async def remove_cart_item(
    medicine_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(customer),
) -> CartRead:
    return await service.remove_cart_item(session, user.id, medicine_id)


@book_router.post("/medicines", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def book_medicines(
    data: CheckoutRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(customer),
) -> OrderRead:
    """Check out the cart: reserves the stock and returns the order with its payment."""
    return await service.checkout(session, user, data)


@my_orders_router.get("", response_model=list[OrderRead])
async def my_orders(
    session: AsyncSession = Depends(get_db_session), user: User = Depends(customer)
) -> list[OrderRead]:
    return await service.list_orders(session, user.id)


@my_orders_router.get("/{order_id}", response_model=OrderRead)
async def my_order(
    order_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(customer),
) -> OrderRead:
    order = await service.get_order(session, order_id)
    if order.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@my_orders_router.post("/{order_id}/cancel", response_model=OrderRead)
async def cancel_my_order(
    order_id: UUID,
    data: OrderCancel | None = None,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(customer),
) -> OrderRead:
    reason = (data.reason or "").strip() if data else ""
    return await service.cancel_by_customer(session, order_id, user, reason or None)


# ---------- admin: inventory ----------


@admin_medicines_router.get("", response_model=list[MedicineAdminRead])
async def list_inventory(
    search: str | None = Query(default=None, max_length=80),
    category: str | None = Query(default=None, max_length=80),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> list[MedicineAdminRead]:
    rows = await service.list_medicines(
        session,
        search=search,
        category=category,
        include_inactive=True,
        offset=offset,
        limit=limit,
    )
    return [service.to_admin(m) for m in rows]


@admin_medicines_router.post(
    "", response_model=MedicineAdminRead, status_code=status.HTTP_201_CREATED
)
async def create_medicine(
    data: MedicineCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> MedicineAdminRead:
    return service.to_admin(await service.create_medicine(session, data, user))


@admin_medicines_router.get("/{medicine_id}", response_model=MedicineAdminRead)
async def get_inventory_item(
    medicine_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> MedicineAdminRead:
    return service.to_admin(await service.get_medicine(session, medicine_id))


@admin_medicines_router.patch("/{medicine_id}", response_model=MedicineAdminRead)
async def update_medicine(
    medicine_id: UUID, data: MedicineUpdate, session: AsyncSession = Depends(get_db_session)
) -> MedicineAdminRead:
    return service.to_admin(await service.update_medicine(session, medicine_id, data))


@admin_medicines_router.delete("/{medicine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medicine(
    medicine_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> Response:
    await service.delete_medicine(session, medicine_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_medicines_router.post("/{medicine_id}/restock", response_model=MedicineAdminRead)
async def restock(
    medicine_id: UUID,
    data: RestockRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> MedicineAdminRead:
    return service.to_admin(await service.restock(session, medicine_id, data, user))


@admin_medicines_router.post("/{medicine_id}/adjust", response_model=MedicineAdminRead)
async def adjust_stock(
    medicine_id: UUID,
    data: StockAdjustRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> MedicineAdminRead:
    return service.to_admin(await service.adjust(session, medicine_id, data, user))


@admin_medicines_router.get("/{medicine_id}/movements", response_model=list[StockMovementRead])
async def stock_movements(
    medicine_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> list[StockMovementRead]:
    return await service.list_movements(session, medicine_id)


# ---------- admin: orders ----------


@admin_orders_router.get("", response_model=list[OrderRead])
async def all_orders(
    order_status: OrderStatus | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db_session),
) -> list[OrderRead]:
    return await service.list_orders(session, None, order_status)


@admin_orders_router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: UUID, session: AsyncSession = Depends(get_db_session)) -> OrderRead:
    return await service.get_order(session, order_id)


@admin_orders_router.post("/{order_id}/cancel", response_model=OrderRead)
async def admin_cancel_order(
    order_id: UUID,
    data: OrderCancel | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> OrderRead:
    reason = (data.reason or "").strip() if data else ""
    if len(reason) < 3:
        raise HTTPException(status_code=422, detail="Give the customer a reason for cancelling")
    return await service.cancel_by_admin(session, order_id, reason)


@admin_orders_router.post("/{order_id}/status", response_model=OrderRead)
async def advance_order(
    order_id: UUID, data: OrderStatusUpdate, session: AsyncSession = Depends(get_db_session)
) -> OrderRead:
    return await service.advance_status(session, order_id, OrderStatus(data.status))
