from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.common.enums import PaymentPurpose, PaymentStatus


class PayRequest(BaseModel):
    method: Literal["upi", "card", "netbanking"]
    upi_id: str | None = Field(default=None, max_length=80)
    card_number: str | None = Field(default=None, max_length=30)
    bank: str | None = Field(default=None, max_length=60)


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    purpose: PaymentPurpose
    reference_id: UUID
    amount_paise: int
    currency: str
    status: PaymentStatus
    method: str | None
    method_detail: str | None
    provider: str
    provider_reference: str | None
    failure_reason: str | None
    paid_at: datetime | None
    refunded_at: datetime | None
    created_at: datetime
