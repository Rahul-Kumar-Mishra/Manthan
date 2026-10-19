from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import StaffStatus
from app.db.base import Base
from app.db.types import str_enum


def _now() -> datetime:
    return datetime.now(UTC)


class StaffMember(Base):
    """Directory entry for anyone working at the hospital, with or without a sign-in."""

    __tablename__ = "staff_members"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    designation: Mapped[str] = mapped_column(String(120))
    department: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    branch_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    email: Mapped[str | None] = mapped_column(String(254), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    employment_type: Mapped[str] = mapped_column(String(20), default="full_time")
    joined_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    left_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[StaffStatus] = mapped_column(
        str_enum(StaffStatus), default=StaffStatus.ACTIVE, index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
