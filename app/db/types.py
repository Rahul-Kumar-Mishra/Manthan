from enum import StrEnum

from sqlalchemy import Enum


def str_enum(cls: type[StrEnum]) -> Enum:
    """Store a StrEnum as its value in a VARCHAR column (no native DB enum)."""
    return Enum(
        cls, values_callable=lambda items: [item.value for item in items], native_enum=False
    )
