from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import Module
from app.db.base import Base


class ModuleGrant(Base):
    """One staff account's access to one module, and who handed it to them.

    `granted_by` forms the delegation tree: the MD sits at the root (implicitly
    holding every module) and anyone holding a module can pass it on.
    """

    __tablename__ = "module_grants"
    __table_args__ = (UniqueConstraint("user_id", "module", name="uq_module_grant_user_module"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    module: Mapped[Module] = mapped_column(
        Enum(Module, values_callable=lambda ms: [m.value for m in ms], native_enum=False),
        index=True,
    )
    granted_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
