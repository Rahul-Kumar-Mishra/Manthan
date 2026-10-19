from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import UserRole
from app.core.exceptions import ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth import repository
from app.modules.auth.models import User
from app.modules.auth.schemas import RegisterRequest, StaffUserCreate
from app.modules.patients.models import Patient


def build_auth_response(user: User) -> dict[str, str | User]:
    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "bearer",
        "user": user,
    }


async def register_patient(session: AsyncSession, data: RegisterRequest) -> dict[str, str | User]:
    user = User(
        email=str(data.email).lower(),
        hashed_password=hash_password(data.password),
        role=UserRole.PATIENT,
    )
    try:
        await repository.add_user(session, user)
        session.add(
            Patient(
                user_id=user.id,
                full_name=data.full_name,
                date_of_birth=data.date_of_birth,
                phone=data.phone,
            )
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("An account with that email already exists") from exc
    await session.refresh(user)
    return build_auth_response(user)


async def authenticate(
    session: AsyncSession, email: str, password: str
) -> dict[str, str | User] | None:
    user = await repository.get_user_by_email(session, email.lower())
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        return None
    return build_auth_response(user)


async def create_staff_user(session: AsyncSession, data: StaffUserCreate) -> User:
    user = User(
        email=str(data.email).lower(),
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    try:
        await repository.add_user(session, user)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("An account with that email already exists") from exc
    await session.refresh(user)
    return user
