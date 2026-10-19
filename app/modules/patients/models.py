from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    date_of_birth: Mapped[date] = mapped_column(Date)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
