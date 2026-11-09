# Manthan — Scalability Plan

Status: **Draft for review** · Author: Rahul Kumar Mishra · Date: 2026-11-09

This plan has two jobs:

1. Make Manthan scale horizontally on Kubernetes **without losing correctness** (no double-bookings, no oversold stock, no lost updates) as replicas and traffic grow.
2. Make every line of the project description true, testable, and demonstrable from the repo.

Each phase below lists **why**, **what changes (files)**, **how to execute (commands)**, and **done when** (acceptance criteria). Phases are ordered so that each one gives the next one something to measure against. Nothing here has been implemented yet; review, adjust, then execute phase by phase (one PR per phase).

---

## 1. Where the project stands today

Audit of the current `main` (commit `827ea9d`) against each claim.

| Claim | What exists now | Status |
|---|---|---|
| Row-level locking (`SELECT FOR UPDATE`) | Doctor row locked in `app/modules/appointments/booking.py:78`; medicine rows locked in `app/modules/pharmacy/service.py:172` (`_locked`), sorted lock order at checkout | ✅ Done |
| GiST exclusion constraint | `ex_appointment_doctor_no_overlap` on `tstzrange(starts_at, ends_at)` in `app/modules/appointments/models.py`; `ck_medicine_stock_non_negative` backstop on stock | ✅ Done |
| "Validated through dedicated concurrency tests" | `tests/concurrency/test_double_booking.py` only checks that the constraint **exists in metadata**. All tests run on **SQLite** (`tests/conftest.py`), where `FOR UPDATE` and GiST are no-ops | ❌ Not actually validated |
| 20 domain modules | 20 packages under `app/modules/`; 8 (`audit`, `billing`, `departments`, `medical_records`, `notifications`, `prescriptions`, `schedules`, `users`) are scaffolding/not mounted in `app/api/router.py` | ⚠️ Count is true; several are dormant |
| 110+ REST APIs | 114 route decorators | ✅ Done |
| SQLAlchemy 2.0 async, JWT, Argon2, module RBAC, OpenAPI | All present (`app/core/security.py`, `app/modules/access/`) | ✅ Done |
| k6 load/stress testing | `load-tests/*.js` only hit `/health/live` — no real endpoint is load-tested | ⚠️ Shell only |
| Prometheus monitoring | `deploy/prometheus/prometheus.yml` scrapes only itself; app exposes no `/metrics` | ❌ Missing |
| Structured request logging | `app/core/logging.py` is `basicConfig`; `configure_logging()` is never called; middleware only echoes `X-Request-ID` | ❌ Missing |
| 33 automated tests, unit/integration/concurrency | 33 test functions; 1 skipped perf placeholder; concurrency test is metadata-only | ⚠️ See above |
| GitHub Actions CI | `.github/workflows/checks.yml`: ruff + pytest on SQLite. Jenkins does image build + smoke | ⚠️ Partial |
| Multi-stage Docker builds | `docker/api.Dockerfile` is single-stage; `docker/worker.Dockerfile` uses plain `pip`, no lock, runs as root | ❌ Missing |
| Kubernetes + HPA 2–8 @ 70% CPU | `deploy/kubernetes/hpa.yaml` matches. But: `:latest` tags, no migration Job, no PDB/ingress, worker has no secrets, CPU request `100m` makes 70% fire at 70m | ⚠️ Works on paper, not production-ready |
| Pluggable payment gateway interface | `PaymentProvider` Protocol in `app/modules/payments/provider.py`; `get_provider()` hard-codes `MockProvider`; no webhook, no idempotency | ⚠️ Interface only |
| React + TypeScript dashboard | No frontend in the repo | ❌ Missing |

---

## 2. Scalability bottlenecks found in the code

These are the things that will break or degrade first when you go from 1 pod to 8.

| # | Problem | Where | Impact at scale |
|---|---|---|---|
| B1 | **Sweeps run inside request paths.** `release_unpaid_holds()` and `expire_unpaid_orders()` scan and update every stale row on every booking, availability check, checkout and order listing | `appointments/booking.py:22,55,77`; `pharmacy/service.py:309,326,390,403` | Every replica does the same table scan + writes concurrently; read endpoints become writers; lock contention grows with traffic |
| B2 | **Unbounded connection pool math.** `create_async_engine(..., pool_pre_ping=True)` → default `pool_size=5, max_overflow=10` | `app/db/session.py` | 8 pods × 15 = 120 connections > Postgres default `max_connections=100` → `too many clients` under HPA scale-out |
| B3 | **RBAC hits the DB on every admin request** | `access/service.py:modules_for` | Extra query per request; fine now, measurable at scale |
| B4 | **`BaseHTTPMiddleware`** for request context | `core/middleware.py` | Known Starlette overhead + breaks contextvars propagation for logging |
| B5 | **Leading-wildcard `ILIKE '%x%'` search** without trigram index | `pharmacy/service.py:83`, `doctors/repository.py:20`, `staff/service.py:32` | Sequential scans on catalogue search |
| B6 | **Hard `limit(500)` lists without pagination** | `pharmacy/service.py:399`, `lab/service.py:94` | Large payloads, slow admin views as data grows |
| B7 | **Migrations run at API start** (`alembic upgrade head && uvicorn` in `compose.yaml`) | `compose.yaml` | In k8s, N replicas race to migrate |
| B8 | **`FOR UPDATE` on the doctor row** blocks *any* other transaction taking `FOR KEY SHARE` on that doctor (e.g. inserting a leave row, FK checks) | `booking.py:78` | Avoidable contention; `FOR NO KEY UPDATE` gives the same serialization for booking |
| B9 | **Readiness probe = DB `SELECT 1`** with no timeout | `app/db/health.py` | A DB blip marks *all* pods unready at once → full outage instead of degraded errors |
| B10 | **Worker is a no-op** (`asyncio.Event().wait()`) | `app/workers/runner.py` | Nowhere to move background work (B1, notifications) yet |

