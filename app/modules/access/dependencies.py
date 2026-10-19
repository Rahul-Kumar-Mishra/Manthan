from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.common.enums import Module, UserRole
from app.modules.access.service import ensure_module
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User


def require_module(module: Module) -> Callable:
    async def module_guard(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        await ensure_module(session, user, module)
        return user

    return module_guard


def require_role_or_module(roles: tuple[UserRole, ...], module: Module) -> Callable:
    """Allow users acting in their own role (e.g. the patient) or staff holding `module`."""

    async def guard(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        if user.role in roles:
            return user
        await ensure_module(session, user, module)
        return user

    return guard
