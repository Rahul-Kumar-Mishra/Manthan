from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.common.enums import AppointmentMode, AppointmentStatus, PaymentStatus, UserRole


class AppointmentCreate(BaseModel):
    doctor_id: UUID
    starts_at: datetime
    ends_at: datetime
    mode: AppointmentMode = AppointmentMode.IN_PERSON
    contact_phone: str | None = Field(default=None, min_length=6, max_length=40)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Appointment timestamps must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_interval(self) -> "AppointmentCreate":
        now = datetime.now(UTC)
        if self.starts_at <= now:
            raise ValueError("Appointment must start in the future")
        if self.ends_at <= self.starts_at:
            raise ValueError("Appointment end must be after its start")
        if (self.ends_at - self.starts_at).total_seconds() > 4 * 60 * 60:
            raise ValueError("Appointment duration cannot exceed four hours")
        return self


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    doctor_id: UUID
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    created_at: datetime
    cancelled_at: datetime | None = None
    cancelled_by_role: UserRole | None = None
    cancellation_reason: str | None = None
    mode: AppointmentMode = AppointmentMode.IN_PERSON
    contact_phone: str | None = None
    fee_paise: int | None = None
    payment_status: PaymentStatus = PaymentStatus.NOT_REQUIRED
    payment_id: UUID | None = None


class AppointmentAvailability(BaseModel):
    doctor_id: UUID
    starts_at: datetime
    ends_at: datetime
    available: bool
    reason: str | None = None


class AppointmentCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus = Field(default=AppointmentStatus.COMPLETED)

    @field_validator("status")
    @classmethod
    def only_complete(cls, value: AppointmentStatus) -> AppointmentStatus:
        if value != AppointmentStatus.COMPLETED:
            raise ValueError("Administrators can only mark appointments completed")
        return value
