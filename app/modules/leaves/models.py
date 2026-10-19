from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import LeaveStatus
from app.db.base import Base


class DoctorLeave(Base):
    __tablename__ = "doctor_leaves"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_doctor_leave_positive_duration"),
        Index("ix_doctor_leaves_doctor_window", "doctor_id", "starts_at", "ends_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    doctor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[LeaveStatus] = mapped_column(
        Enum(
            LeaveStatus,
            values_callable=lambda statuses: [status.value for status in statuses],
            native_enum=False,
        ),
        default=LeaveStatus.PENDING,
        index=True,
    )
    requested_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
