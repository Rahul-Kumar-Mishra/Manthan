"""Smoke tests for the Postgres harness: real DB, schema built by the Alembic migrations."""

import uuid
from pathlib import Path

import httpx
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.modules.patients.models import Patient

REPO_ROOT = Path(__file__).resolve().parents[2]


def alembic_head() -> str:
    config = Config()
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    head = ScriptDirectory.from_config(config).get_current_head()
    assert head is not None
    return head


async def test_schema_is_built_by_migrations_at_head(pg_engine: AsyncEngine) -> None:
    async with pg_engine.connect() as connection:
        version = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        extension = await connection.scalar(
            text("SELECT extname FROM pg_extension WHERE extname = 'btree_gist'")
        )
        constraint_type = await connection.scalar(
            text(
                "SELECT contype FROM pg_constraint "
                "WHERE conname = 'ex_appointment_doctor_no_overlap'"
            )
        )

    assert version == alembic_head()
    assert extension == "btree_gist"
    assert constraint_type == "x"  # exclusion constraint


async def test_exclusion_constraint_rejects_overlapping_scheduled_appointments(
    pg_engine: AsyncEngine,
) -> None:
    hospital_id, branch_id, doctor_id, patient_id = (uuid.uuid4() for _ in range(4))
    async with pg_engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO hospitals (id, name, created_at) VALUES (:id, 'H', now())"),
            {"id": hospital_id},
        )
        await connection.execute(
            text(
                "INSERT INTO branches (id, hospital_id, name, created_at) "
                "VALUES (:id, :hospital_id, 'B', now())"
            ),
            {"id": branch_id, "hospital_id": hospital_id},
        )
        await connection.execute(
            text(
                "INSERT INTO doctors (id, branch_id, full_name, specialization, is_active, "
                "created_at) VALUES (:id, :branch_id, 'Dr X', 'General', true, now())"
            ),
            {"id": doctor_id, "branch_id": branch_id},
        )
        await connection.execute(
            text(
                "INSERT INTO patients (id, full_name, date_of_birth, created_at) "
                "VALUES (:id, 'P', '1990-01-01', now())"
            ),
            {"id": patient_id},
        )

    insert_appointment = text(
        "INSERT INTO appointments (id, patient_id, doctor_id, starts_at, ends_at, status, "
        "created_at) VALUES (gen_random_uuid(), :patient_id, :doctor_id, "
        "CAST(:starts_at AS timestamptz), CAST(:ends_at AS timestamptz), 'scheduled', now())"
    )
    ids = {"patient_id": patient_id, "doctor_id": doctor_id}
    async with pg_engine.begin() as connection:
        await connection.execute(
            insert_appointment,
            {**ids, "starts_at": "2030-01-01T10:00Z", "ends_at": "2030-01-01T10:30Z"},
        )

    # Different start time (so the unique index can't catch it) but overlapping range.
    with pytest.raises(IntegrityError, match="ex_appointment_doctor_no_overlap"):
        async with pg_engine.begin() as connection:
            await connection.execute(
                insert_appointment,
                {**ids, "starts_at": "2030-01-01T10:15Z", "ends_at": "2030-01-01T10:45Z"},
            )

    # Back-to-back slots are fine: the range is half-open '[)'.
    async with pg_engine.begin() as connection:
        await connection.execute(
            insert_appointment,
            {**ids, "starts_at": "2030-01-01T10:30Z", "ends_at": "2030-01-01T11:00Z"},
        )


async def test_api_runs_against_postgres(
    pg_client: httpx.AsyncClient, pg_session_factory: async_sessionmaker
) -> None:
    response = await pg_client.post(
        "/api/v1/auth/register",
        json={
            "email": "pg-patient@example.com",
            "password": "test-patient-password-123",
            "full_name": "Postgres Patient",
            "date_of_birth": "1990-01-01",
        },
    )
    assert response.status_code == 201, response.text

    async with pg_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Patient)) == 1


async def test_tables_start_empty_for_each_test(pg_session_factory: async_sessionmaker) -> None:
    # Runs after the test above registered a patient; truncation must have cleared it.
    async with pg_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Patient)) == 0
