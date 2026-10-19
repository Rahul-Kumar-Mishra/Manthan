from uuid import UUID


def normalize_uuid(value: UUID | str) -> UUID:
    return value if isinstance(value, UUID) else UUID(value)
