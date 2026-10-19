import asyncio
from getpass import getpass

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select

from app.common.enums import UserRole
from app.core.security import hash_password
from app.db.session import engine, session_factory
from app.modules.auth.models import User


async def main() -> None:
    email = str(TypeAdapter(EmailStr).validate_python(input("Admin email: "))).lower()
    password = getpass("Admin password (12+ characters): ")
    confirmation = getpass("Confirm admin password: ")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters")
    if password != confirmation:
        raise SystemExit("Passwords do not match")

    async with session_factory() as session:
        existing_user = await session.scalar(select(User).where(User.email == email))
        if existing_user is not None:
            raise SystemExit("An account with that email already exists")
        session.add(
            User(
                email=email,
                hashed_password=hash_password(password),
                role=UserRole.ADMIN,
            )
        )
        await session.commit()
    await engine.dispose()
    print(f"Created administrator account for {email}")


if __name__ == "__main__":
    asyncio.run(main())
