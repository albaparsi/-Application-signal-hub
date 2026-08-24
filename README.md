# Application Signal Hub

A privacy-first job application tracker. This repo is being built in phases:

- **Phase 1 (this phase):** Project scaffold, Docker Compose, data model, CRUD API for applications.
- **Phase 2:** Status transitions, timeline/audit history, search & filters.
- **Phase 3:** Synthetic email ingestion, deterministic classification, conservative matching, proposals.
- **Phase 4:** Idempotency, retries, dead-letter queue, PII-safe structured logging.
- **Phase 5:** Redis + background workers for async email processing.
- **Phase 6+:** React dashboard, Gmail OAuth, browser extension backend, OpenTelemetry.

## Phase 1 scope

- `applications`: the core record (company, role, url, location, status, source, dates, notes).
- `application_events`: append-only timeline of everything that happens to an application (created, status changes, notes). This table is the foundation Phase 3 will reuse when email-driven proposals get *approved* and turn into timeline entries.
- `audit_log`: a separate, stricter trail of *who/what changed state and why* (actor, action, before/after). Kept separate from the timeline because the timeline is user-facing ("what happened to my application") while the audit log is a compliance/debugging trail (system-facing).

Two tables (`events` + `audit_log`) instead of one is a deliberate design choice: it keeps the user-facing timeline clean and readable while still giving you a rigorous audit trail underneath. Phase 3's `email_events` and `proposals` tables will slot in alongside these without changes to what's built here.

## Getting started

```bash
cp .env.example .env
docker compose up --build
```

API docs: http://localhost:8000/docs
Dashboard: http://localhost:8080

See `extension/README.md` to load the browser extension for one-click
saving from a job posting.

## Database migrations

Schema is owned by Alembic, not SQLAlchemy's `create_all()`. The `api`
container runs `alembic upgrade head` automatically before starting the
server. When you change a model, generate a migration and review it by
hand before committing:

```bash
cd backend
DATABASE_URL=postgresql+psycopg2://signalhub:signalhub@localhost:5433/signalhub \
  alembic revision --autogenerate -m "describe the change"
```

(Host port is 5433, not Postgres' default 5432 — see
`docker-compose.yml`'s `db` service.)

## Running tests

Tests use an in-memory SQLite database for speed (no Docker required):

```bash
cd backend
pip install -r requirements.txt
pytest
```

## Design notes / trade-offs made in Phase 1

- **Free-text company/role** (not normalized lookup tables): simpler for MVP, per project decision. Revisit if/when you want company-level analytics (e.g. "how many applications at each company") or autocomplete; that would want a `companies` table.
- **No auth yet**: single-user assumption for MVP. Every model already has room to add a `user_id` column later without restructuring, but no auth middleware exists yet.
- **Status transitions are currently unrestricted**: the API lets you set any status directly (e.g. `saved` → `offer`). Phase 2 is where we should decide whether to enforce a state machine (e.g. disallow `rejected` → `interview`) or keep it permissive since real job searches don't always move linearly.
- **SQLite for tests, Postgres for dev/prod**: deliberate speed/fidelity trade-off. If you hit Postgres-specific bugs (e.g. JSONB behavior) that SQLite hides, we should add a docker-based integration test tier in Phase 4.
