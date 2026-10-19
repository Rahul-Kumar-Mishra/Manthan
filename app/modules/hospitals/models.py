from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Hospital(Base):
    __tablename__ = "hospitals"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
