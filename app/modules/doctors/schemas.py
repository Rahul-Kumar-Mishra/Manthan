from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class DoctorCreate(BaseModel):
    user_id: UUID | None = None
    branch_id: UUID
    full_name: str = Field(min_length=2, max_length=160)
    specialization: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    experience_years: int | None = Field(default=None, ge=0, le=70)
    qualifications: str | None = Field(default=None, max_length=300)
    registration_number: str | None = Field(default=None, max_length=60)
    languages: str | None = Field(default=None, max_length=200)
    bio: str | None = Field(default=None, max_length=2000)
    consultation_fee_paise: int | None = Field(default=None, ge=0, le=10_000_000)
    online_fee_paise: int | None = Field(default=None, gt=0, le=10_000_000)
    available_online: bool = False

    @model_validator(mode="after")
    def online_needs_fee(self) -> "DoctorCreate":
        if self.available_online and not self.online_fee_paise:
            raise ValueError("Set an online consultation fee to offer on-call appointments")
        return self


class DoctorUpdate(BaseModel):
    user_id: UUID | None = None
    branch_id: UUID | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    specialization: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    is_active: bool | None = None
    experience_years: int | None = Field(default=None, ge=0, le=70)
    qualifications: str | None = Field(default=None, max_length=300)
    registration_number: str | None = Field(default=None, max_length=60)
    languages: str | None = Field(default=None, max_length=200)
    bio: str | None = Field(default=None, max_length=2000)
    consultation_fee_paise: int | None = Field(default=None, ge=0, le=10_000_000)
    online_fee_paise: int | None = Field(default=None, gt=0, le=10_000_000)
    available_online: bool | None = None


class DoctorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    branch_id: UUID
    full_name: str
    specialization: str
    email: EmailStr | None
    phone: str | None
    is_active: bool
    experience_years: int | None = None
    qualifications: str | None = None
    registration_number: str | None = None
    languages: str | None = None
    bio: str | None = None
    consultation_fee_paise: int | None = None
    online_fee_paise: int | None = None
    available_online: bool = False
    created_at: datetime
