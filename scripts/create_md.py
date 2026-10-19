"""Create (or promote) the managing director: the root of the module-access hierarchy.

    uv run python scripts/create_md.py                       # rahul.mishra@manthan.in, prompts
    uv run python scripts/create_md.py --email someone@x.in  # a different MD

Set MANTHAN_MD_PASSWORD to run non-interactively. The password is never written to disk.
"""

import argparse
import asyncio
import os
from getpass import getpass

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select

from app.common.enums import UserRole
from app.core.security import hash_password
from app.db.session import engine, session_factory
from app.modules.auth.models import User

DEFAULT_MD_EMAIL = "rahul.mishra@manthan.in"


def read_password() -> str:
    password = os.environ.get("MANTHAN_MD_PASSWORD")
    if password is None:
        password = getpass("MD password (12+ characters): ")
        if getpass("Confirm MD password: ") != password:
            raise SystemExit("Passwords do not match")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters")
    return password


async def main(email: str) -> None:
    email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                hashed_password=hash_password(read_password()),
                role=UserRole.ADMIN,
                is_md=True,
            )
            session.add(user)
            action = "Created"
        else:
            if user.role != UserRole.ADMIN:
                raise SystemExit(f"{email} is a {user.role.value} account and cannot become MD")
            user.is_md = True
            user.is_active = True
            action = "Promoted"
        await session.commit()
    await engine.dispose()
    print(f"{action} managing director {email} with access to every module")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", default=DEFAULT_MD_EMAIL)
    asyncio.run(main(parser.parse_args().email))
