from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common.enums import OrderStatus, StockMovementReason

MAX_CART_QUANTITY = 20


class MedicineFields(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    generic_name: str | None = Field(default=None, max_length=160)
    manufacturer: str | None = Field(default=None, max_length=160)
    form: str = Field(min_length=2, max_length=40, description="tablet, capsule, syrup, ...")
    strength: str | None = Field(default=None, max_length=60)
    pack_size: str | None = Field(default=None, max_length=60)
    category: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    price_paise: int = Field(gt=0, le=10_000_000)
    requires_prescription: bool = False


class MedicineCreate(MedicineFields):
    stock_quantity: int = Field(default=0, ge=0, le=1_000_000)
    reorder_level: int = Field(default=10, ge=0, le=100_000)


class MedicineUpdate(BaseModel):
    """Catalogue edits. Stock only changes through restock/adjust so it stays audited."""

    name: str | None = Field(default=None, min_length=2, max_length=160)
    generic_name: str | None = Field(default=None, max_length=160)
    manufacturer: str | None = Field(default=None, max_length=160)
    form: str | None = Field(default=None, min_length=2, max_length=40)
    strength: str | None = Field(default=None, max_length=60)
    pack_size: str | None = Field(default=None, max_length=60)
    category: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    price_paise: int | None = Field(default=None, gt=0, le=10_000_000)
    requires_prescription: bool | None = None
    reorder_level: int | None = Field(default=None, ge=0, le=100_000)
    is_active: bool | None = None


class MedicineCatalogRead(BaseModel):
    """What patients see: availability only, never the stock count."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    generic_name: str | None
    manufacturer: str | None
    form: str
    strength: str | None
    pack_size: str | None
    category: str | None
    description: str | None
    price_paise: int
    requires_prescription: bool
    in_stock: bool


class MedicineAdminRead(MedicineCatalogRead):
    stock_quantity: int
    reorder_level: int
    low_stock: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RestockRequest(BaseModel):
    quantity: int = Field(gt=0, le=1_000_000)
    batch_number: str | None = Field(default=None, max_length=60)
    expiry_date: date | None = None
    note: str | None = Field(default=None, max_length=300)


class StockAdjustRequest(BaseModel):
    change: int = Field(ge=-1_000_000, le=1_000_000)
    reason: Literal["adjustment", "expired"] = "adjustment"
    note: str = Field(min_length=3, max_length=300)

    @field_validator("change")
    @classmethod
    def non_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("Adjustment cannot be zero")
        return value


class StockMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    medicine_id: UUID
    change: int
    quantity_after: int
    reason: StockMovementReason
    batch_number: str | None
    expiry_date: str | None
    note: str | None
    order_id: UUID | None
    performed_by: UUID | None
    created_at: datetime


class CartItemSet(BaseModel):
    quantity: int = Field(ge=1, le=MAX_CART_QUANTITY)


class CartLine(BaseModel):
    medicine: MedicineCatalogRead
    quantity: int
    line_total_paise: int
    available: bool


class CartRead(BaseModel):
    items: list[CartLine]
    total_paise: int
    all_available: bool


class CheckoutRequest(BaseModel):
    delivery_address: str = Field(min_length=10, max_length=400)
    contact_phone: str = Field(min_length=6, max_length=40)


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    medicine_id: UUID | None
    medicine_name: str
    unit_price_paise: int
    quantity: int


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    status: OrderStatus
    total_paise: int
    delivery_address: str
    contact_phone: str
    payment_id: UUID | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]


class OrderStatusUpdate(BaseModel):
    status: Literal["packed", "dispatched", "delivered"]


class OrderCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=300)
