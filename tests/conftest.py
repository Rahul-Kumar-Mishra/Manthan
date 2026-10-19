from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db_session
from app.common.enums import UserRole
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.main import app
from app.modules.auth.models import User


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    app.state.test_session_factory = session_factory
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        del app.state.test_session_factory
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.fixture
async def admin_client(client: httpx.AsyncClient) -> AsyncIterator[httpx.AsyncClient]:
    async with app.state.test_session_factory() as session:
        user = User(
            email="admin@example.com",
            hashed_password=hash_password("test-admin-password-123"),
            role=UserRole.ADMIN,
            is_md=True,
        )
        session.add(user)
        await session.commit()
        token = create_access_token(str(user.id))
    client.headers["Authorization"] = f"Bearer {token}"
    yield client


@pytest.fixture
async def patient_client(client: httpx.AsyncClient) -> AsyncIterator[httpx.AsyncClient]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "patient@example.com",
            "password": "test-patient-password-123",
            "full_name": "Example Patient",
            "date_of_birth": "1990-01-01",
        },
    )
    assert response.status_code == 201
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    yield client
