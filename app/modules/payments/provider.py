"""Payment gateway adapters.

Only a simulated gateway ships today. A real integration (e.g. Juspay) would
implement `PaymentProvider.charge`/`refund` against its API and be selected by
`settings.payment_provider`.
"""

import re
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from app.modules.payments.schemas import PayRequest


@dataclass
class ChargeResult:
    success: bool
    reference: str
    method_detail: str
    failure_reason: str | None = None


class PaymentProvider(Protocol):
    name: str

    async def charge(self, amount_paise: int, request: PayRequest) -> ChargeResult: ...

    async def refund(self, reference: str, amount_paise: int) -> str: ...


UPI_PATTERN = re.compile(r"^[\w.\-]{2,}@[a-zA-Z]{2,}$")
DECLINED_TEST_CARD = "4000000000000002"


class MockProvider:
    """Deterministic test gateway: UPI IDs ending in @fail and card 4000 0000 0000 0002 decline."""

    name = "mock"

    async def charge(self, amount_paise: int, request: PayRequest) -> ChargeResult:
        reference = f"mock_{uuid4().hex[:16]}"
        if request.method == "upi":
            upi = (request.upi_id or "").strip()
            if not UPI_PATTERN.match(upi):
                return ChargeResult(False, reference, upi, "Enter a valid UPI ID, e.g. name@bank")
            if upi.lower().endswith("@fail"):
                return ChargeResult(False, reference, upi, "Declined by the UPI app")
            return ChargeResult(True, reference, upi)
        if request.method == "card":
            digits = re.sub(r"\D", "", request.card_number or "")
            if len(digits) < 12 or len(digits) > 19:
                return ChargeResult(False, reference, "card", "Enter a valid card number")
            detail = f"card •••• {digits[-4:]}"
            if digits == DECLINED_TEST_CARD:
                return ChargeResult(False, reference, detail, "Card declined by the issuing bank")
            return ChargeResult(True, reference, detail)
        bank = (request.bank or "").strip()
        if not bank:
            return ChargeResult(False, reference, "netbanking", "Choose a bank")
        return ChargeResult(True, reference, f"netbanking · {bank}")

    async def refund(self, reference: str, amount_paise: int) -> str:
        return f"mock_refund_{uuid4().hex[:12]}"


def get_provider() -> PaymentProvider:
    return MockProvider()