---

## 3. Target architecture

```
                       ┌──────────────────────────┐
  Browser ──HTTPS──►   │ Ingress (nginx)          │
                       │  /       → web (React)   │
                       │  /api/*  → manthan-api   │
                       └─────────┬────────────────┘
                                 │
           ┌─────────────────────┼───────────────────────┐
           ▼                     ▼                       ▼
   ┌──────────────┐    ┌──────────────────┐     ┌────────────────┐
   │ web (nginx + │    │ manthan-api      │     │ manthan-worker │
   │ static SPA)  │    │ Deployment       │     │ Deployment     │
   └──────────────┘    │ HPA 2–8 @70% CPU │     │ 1–3 replicas   │
                       │ /metrics         │     │ sweeps, notifs │
                       └──┬─────────┬─────┘     └───┬────────┬───┘
                          │         │               │        │
                          ▼         ▼               ▼        ▼
                    ┌──────────┐ ┌──────┐     (same PgBouncer, Redis)
                    │PgBouncer │ │Redis │
                    │txn mode  │ │cache,│
                    └────┬─────┘ │rate  │
                         ▼       │limit,│
                   ┌──────────┐  │queue │
                   │PostgreSQL│  └──────┘
                   │ 17       │
                   └──────────┘
      Prometheus ──scrapes──► api /metrics, worker /metrics, postgres-exporter
      Grafana    ──reads────► Prometheus
```

Principles:
- **API pods are stateless.** Every piece of shared state is in Postgres (truth) or Redis (derived/ephemeral).
- **Correctness lives in Postgres**, not in app memory or Redis: locks + constraints, so it holds at any replica count.
- **Background work is idempotent and replica-safe** (`FOR UPDATE SKIP LOCKED`), so the worker can scale too.
- **Measure before tuning.** HPA targets and resource requests are set from k6 numbers, not guessed.

---

## 4. Phased execution plan

### Phase 0 — Postgres-backed test harness (foundation)

**Why:** Every concurrency claim depends on Postgres semantics. SQLite cannot validate them.

**Changes**
- `pyproject.toml`: add dev deps `testcontainers[postgres]`, `pytest-xdist` (optional).
- `tests/conftest.py`: add a `pg_engine` fixture (session-scoped) that:
  - uses `TEST_DATABASE_URL` if set (CI service container), else starts a `postgres:17-alpine` testcontainer;
  - runs `alembic upgrade head` (so the **real migrations** — including the GiST constraint and `btree_gist` extension — are under test);
  - truncates tables between tests.
- Add pytest markers in `pyproject.toml`: `postgres`, `concurrency`, `slow`. Keep the existing fast SQLite `client` fixture for unit/integration tests that don't need Postgres.

**Execute**
```sh
uv add --dev "testcontainers[postgres]"
uv run pytest -m "not postgres"          # fast loop, unchanged
uv run pytest -m postgres                # needs Docker
```

**Done when:** `uv run pytest -m postgres` runs at least one test against a real Postgres built from Alembic migrations.

---

### Phase 1 — Prove and harden concurrency safety

**Why:** This is the headline claim; it must be demonstrated by tests that would fail without the locks/constraints.

**1a. Real concurrency tests** — `tests/concurrency/`

Each test opens **N independent sessions** (separate connections, not one shared session) and fires them with `asyncio.gather`, synchronised with an `asyncio.Barrier` so they hit the DB at the same instant.

| Test file | Scenario | Assertion |
|---|---|---|
| `test_double_booking.py` (rewrite) | 20 patients book the **same doctor + same slot** | exactly 1 success, 19 `ConflictError`; 1 `scheduled` row in DB |
| | 20 patients book **overlapping** slots (10:00–10:30, 10:15–10:45, …) | no two scheduled rows overlap (SQL check with `tstzrange &&`) |
| `test_constraint_backstop.py` | Bypass the service and `INSERT` overlapping rows directly | raises `ExclusionViolation` → proves the DB guards even if app logic regresses |
| `test_pharmacy_stock.py` | Stock = 5; 20 concurrent checkouts of qty 1 | exactly 5 orders; `stock_quantity == 0`; `sum(stock_movements.change) == -5` |
| | Concurrent `restock(+10)` ×10 and `checkout(-1)` ×10 on the same medicine | final stock = start + 100 − 10 (**no lost update**) |
| | Two carts with medicines A,B and B,A checked out concurrently | both complete or fail cleanly; **no deadlock** (proves sorted lock order) |
| | Customer cancel vs. admin advance-status on same order | order ends in one valid state; stock movements consistent |
| `test_lock_regression.py` | Monkeypatch `with_for_update` out, rerun the stock test | test **fails** (oversell/lost update) → proves the test actually exercises the lock |

