from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PatientCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    date_of_birth: date
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("date_of_birth")
    @classmethod
    def date_of_birth_must_not_be_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value


class PatientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    date_of_birth: date | None = None
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("date_of_birth")
    @classmethod
    def date_of_birth_must_not_be_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    date_of_birth: date
    phone: str | None
    created_at: datetime
