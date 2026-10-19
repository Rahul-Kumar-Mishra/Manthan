from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HospitalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    address: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=40)


class HospitalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    address: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=40)


class HospitalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    address: str | None
    phone: str | None
    created_at: datetime
