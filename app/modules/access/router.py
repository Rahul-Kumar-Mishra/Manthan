from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.common.enums import Module, UserRole
from app.modules.access import service
from app.modules.access.schemas import (
    GrantCreate,
    GrantRead,
    ModuleInfo,
    MyAccess,
    RevokeResult,
    StaffAccess,
)
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.auth.models import User

# Mounted at /admin/access: every admin account, including those without modules yet.
router = APIRouter(dependencies=[Depends(require_roles(UserRole.ADMIN))])


@router.get("/modules", response_model=list[ModuleInfo])
async def list_modules(_: User = Depends(get_current_user)) -> list[ModuleInfo]:
    return [ModuleInfo(module=m, description=d) for m, d in service.MODULE_DESCRIPTIONS.items()]


@router.get("/me", response_model=MyAccess)
async def my_access(
    session: AsyncSession = Depends(get_db_session), user: User = Depends(get_current_user)
) -> MyAccess:
    modules = await service.modules_for(session, user)
    return MyAccess(is_md=user.is_md, modules=sorted(modules))


@router.get("/staff", response_model=list[StaffAccess])
async def list_staff_access(
    session: AsyncSession = Depends(get_db_session), user: User = Depends(get_current_user)
) -> list[StaffAccess]:
    # Anyone who can hand out at least one module needs to see who to hand it to.
    if not await service.modules_for(session, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No module access")
    rows = await service.list_staff_accounts(session)
    return [
        StaffAccess(
            user_id=u.id,
            email=u.email,
            is_md=u.is_md,
            is_active=u.is_active,
            created_at=u.created_at,
            grants=[GrantRead.model_validate(g) for g in grants],
        )
        for u, grants in rows
    ]


@router.post("/grants", response_model=GrantRead, status_code=status.HTTP_201_CREATED)
async def grant_module(
    data: GrantCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> GrantRead:
    return await service.grant(session, user, data.user_id, Module(data.module))


@router.delete("/grants/{grant_id}", response_model=RevokeResult)
async def revoke_grant(
    grant_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> RevokeResult:
    return RevokeResult(revoked=await service.revoke(session, user, grant_id))
