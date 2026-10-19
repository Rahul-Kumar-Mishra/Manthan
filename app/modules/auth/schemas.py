from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.common.enums import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class SignInRequest(LoginRequest):
    """Which door the person used. "customer" is for patients; "staff" for admins and doctors.

    Omitted means either (kept for API clients that predate the split).
    """

    audience: Literal["customer", "staff"] | None = None


class RegisterRequest(LoginRequest):
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=2, max_length=160)
    date_of_birth: date
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("date_of_birth")
    @classmethod
    def date_of_birth_must_not_be_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value


class StaffUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: UserRole

    @field_validator("role")
    @classmethod
    def disallow_patient_role(cls, value: UserRole) -> UserRole:
        if value == UserRole.PATIENT:
            raise ValueError("Patient accounts must be created through registration")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: UserRole
    is_active: bool
    is_md: bool = False
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthResponse(TokenResponse):
    user: UserRead
