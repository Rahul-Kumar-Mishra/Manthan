from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("hospital_id", "name", name="uq_branch_hospital_name"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    hospital_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
