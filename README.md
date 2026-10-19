# Manthan Hospital Management System

Manthan is a Python 3.12 FastAPI modular monolith. Level 1 implements hospital/branch, doctor, patient, authentication, and appointment APIs on PostgreSQL. Appointment booking uses a transaction-locked doctor row and PostgreSQL exclusion constraints to prevent overlapping bookings.

## Local setup

Install Python 3.12, Docker Compose, and uv. From the repository root:

```sh
uv sync --dev
cp .env.example .env
docker compose up -d postgres
uv run alembic upgrade head
uv run python scripts/create_admin.py
uv run uvicorn app.main:app --reload
```

The local database credentials in `.env.example` are development-only. The admin script prompts for an email and password without writing the password to a file. The API is at `http://127.0.0.1:8000`; OpenAPI docs are at `/docs`, liveness at `/health/live`, and database readiness at `/api/v1/health/ready`.

## Authentication

Use `POST /api/v1/auth/login` to obtain a bearer token. Public registration creates patient accounts only. The initial administrator is created with `scripts/create_admin.py`; administrators can create staff accounts and manage hospital, branch, doctor, and patient records. Patients can view/update their own profile and manage their own appointments. Keep secrets and real patient data out of source control and test fixtures.

## Postman

Import [Manthan.postman_collection.json](Manthan.postman_collection.json). It covers every route and is ordered so the Collection Runner can run it top to bottom. Create the managing director with `uv run python scripts/create_md.py`, then set the `adminEmail` and `adminPassword` collection variables. The run itself fills in tokens (`adminToken`, `patientToken`, `doctorToken`), IDs, emails and future time slots, so it can be re-run as is. From the command line: `npx newman run Manthan.postman_collection.json --env-var adminEmail=... --env-var adminPassword=...`.

## Checks

```sh
uv run pytest
uv run ruff check .
```

Redis, workers, billing, prescriptions, notifications, and other Level 2/3 infrastructure remain dormant scaffolding and are not required to run Level 1.