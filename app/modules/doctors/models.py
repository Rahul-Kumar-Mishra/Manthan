from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    branch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), index=True
    )
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    specialization: Mapped[str] = mapped_column(String(120), index=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qualifications: Mapped[str | None] = mapped_column(String(300), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    languages: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    consultation_fee_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    online_fee_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_online: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
