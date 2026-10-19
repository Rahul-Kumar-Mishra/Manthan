from collections.abc import Callable
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.common.enums import UserRole
from app.core.config import settings
from app.modules.auth.models import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid bearer credentials are required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=["HS256"])
        user_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise unauthorized from None
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_roles(*allowed_roles: UserRole) -> Callable:
    async def role_guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return role_guard