**1b. Hardening changes**

- **Move sweeps off the hot path (B1).**
  - New `app/workers/jobs/expiry.py`: `release_unpaid_holds` / `expire_unpaid_orders` process in batches using
    `SELECT … WHERE status=… AND created_at < cutoff ORDER BY created_at LIMIT 100 FOR UPDATE SKIP LOCKED`, commit per batch. Safe with multiple worker replicas.
  - In the request path keep only a **scoped** release: inside `book_appointment`, after locking the doctor, release stale holds **for that doctor and overlapping window only**. In `checkout`, release stale orders only for the medicines being locked. This keeps "slot frees up exactly at 15 min" semantics without global scans.
  - Remove the sweep calls from read endpoints (`unavailable_reason`, `list_orders`). `ensure_order_payable` already checks the payment window on its own.
- **Narrow the doctor lock (B8):** `.with_for_update(key_share=True)` → `FOR NO KEY UPDATE`. Same serialization between bookings, doesn't block FK-referencing inserts.
- **Lock timeouts:** in booking/checkout transactions run `SET LOCAL lock_timeout = '3s'`; map `LockNotAvailable` to `409 Conflict, "Busy, please retry"` instead of a hung request.
- **Idempotency keys** for `POST /book/*` and `POST /my/payments/*`: optional `Idempotency-Key` header stored in a `idempotency_keys` table (unique on `user_id, key`) with the stored response; retries from a flaky mobile network don't create duplicates.

**Execute**
```sh
uv run pytest tests/concurrency -m concurrency -v
uv run alembic revision -m "idempotency keys" --autogenerate
```

**Done when:** all concurrency tests pass on Postgres; the lock-regression test proves they'd fail without locks; no sweep query appears in the read-path SQL (verify with `echo=True` or `pg_stat_statements`).

---

### Phase 2 — Stateless, pool-aware API

**Why:** HPA can only add pods if each pod is cheap on shared resources (DB connections) and fully stateless.

**Changes**
- `app/core/config.py`: add
  ```python
  environment: str = "local"           # local | ci | staging | prod
  db_pool_size: int = 5
  db_max_overflow: int = 5
  db_pool_timeout: int = 5
  db_statement_timeout_ms: int = 5000
  use_pgbouncer: bool = False
  log_level: str = "INFO"
  log_json: bool = False
  payment_provider: str = "mock"
  cors_origins: list[str] = []
  ```
  and fail fast at startup if `environment == "prod"` and `secret_key` is the default.
- `app/db/session.py`: pass pool settings; set `statement_timeout` via `connect_args={"options": "-c statement_timeout=5000"}`; when `use_pgbouncer`, set `prepare_threshold=None` (psycopg 3 server-side prepared statements are incompatible with transaction pooling).
- **PgBouncer** (transaction mode) between API and Postgres. Row locks and `SET LOCAL` are transaction-scoped, so they work under transaction pooling. Avoid session-level advisory locks and `SET` (non-LOCAL).
- **Connection budget** (document in `docs/scaling-strategy.md`):

  | Component | Count | Client conns each | Total to PgBouncer |
  |---|---|---|---|
  | API pods (max) | 8 | 10 | 80 |
  | Worker pods (max) | 3 | 3 | 9 |
  | PgBouncer → Postgres `default_pool_size` | — | — | **25** real server connections |

- `app/core/middleware.py` (B4): rewrite as a pure ASGI middleware; store `request_id` in a `contextvars.ContextVar` for logging (Phase 3).
- `app/main.py`: add a `lifespan` that calls `configure_logging()`, opens the Redis client, and on shutdown `await engine.dispose()`; add `CORSMiddleware` from settings; add `GZipMiddleware(minimum_size=1024)`.
- Uvicorn flags: `--proxy-headers --forwarded-allow-ips='*' --timeout-graceful-shutdown 20`. One uvicorn process per pod — scale via pods, not workers, so HPA CPU math stays honest.
- **Readiness (B9):** `/health/ready` checks DB with a 1 s timeout; add `/health/startup` for the startup probe. Liveness never touches the DB.
- **Pagination (B6):** replace `limit(500)` with the existing `app/common/pagination.py` (`offset/limit`, max 100) on orders and lab bookings; consider keyset pagination (`created_at, id`) for admin lists.
- **Indexes (B5)** — new migration:
  ```sql
  CREATE EXTENSION IF NOT EXISTS pg_trgm;
  CREATE INDEX CONCURRENTLY ix_medicines_name_trgm ON medicines USING gin (name gin_trgm_ops);
  CREATE INDEX CONCURRENTLY ix_medicines_generic_trgm ON medicines USING gin (generic_name gin_trgm_ops);
  CREATE INDEX CONCURRENTLY ix_doctors_specialization_trgm ON doctors USING gin (specialization gin_trgm_ops);
  CREATE INDEX CONCURRENTLY ix_orders_status_created ON medicine_orders (status, created_at);
  CREATE INDEX CONCURRENTLY ix_appt_pending_created ON appointments (created_at)
      WHERE status = 'scheduled' AND payment_status = 'pending';
  ```
  (`CONCURRENTLY` needs `op.get_context().autocommit_block()` in Alembic.)

