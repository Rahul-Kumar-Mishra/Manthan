from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.enums import OrderStatus, StockMovementReason
from app.db.base import Base
from app.db.types import str_enum


def _now() -> datetime:
    return datetime.now(UTC)


class Medicine(Base):
    __tablename__ = "medicines"
    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_medicine_stock_non_negative"),
        CheckConstraint("price_paise > 0", name="ck_medicine_positive_price"),
        UniqueConstraint("name", "strength", "form", name="uq_medicine_name_strength_form"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), index=True)
    generic_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(160), nullable=True)
    form: Mapped[str] = mapped_column(String(40))
    strength: Mapped[str | None] = mapped_column(String(60), nullable=True)
    pack_size: Mapped[str | None] = mapped_column(String(60), nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    price_paise: Mapped[int] = mapped_column(Integer)
    requires_prescription: Mapped[bool] = mapped_column(Boolean, default=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class StockMovement(Base):
    """Audit trail for every change to a medicine's stock count."""

    __tablename__ = "stock_movements"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    medicine_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("medicines.id", ondelete="CASCADE"), index=True
    )
    change: Mapped[int] = mapped_column(Integer)
    quantity_after: Mapped[int] = mapped_column(Integer)
    reason: Mapped[StockMovementReason] = mapped_column(str_enum(StockMovementReason))
    batch_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    expiry_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    order_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    performed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("user_id", "medicine_id", name="uq_cart_user_medicine"),
        CheckConstraint("quantity > 0", name="ck_cart_positive_quantity"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    medicine_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("medicines.id", ondelete="CASCADE")
    )
    quantity: Mapped[int] = mapped_column(Integer)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MedicineOrder(Base):
    __tablename__ = "medicine_orders"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        str_enum(OrderStatus), default=OrderStatus.PENDING_PAYMENT, index=True
    )
    total_paise: Mapped[int] = mapped_column(Integer)
    delivery_address: Mapped[str] = mapped_column(String(400))
    contact_phone: Mapped[str] = mapped_column(String(40))
    payment_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", lazy="selectin", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "medicine_order_items"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("medicine_orders.id", ondelete="CASCADE"), index=True
    )
    medicine_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("medicines.id", ondelete="SET NULL"), nullable=True
    )
    # Name and price are copied at checkout so later catalogue edits don't rewrite history.
    medicine_name: Mapped[str] = mapped_column(String(240))
    unit_price_paise: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)

    order: Mapped[MedicineOrder] = relationship(back_populates="items")
