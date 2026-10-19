from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import PaymentPurpose, PaymentStatus
from app.db.base import Base
from app.db.types import str_enum


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount_paise > 0", name="ck_payment_positive_amount"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    purpose: Mapped[PaymentPurpose] = mapped_column(str_enum(PaymentPurpose))
    reference_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[PaymentStatus] = mapped_column(
        str_enum(PaymentStatus), default=PaymentStatus.PENDING, index=True
    )
    method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    method_detail: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider: Mapped[str] = mapped_column(String(40), default="mock")
    provider_reference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
