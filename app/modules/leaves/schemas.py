from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.common.enums import LeaveStatus

MAX_LEAVE_DAYS = 120


class LeaveScope(StrEnum):
    CURRENT = "current"
    UPCOMING = "upcoming"
    PAST = "past"


class LeaveCreate(BaseModel):
    doctor_id: UUID | None = Field(
        default=None, description="Required for administrators; ignored for doctors."
    )
    starts_at: datetime
    ends_at: datetime
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Leave timestamps must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_interval(self) -> "LeaveCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("Leave end must be after its start")
        if self.ends_at <= datetime.now(UTC):
            raise ValueError("Leave must end in the future")
        if self.ends_at - self.starts_at > timedelta(days=MAX_LEAVE_DAYS):
            raise ValueError(f"Leave cannot exceed {MAX_LEAVE_DAYS} days")
        return self


class LeaveReview(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class LeaveAppointmentsCancel(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class LeaveRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    doctor_id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: str
    status: LeaveStatus
    requested_by: UUID | None
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime


class LeaveWindow(BaseModel):
    """Approved leave as shown to anyone booking: dates only, no reason."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    doctor_id: UUID
    starts_at: datetime
    ends_at: datetime
