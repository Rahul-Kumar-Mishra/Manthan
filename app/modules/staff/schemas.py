from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.common.enums import StaffStatus

EmploymentType = Literal["full_time", "part_time", "contract", "visiting"]


class StaffCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    designation: str = Field(min_length=2, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    branch_id: UUID | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    employment_type: EmploymentType = "full_time"
    joined_on: date | None = None
    user_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)


class StaffUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    designation: str | None = Field(default=None, min_length=2, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    branch_id: UUID | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    employment_type: EmploymentType | None = None
    joined_on: date | None = None
    status: Literal["active", "on_leave"] | None = None
    user_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)


class StaffOffboard(BaseModel):
    left_on: date | None = None
    note: str | None = Field(default=None, max_length=300)


class StaffRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    designation: str
    department: str | None
    branch_id: UUID | None
    email: str | None
    phone: str | None
    employment_type: str
    joined_on: date | None
    left_on: date | None
    status: StaffStatus
    user_id: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
