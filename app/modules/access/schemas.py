from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.common.enums import Module


class ModuleInfo(BaseModel):
    module: Module
    description: str


class MyAccess(BaseModel):
    is_md: bool
    modules: list[Module]


class GrantCreate(BaseModel):
    user_id: UUID
    module: Module


class GrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    module: Module
    granted_by: UUID | None
    created_at: datetime


class StaffAccess(BaseModel):
    user_id: UUID
    email: str
    is_md: bool
    is_active: bool
    created_at: datetime
    grants: list[GrantRead]


class RevokeResult(BaseModel):
    revoked: int