**Done when:** API starts with explicit pool limits; at 8 replicas under k6 load, `SELECT count(*) FROM pg_stat_activity` stays ≤ PgBouncer pool size; `EXPLAIN` on catalogue search shows index usage.

---

### Phase 3 — Observability: structured logs + Prometheus + Grafana

**Changes**
- **Structured logging** — `app/core/logging.py`: JSON formatter (stdlib `logging` + a small formatter, or `structlog`). Every line carries `timestamp, level, logger, request_id, method, path, status, duration_ms, user_id (if authenticated), pod`. Access log emitted by the ASGI middleware; disable uvicorn's default access log. Never log request bodies, tokens or patient PII.
- **Metrics** — add `prometheus-client` (or `prometheus-fastapi-instrumentator`), expose `GET /metrics` (excluded from OpenAPI; not routed through the public ingress):
  - `http_requests_total{method,route,status}`, `http_request_duration_seconds{method,route}` (histogram — use the **route template**, not the raw path, to keep cardinality bounded);
  - business metrics: `appointment_bookings_total{result=success|conflict|on_leave}`, `pharmacy_checkouts_total{result}`, `db_lock_wait_seconds` (time spent acquiring `FOR UPDATE`), `expiry_sweep_released_total{kind}`;
  - DB pool gauges: checked-out / overflow from SQLAlchemy pool events.
- Worker exposes `/metrics` on a side port (`prometheus_client.start_http_server(9100)`).
- `deploy/prometheus/prometheus.yml`: scrape `manthan-api`, `manthan-worker`, `postgres-exporter`, `redis-exporter`. In k8s use pod annotations or a `ServiceMonitor` (kube-prometheus-stack).
- `deploy/grafana/dashboards/manthan.json`: RED panels (rate, errors, p50/p95/p99 duration) per route, booking conflict rate, lock wait p95, DB pool saturation, HPA replica count.
- Alert rules (`deploy/prometheus/alerts.yml`): 5xx rate > 1% for 5 min; p95 > 1 s for 10 min; DB pool waiting > 0 for 5 min.
- `compose.yaml`: add `prometheus`, `grafana`, `redis` services under a `monitoring` profile (`docker compose --profile monitoring up`).

**Done when:** `curl localhost:8000/metrics` returns the histograms; Grafana dashboard shows live data during a k6 run; each log line is valid JSON with a `request_id` that matches the response header.

---

### Phase 4 — Realistic k6 load, stress and contention tests

**Why:** Current scripts only ping `/health/live`. Capacity numbers and HPA thresholds must come from real traffic.

**Changes** — `load-tests/`
- `lib/auth.js`: `setup()` logs in a pool of seeded patients/admins and returns tokens.
- `scripts/seed_load_data.py`: seeds e.g. 5 hospitals, 200 doctors, 10k patients, 2k medicines.
- `load-test.js` — steady realistic mix (scenarios with `constant-arrival-rate`):
  - 60% catalogue browse (`GET /doctors`, `/medicines?search=`), 20% profile/my-appointments, 10% availability, 7% booking, 3% cart+checkout.
  - thresholds: `http_req_failed < 1%`, `p(95) < 300ms` reads, `p(95) < 800ms` booking/checkout.
- `stress-test.js` — ramp to breaking point (`ramping-arrival-rate` 50 → 1000 rps) to find max throughput per pod and confirm HPA scales 2 → 8.
- `contention-test.js` — 200 VUs hammer **one doctor's single slot** and **one low-stock medicine**; custom `Counter`s for 201 vs 409; post-run check script asserts exactly 1 booking and stock never negative. This is the load-level twin of Phase 1.
- `soak-test.js` — 30–60 min at 60% of peak; watch memory/connection leaks.
- Output to Prometheus remote-write (`k6 run -o experimental-prometheus-rw`) so load and server metrics appear on the same Grafana dashboard.
- Replace the skipped `tests/performance/test_api_performance.py` placeholder with a pytest that runs `k6 run smoke-test.js` when `K6=1`, or delete it.

**Execute**
```sh
uv run python scripts/seed_load_data.py
k6 run -e BASE_URL=http://localhost:8000 load-tests/load-test.js
k6 run -e BASE_URL=http://localhost:8000 load-tests/contention-test.js
```

**Done when:** a baseline results table (rps, p95, error %) per scenario is recorded in `load-tests/README.md` for 1 pod and for the k8s HPA setup.

---

### Phase 5 — Redis: caching, rate limiting, RBAC cache

**Changes**
- Wire the existing `app/cache/` into the app lifespan; expose `get_cache()` dependency. Make Redis **optional**: if unreachable, log and fall through to the DB (cache must never be required for correctness).
- **Read-through cache** (`app/cache/keys.py` for key names, versioned prefix `v1:`):
  - catalogue lists — hospitals, branches, doctors, medicines, lab tests — TTL 60 s, invalidated on admin write;
  - **never** cache stock counts used for checkout decisions or availability used for booking — those always come from Postgres under lock.
