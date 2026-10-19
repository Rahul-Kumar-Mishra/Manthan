from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common.enums import CollectionType, LabBookingStatus


class LabTestCreate(BaseModel):
    code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=160)
    category: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    sample_type: str | None = Field(default=None, max_length=60)
    preparation: str | None = Field(default=None, max_length=300)
    turnaround_hours: int = Field(default=24, ge=1, le=24 * 30)
    price_paise: int = Field(gt=0, le=10_000_000)
    home_collection: bool = False


class LabTestUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    category: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    sample_type: str | None = Field(default=None, max_length=60)
    preparation: str | None = Field(default=None, max_length=300)
    turnaround_hours: int | None = Field(default=None, ge=1, le=24 * 30)
    price_paise: int | None = Field(default=None, gt=0, le=10_000_000)
    home_collection: bool | None = None
    is_active: bool | None = None


class LabTestRead(LabTestCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime


class LabBookingCreate(BaseModel):
    lab_test_id: UUID
    scheduled_at: datetime
    collection_type: CollectionType = CollectionType.LAB_VISIT
    address: str | None = Field(default=None, max_length=400)
    contact_phone: str = Field(min_length=6, max_length=40)

    @field_validator("scheduled_at")
    @classmethod
    def future_and_soon(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduled_at must include a timezone")
        value = value.astimezone(UTC)
        now = datetime.now(UTC)
        if value <= now:
            raise ValueError("Pick a time in the future")
        if value > now + timedelta(days=60):
            raise ValueError("Lab tests can be booked up to 60 days ahead")
        return value


class LabBookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    lab_test_id: UUID | None
    test_name: str
    price_paise: int
    scheduled_at: datetime
    collection_type: CollectionType
    address: str | None
    contact_phone: str
    status: LabBookingStatus
    result_note: str | None
    cancellation_reason: str | None
    created_at: datetime


class LabBookingStatusUpdate(BaseModel):
    status: Literal["sample_collected", "completed"]
    result_note: str | None = Field(default=None, max_length=1000)


class LabBookingCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=300)
