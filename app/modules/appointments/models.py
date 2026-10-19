from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import AppointmentMode, AppointmentStatus, PaymentStatus, UserRole
from app.db.base import Base
from app.db.types import str_enum


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_appointment_positive_duration"),
        Index(
            "uq_appointment_doctor_start",
            "doctor_id",
            "starts_at",
            unique=True,
            sqlite_where=text("status = 'scheduled'"),
            postgresql_where=text("status = 'scheduled'"),
        ),
        ExcludeConstraint(
            ("doctor_id", "="),
            (text("tstzrange(starts_at, ends_at, '[)')"), "&&"),
            using="gist",
            name="ex_appointment_doctor_no_overlap",
            ops={"doctor_id": "gist_uuid_ops"},
            where=text("status = 'scheduled'"),
        ).ddl_if(dialect="postgresql"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    doctor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(
            AppointmentStatus,
            values_callable=lambda statuses: [status.value for status in statuses],
            native_enum=False,
        ),
        default=AppointmentStatus.SCHEDULED,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_role: Mapped[UserRole | None] = mapped_column(
        Enum(
            UserRole,
            values_callable=lambda roles: [role.value for role in roles],
            native_enum=False,
            create_constraint=False,
        ),
        nullable=True,
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mode: Mapped[AppointmentMode] = mapped_column(
        str_enum(AppointmentMode), default=AppointmentMode.IN_PERSON
    )
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fee_paise: Mapped[int | None] = mapped_column(nullable=True)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        str_enum(PaymentStatus), default=PaymentStatus.NOT_REQUIRED
    )
    payment_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