- **RBAC cache (B3):** `modules_for(user)` cached under `rbac:{user_id}` TTL 300 s; `grant`/`revoke` delete the key (and the subtree's keys).
- **Rate limiting:** fixed-window counter in Redis (`INCR` + `EXPIRE`) as a dependency: `POST /auth/login` 10/min per IP+email, `POST /auth/register` 5/min per IP, booking 30/min per user. Return `429` with `Retry-After`.
- Add `redis` to `compose.yaml`; in k8s use a managed Redis or Bitnami chart.

**Done when:** cached catalogue endpoints show p95 drop in k6; tests cover cache invalidation on admin update and graceful behaviour with Redis down.

---

### Phase 6 — Real worker

**Changes**
- `app/workers/runner.py`: async loop with a small scheduler (`asyncio` tasks, no extra dependency) running:
  - `expire_unpaid_holds` every 30 s, `expire_unpaid_orders` every 30 s (Phase 1 batch + `SKIP LOCKED` versions);
  - `notifications` consumer: Redis Streams consumer group (`XREADGROUP`, `XACK`) — appointment confirmations, order status changes. API publishes events after commit (outbox table if you need exactly-once; at-least-once + idempotent handlers is enough for now).
- Graceful shutdown on `SIGTERM` (finish current batch, then exit).
- `/metrics` + a tiny liveness file or HTTP endpoint (`app/workers/health.py` exists).

**Done when:** running 3 worker replicas never double-processes a row (assert via a test that runs two sweepers concurrently on the same stale rows).

---

### Phase 7 — Multi-stage Docker images

**`docker/api.Dockerfile`** (worker uses the same file with a different `CMD`, or `--target worker`):

```dockerfile
# ---- builder: resolve and install deps with uv ----
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

# ---- runtime: no uv, no build tools, non-root ----
FROM python:3.12-slim AS runtime
RUN useradd --uid 10001 --create-home appuser
WORKDIR /app
COPY --from=builder --chown=appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser /app/app ./app
COPY --from=builder --chown=appuser /app/migrations ./migrations
COPY --from=builder --chown=appuser /app/alembic.ini ./
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER 10001

FROM runtime AS api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips=*", "--no-access-log"]

FROM runtime AS worker
CMD ["python", "-m", "app.workers.runner"]
```

- Remove the Docker `HEALTHCHECK` (k8s probes replace it; it also spawns Python every interval).
- Delete `docker/worker.Dockerfile` (superseded by `--target worker`).
- `.dockerignore`: ensure `.venv`, `tests`, `load-tests`, `.git`, `web/node_modules` are excluded.
- Frontend: `web/Dockerfile` — `node:22-alpine` build stage → `nginx:1.27-alpine` runtime serving `dist/`.

**Execute**
```sh
docker build -f docker/api.Dockerfile --target api    -t manthan-api:dev .
docker build -f docker/api.Dockerfile --target worker -t manthan-worker:dev .
docker image ls manthan-api   # expect a markedly smaller image than the current single-stage one
```

**Done when:** images build, run as UID 10001, contain no `uv`/compilers, and pass the Jenkins smoke stage.

---

### Phase 8 — Kubernetes, production-shaped

Reorganise `deploy/kubernetes/` into **Kustomize** (`base/` + `overlays/{local,prod}`) so local (kind/minikube) and prod differ only by patches.

**base/**
- `api-deployment.yaml`
  - image pinned by tag/digest (CI sets it via `kustomize edit set image`), never `:latest`;
  - `resources`: start at `requests: cpu 250m, memory 256Mi; limits: memory 512Mi` (no CPU limit to avoid throttling; **tune from Phase 4 numbers**). HPA % is relative to *requests*, so a realistic request is what makes "70%" meaningful;
  - probes: `startupProbe` → `/health/startup`, `readinessProbe` → `/api/v1/health/ready` (timeout 2s), `livenessProbe` → `/health/live`;
  - `lifecycle.preStop: sleep 10` + `terminationGracePeriodSeconds: 30` so the pod leaves the Service endpoints before uvicorn stops (zero dropped requests during scale-in / rollout);
  - `strategy: RollingUpdate maxUnavailable: 0, maxSurge: 25%`;
  - `topologySpreadConstraints` across nodes; `securityContext` (`runAsNonRoot`, `readOnlyRootFilesystem`, drop all caps) + `emptyDir` for `/tmp`;
  - Prometheus scrape annotations.
- `hpa.yaml` — keep 2–8 @ 70% CPU, add `behavior`:
  ```yaml
  behavior:
    scaleUp:   { stabilizationWindowSeconds: 0,   policies: [{type: Pods, value: 2, periodSeconds: 30}] }
    scaleDown: { stabilizationWindowSeconds: 300, policies: [{type: Pods, value: 1, periodSeconds: 60}] }
  ```
- `pdb.yaml` — `minAvailable: 1` for api (2 is the HPA floor).
- `migrate-job.yaml` — `alembic upgrade head` as a Job run by CI **before** rolling the Deployment (fixes B7). Migrations follow expand → deploy → contract so old and new pods both work mid-rollout.
- `worker-deployment.yaml` — same secrets as API, resources, `/metrics` port, 1 replica (can go to 3 safely after Phase 6).
- `pgbouncer.yaml` — Deployment + Service (`edoburu/pgbouncer` or bitnami), `POOL_MODE=transaction`.
- `web-deployment.yaml` + Service for the React app.
- `ingress.yaml` — `/` → web, `/api` → api; TLS via cert-manager; `/metrics` not exposed.
- `secret.example.yaml` — template only; real secrets via `kubectl create secret` / Sealed Secrets / External Secrets. Never commit real values.
- Postgres: **managed (RDS/Cloud SQL) for prod**; for local use CloudNativePG operator or the Bitnami chart.

**Execute (local, kind)**
```sh
kind create cluster --name manthan
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
# (kind needs --kubelet-insecure-tls patched into metrics-server)
kind load docker-image manthan-api:dev manthan-worker:dev manthan-web:dev --name manthan
kubectl apply -k deploy/kubernetes/overlays/local
kubectl apply -f deploy/kubernetes/base/migrate-job.yaml && kubectl -n manthan wait --for=condition=complete job/manthan-migrate
kubectl -n manthan get hpa -w &
k6 run -e BASE_URL=http://localhost:8080 load-tests/stress-test.js
```

**Done when:** under `stress-test.js` the HPA scales 2 → 8 and back down; a rolling deploy during `load-test.js` shows 0 failed requests; killing a pod mid-test shows no 5xx spike beyond retries.

---

### Phase 9 — Pluggable payment gateway, production-shaped

**Changes** — `app/modules/payments/`
- `providers/` package: `base.py` (the existing `PaymentProvider` Protocol, extended with `create_order`, `verify_webhook(headers, body) -> WebhookEvent`, `get_status(reference)`), `mock.py` (current `MockProvider`), `juspay.py` / `razorpay.py` (adapters behind the same interface; sandbox credentials from secrets).
- `get_provider()` → registry keyed by `settings.payment_provider`; unknown name fails at startup.
- **Webhook endpoint** `POST /api/v1/payments/webhooks/{provider}`: verify signature, then apply the state transition **idempotently** (unique on `provider, provider_event_id`) using `FOR UPDATE` on the payment row. Gateway webhooks and the user's redirect can race — the lock + state machine (`pending → succeeded|failed → refunded`) makes order of arrival irrelevant.
- Outbound calls: `httpx.AsyncClient` with timeouts + retries on idempotent operations only; pass our payment id as the gateway idempotency key.
- **Reconciliation job** in the worker: payments `pending` > N minutes → `get_status()` from gateway.
- Contract test suite `tests/payments/test_provider_contract.py` parametrized over every registered provider (mock always; real ones with sandbox creds behind a marker).

**Done when:** switching `PAYMENT_PROVIDER=mock|<real>` needs no code change; duplicate/out-of-order webhooks are covered by tests.

---

### Phase 10 — React + TypeScript dashboard

**Stack:** Vite + React 18 + TypeScript (strict), React Router, TanStack Query, a component library (e.g. shadcn/ui or Mantine), **`openapi-typescript` + `openapi-fetch`** to generate a typed client from FastAPI's `/openapi.json` (so the 114 routes stay in sync with the frontend automatically).

**Layout:** `web/` at repo root.
```
web/
  src/api/schema.d.ts       # generated: npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts
  src/api/client.ts         # openapi-fetch + auth header + 401 → logout
  src/auth/                 # login, token storage (memory + refresh on reload), role/module guard
  src/routes/patient/       # catalogue, book appointment, my appointments, cart/checkout, payments
  src/routes/doctor/        # schedule, appointments, leaves
  src/routes/admin/         # per-module screens, shown only if the user holds that module
  src/routes/admin/ops/     # live ops: today's bookings, low-stock medicines, pending payments
```

**Scope for v1 (keep it small and demo-able):** login; patient booking flow (with 409 conflict handled nicely); admin pharmacy stock screen; ops dashboard with KPIs. Later: everything else.

**Quality:** ESLint + `tsc --noEmit` + Vitest + one Playwright e2e (login → book → see appointment) in CI.

**Done when:** `npm run build` produces a static bundle served by the `web` image; the typed client fails to compile if a backend schema changes incompatibly.

---

### Phase 11 — CI/CD in GitHub Actions

Rewrite `.github/workflows/checks.yml` into `ci.yml` with these jobs:

| Job | Runs | Notes |
|---|---|---|
| `lint` | `ruff check`, `ruff format --check`, `ty check` | fast fail |
| `unit` | `pytest -m "not postgres"` | SQLite, seconds |
| `integration` | `pytest -m postgres` | `services: postgres:17-alpine`, `TEST_DATABASE_URL` set |
| `concurrency` | `pytest tests/concurrency` | same Postgres service; separate job so failures are obvious |
| `migrations` | `alembic upgrade head` → `alembic downgrade base` → `upgrade head` on empty DB | catches broken downgrades |
| `web` | `npm ci && npm run lint && npm run typecheck && npm test && npm run build` | in `web/` |
| `images` | `docker/build-push-action` with `cache-from/to: type=gha`, targets `api`, `worker`, `web`; Trivy scan (fail on HIGH/CRITICAL) | needs all above |
| `smoke` | `docker compose up`, `k6 run load-tests/smoke-test.js` | reuse Jenkins smoke logic |
| `push` | push to GHCR tagged `sha-<short>` (+ `vX.Y.Z` on tags) | only on `main`/tags |
| `deploy` (optional) | `kustomize edit set image` + apply migrate Job + apply overlay | manual approval environment |

Add `concurrency: { group: ci-${{ github.ref }}, cancel-in-progress: true }`, and uv/npm caching. Decide whether Jenkins stays (duplicate) or is retired — see open questions.

**Done when:** a PR shows all jobs green; a deliberately broken lock (Phase 1 regression test) turns `concurrency` red.

---

## 5. SLOs and capacity targets (initial — revise after Phase 4 baseline)

| Metric | Target |
|---|---|
| Availability (API) | 99.9% monthly |
| p95 latency — catalogue reads | < 200 ms |
| p95 latency — booking / checkout | < 600 ms |
| Error rate (5xx) | < 0.5% |
| Double bookings / oversells | **0**, always (correctness, not an SLO) |
| Scale-out time 2 → 8 pods | < 3 min under stress ramp |
| Rolling deploy | 0 failed requests |

---

## 6. Suggested order and effort

| Order | Phase | Rough effort | Depends on |
|---|---|---|---|
| 1 | 0 — Postgres test harness | 0.5 day | — |
| 2 | 1 — Concurrency tests + hardening | 2 days | 0 |
| 3 | 2 — Pool-aware stateless API | 1.5 days | — |
| 4 | 3 — Logging + metrics + Grafana | 1.5 days | 2 (middleware) |
| 5 | 4 — Real k6 scenarios + baseline | 1.5 days | 3 |
| 6 | 7 — Multi-stage Docker | 0.5 day | — |
| 7 | 11 — CI (backend jobs first) | 1 day | 0, 1, 7 |
| 8 | 6 — Worker | 1 day | 1 |
| 9 | 5 — Redis cache/rate limit | 1.5 days | 2 |
| 10 | 8 — Kubernetes hardening + HPA demo | 2 days | 4, 7 |
| 11 | 9 — Payment gateway | 2 days | 6 |
| 12 | 10 — React dashboard v1 | 4–5 days | 2 (CORS) |

Total: roughly 3–4 focused weeks. Phases 0–4 + 7 alone make the core concurrency/testing/observability claims fully true (~8 days).

---

## 6a. Task breakdown — one branch, one PR each

Every task below is a **separate branch and a separate PR**, small enough to review in one sitting and to revert on its own.

### Branching and revert rules

- **Independent tasks** (`Base` = `main`) branch from the latest `main`.
- **Dependent tasks** are **stacked**: the branch is cut from its parent task's branch and the PR targets the parent branch. When the parent merges, the child is rebased onto `main` and retargeted to `main`, so each PR on `main` contains only its own change.
- **Merge with "Squash and merge".** Each task becomes exactly one commit on `main`, so `git revert <sha>` (or GitHub's *Revert* button) undoes one task cleanly.
- **Reverting a task that others depend on:** revert the dependents first (newest first), then the task. The `Depends on` column lists which ones.
- Each PR must leave `main` green: `ruff check`, `pytest` (plus `pytest -m postgres` once T01 lands).
- Schema changes come with a working `downgrade()`, so reverting the code can be paired with `alembic downgrade -1`.
- Branch names: `<type>/<tNN>-<slug>`, e.g. `test/t01-postgres-harness`.

### Tasks

| ID | Branch | What | Depends on | Needs decision |
|---|---|---|---|---|
| T00 | `docs/t00-scalability-plan` | Add this plan | — | — |
| **Phase 0 / 1 — correctness** |||||
| T01 | `test/t01-postgres-harness` | Testcontainers/`TEST_DATABASE_URL` fixture, Alembic-built schema, `postgres`/`concurrency` markers | — | — |
| T02 | `test/t02-concurrent-booking` | Real concurrent same-slot / overlapping-slot booking tests + direct-INSERT constraint backstop test | T01 | — |
| T03 | `test/t03-concurrent-pharmacy` | Oversell, lost-update (restock vs checkout), deadlock (A,B vs B,A), lock-regression test | T01 | — |
| T04 | `fix/t04-scoped-expiry` | Remove global sweeps from read paths; scoped release inside booking/checkout transactions | T02, T03 | — |
| T05 | `feat/t05-lock-tuning` | `FOR NO KEY UPDATE` on doctor; `SET LOCAL lock_timeout`; lock timeout → 409 | T02 | — |
| T06 | `feat/t06-idempotency-keys` | `Idempotency-Key` for booking & payment POSTs (+ migration) | T01 | — |
| **Phase 2 — stateless, pool-aware API** |||||
| T07 | `feat/t07-db-pool-settings` | Pool size/overflow/timeout, `statement_timeout`, PgBouncer flag, prod secret guard | — | — |
| T08 | `refactor/t08-asgi-middleware-lifespan` | Pure-ASGI request-id middleware (contextvar), lifespan (dispose engine), CORS, GZip | — | — |
| T09 | `feat/t09-health-probes` | `/health/startup`, readiness with 1 s DB timeout | — | — |
| T10 | `perf/t10-paginate-lists` | Replace `limit(500)` lists with pagination | — | — |
| T11 | `perf/t11-trigram-indexes` | `pg_trgm` + search/sweep indexes migration | T01 | — |
| **Phase 3 — observability** |||||
| T12 | `feat/t12-structured-logging` | JSON logs with request_id, access log, no PII | T08 | — |
| T13 | `feat/t13-prometheus-metrics` | `/metrics`, RED histograms by route template, DB pool gauges | T08 | — |
| T14 | `feat/t14-business-metrics` | Booking/checkout outcome counters, lock-wait histogram | T13 | — |
| T15 | `ops/t15-monitoring-stack` | Prometheus scrape config, alert rules, Grafana dashboard, compose `monitoring` profile | T13 | — |
| **Phase 4 — load testing** |||||
| T16 | `test/t16-k6-seed-auth` | Load-data seeder + k6 auth helper | — | — |
| T17 | `test/t17-k6-scenarios` | Realistic load, stress, contention, soak scripts + thresholds; replace perf placeholder | T16 | — |
| **Phase 7 / 11 — build & CI** |||||
| T18 | `build/t18-multistage-docker` | Multi-stage api/worker targets, non-root, drop old worker Dockerfile | — | — |
| T19 | `ci/t19-actions-postgres` | Actions: lint, unit, Postgres integration, concurrency, migration up/down | T01 | — |
| T20 | `ci/t20-image-build-push` | Buildx cache, Trivy scan, smoke, push | T18, T19 | #3, #4 |
| **Phase 6 — worker** |||||
| T21 | `feat/t21-worker-expiry-jobs` | Worker scheduler, `SKIP LOCKED` batch expiry, graceful shutdown | T04 | — |
| T22 | `feat/t22-notification-queue` | Event publishing + consumer | T21 | #2 |
| **Phase 5 — Redis** |||||
| T23 | `feat/t23-redis-optional` | Redis client in lifespan, fail-open dependency, compose service | T08 | — |
| T24 | `feat/t24-catalogue-cache` | Read-through catalogue cache + invalidation | T23 | — |
| T25 | `feat/t25-rbac-cache` | Cache `modules_for`, invalidate on grant/revoke | T23 | — |
| T26 | `feat/t26-rate-limiting` | Login/register/booking rate limits → 429 | T23 | — |
| **Phase 8 — Kubernetes** |||||
| T27 | `deploy/t27-kustomize-layout` | Move manifests to `base/` + `overlays/{local,prod}` (no behaviour change) | — | — |
| T28 | `deploy/t28-api-hardening` | Probes, preStop, resources, rollout strategy, HPA behavior, PDB, securityContext | T27, T09 | — |
| T29 | `deploy/t29-migrate-job-pgbouncer` | Migration Job, PgBouncer, worker secrets/resources | T27, T07 | #1 |
| T30 | `deploy/t30-ingress` | Ingress (`/` web, `/api` api), TLS | T27 | — |
| **Phase 9 — payments** |||||
| T31 | `feat/t31-payment-registry` | `providers/` package, settings-driven registry | — | — |
| T32 | `feat/t32-payment-webhooks` | Signed, idempotent webhook endpoint + state machine | T31 | — |
| T33 | `feat/t33-payment-reconcile` | Worker reconciliation job | T32, T21 | — |
| T34 | `feat/t34-gateway-adapter` | First real sandbox adapter + contract tests | T32 | #6 |
| **Phase 10 — dashboard** |||||
| T35 | `feat/t35-web-scaffold` | Vite + React + TS, generated OpenAPI client, lint/typecheck/test | — | #7 |
| T36 | `feat/t36-web-auth` | Login, token handling, role/module guards | T35 | — |
| T37 | `feat/t37-web-booking` | Patient booking flow with conflict handling | T36 | — |
| T38 | `feat/t38-web-admin-ops` | Pharmacy stock + ops KPI screens | T36 | — |
| T39 | `build/t39-web-image-ci` | Web Dockerfile + CI job | T35, T18 | — |

---

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| PgBouncer transaction mode + psycopg prepared statements → `prepared statement does not exist` errors | `prepare_threshold=None` when `use_pgbouncer`; integration test runs through PgBouncer in CI |
| Removing sweeps from the hot path delays slot release | Scoped release inside the booking/checkout transaction keeps exact behaviour; worker handles the rest |
| Cache serves stale data | Never cache stock/availability; short TTL + explicit invalidation on admin writes |
| Concurrency tests flaky | Use `asyncio.Barrier`, assert on final DB state (not timing), run each 5× in CI initially to shake out flakiness |
| Migrations break mid-rollout | Expand/contract migrations; migrate Job runs before Deployment update; `downgrade` tested in CI |
| HPA flaps | `behavior` stabilisation windows; requests set from measured usage |

---

## 8. Decisions needed from you (before execution)

1. **Postgres in prod:** managed (RDS / Cloud SQL / Neon) vs. in-cluster (CloudNativePG)? Recommendation: managed.
2. **Queue for notifications:** Redis Streams (recommended — Redis is already planned) vs. Postgres outbox + `LISTEN/NOTIFY` vs. a real broker.
3. **CI:** keep Jenkins alongside GitHub Actions, or move fully to Actions? Recommendation: Actions as the single source of truth; keep Jenkins only if it's needed for a demo.
4. **Registry:** Docker Hub (`rahulkmishra2806/manthan-api`, as Jenkins uses) or GHCR?
5. **Dormant modules** (`billing`, `prescriptions`, `medical_records`, `schedules`, `departments`, `notifications`, `audit`, `users`): finish and mount some of them, or leave as scaffolding?
6. **Real payment adapter:** which gateway sandbox to integrate first?
7. **Dashboard scope:** v1 as listed in Phase 10, or broader?

Once these are settled, execution starts at Phase 0, one PR per phase, each PR including its tests and a short note in `docs/` describing what changed.
