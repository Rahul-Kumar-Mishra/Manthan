from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.common.enums import UserRole
from app.modules.auth import service
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    AuthResponse,
    RegisterRequest,
    SignInRequest,
    UserRead,
)

router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest, session: AsyncSession = Depends(get_db_session)
) -> AuthResponse:
    return await service.register_patient(session, data)


@router.post("/login", response_model=AuthResponse)
async def login(
    data: SignInRequest, session: AsyncSession = Depends(get_db_session)
) -> AuthResponse:
    result = await service.authenticate(session, str(data.email), data.password)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Customers and staff sign in through separate pages; send people to the right one.
    is_staff = result["user"].role in (UserRole.ADMIN, UserRole.DOCTOR)
    if data.audience == "customer" and is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This is a staff account. Please use the admin login.",
        )
    if data.audience == "staff" and not is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This is a customer account. Please use the customer sign in.",
        )
    return result


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> UserRead:
    return user
