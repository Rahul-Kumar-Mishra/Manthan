import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
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


# ---------------------------------------------------------------------------
# Postgres harness
#
# Tests that need real Postgres semantics (row locks, the GiST exclusion
# constraint, concurrent transactions) request `pg_engine`, `pg_session_factory`
# or `pg_client`. The schema is built by `alembic upgrade head`, so the real
# migrations are under test, not `Base.metadata.create_all`.
#
# Database source, in order:
#   1. TEST_DATABASE_URL (e.g. a CI service container) - used as-is, never skipped.
#   2. A throwaway `postgres:17-alpine` testcontainer - skipped if Docker is unavailable.
#
# Any test that uses these fixtures is marked `postgres` automatically, so
# `pytest -m "not postgres"` keeps the fast SQLite loop.
# ---------------------------------------------------------------------------

POSTGRES_IMAGE = "postgres:17-alpine"
REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # tryfirst: add the marker before `-m` deselection runs.
    for item in items:
        if "postgres_url" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.postgres)


def run_migrations(database_url: str, revision: str = "head") -> None:
    config = Config(attributes={"database_url": database_url})
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    command.upgrade(config, revision)


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """URL of a Postgres database migrated to `head`, shared by the whole session."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        run_migrations(url)
        yield url
        return

    try:
        from testcontainers.community.postgres import PostgresContainer

        container = PostgresContainer(POSTGRES_IMAGE, driver="psycopg")
        container.start()
    except Exception as exc:  # Docker missing, daemon down, image pull failed...
        pytest.skip(f"Postgres unavailable (set TEST_DATABASE_URL or start Docker): {exc}")

    try:
        url = container.get_connection_url()
        run_migrations(url)
        yield url
    finally:
        container.stop()


async def truncate_all_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        tables = (
            await connection.execute(
                text(
                    "SELECT quote_ident(tablename) FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
            )
        ).scalars()
        names = ", ".join(tables)
        if names:
            await connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def pg_engine(postgres_url: str) -> AsyncIterator[AsyncEngine]:
    """Async engine on the migrated test database; every table starts empty."""
    engine = create_async_engine(postgres_url)
    await truncate_all_tables(engine)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def pg_session_factory(pg_engine: AsyncEngine) -> async_sessionmaker:
    """Each call opens an independent session on its own pooled connection."""
    return async_sessionmaker(pg_engine, expire_on_commit=False)


@pytest.fixture
async def pg_client(pg_session_factory: async_sessionmaker) -> AsyncIterator[httpx.AsyncClient]:
    """Like `client`, but the API talks to the real Postgres database."""

    async def override_db_session():
        async with pg_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    app.state.test_session_factory = pg_session_factory
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        del app.state.test_session_factory
