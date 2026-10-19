from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import UserRole
from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'doctor', 'patient')", name="ck_user_role"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            values_callable=lambda roles: [role.value for role in roles],
            native_enum=False,
        )
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # The managing director is the root of the access hierarchy and holds every module.
    is_md: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
