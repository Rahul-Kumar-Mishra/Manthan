from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import CollectionType, LabBookingStatus
from app.db.base import Base
from app.db.types import str_enum


def _now() -> datetime:
    return datetime.now(UTC)


class LabTest(Base):
    __tablename__ = "lab_tests"
    __table_args__ = (CheckConstraint("price_paise > 0", name="ck_lab_test_positive_price"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sample_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    preparation: Mapped[str | None] = mapped_column(String(300), nullable=True)
    turnaround_hours: Mapped[int] = mapped_column(Integer, default=24)
    price_paise: Mapped[int] = mapped_column(Integer)
    home_collection: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LabBooking(Base):
    __tablename__ = "lab_bookings"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    lab_test_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lab_tests.id", ondelete="SET NULL"), nullable=True
    )
    test_name: Mapped[str] = mapped_column(String(160))
    price_paise: Mapped[int] = mapped_column(Integer)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    collection_type: Mapped[CollectionType] = mapped_column(str_enum(CollectionType))
    address: Mapped[str | None] = mapped_column(String(400), nullable=True)
    contact_phone: Mapped[str] = mapped_column(String(40))
    status: Mapped[LabBookingStatus] = mapped_column(
        str_enum(LabBookingStatus), default=LabBookingStatus.BOOKED, index=True
    )
    result_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
