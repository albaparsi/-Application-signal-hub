# Application Signal Hub

A privacy-first job application tracker. Detects recruiting-email signals
(interview invite, rejection, confirmation, offer) and proposes status
updates for review, it never applies them automatically.

## About this project

I built this using [Claude Code](https://claude.com/claude-code) as an
AI pair-programmer. I directed the architecture and product decisions,
reviewed and tested every change against a real Postgres database and
the actual running app (not just unit tests), made the calls on
trade-offs (least-privilege browser extension permissions, where an LLM
call was and wasn't the right tool, when to add database constraints,
what to cut from scope), and debugged real issues that came up along the
way, including a schema-drift bug between the ORM and Postgres, and a
local port conflict with an existing Postgres install. Claude handled a
lot of the implementation; the engineering judgment, testing, and
decisions are mine. 

## What's here

- **Applications API**: CRUD with a user-facing timeline
  (`application_events`) kept separate from a stricter system audit trail
  (`audit_log`), a real status-transition state machine (invalid
  transitions return `409` unless explicitly forced), and search/filter/
  sort on `GET /applications`.
- **Email signal pipeline**: deterministic keyword-based classification
  (`app/classifier.py`) and conservative company matching
  (`app/matcher.py`) that never guesses: zero or ambiguous matches
  produce no proposal. Proposals require explicit approve/reject; nothing
  is ever auto-applied.
- **Browser extension**: (`extension/`), Manifest V3, least-privilege
  permissions (`activeTab` + `scripting` only). One click captures the
  job posting you're viewing, pre-fills company/role/location/status via
  server-side LLM-assisted extraction (falling back to page structured
  data, then local heuristics), and saves only on explicit confirmation.
- **Dashboard**: (`dashboard/`), a read-only web view for searching,
  filtering, and sorting saved applications, with a per-application
  timeline.
- **Database hardening**: `CHECK`/`UNIQUE` constraints mirroring every
  Python enum, enforced at the Postgres level (not just app-level
  validation), with Alembic migrations as the sole schema source of
  truth.

## Stack

FastAPI, PostgreSQL, SQLAlchemy 2.0, Alembic, Docker Compose, pytest for
the backend; a plain HTML/CSS/JS dashboard and a Manifest V3 browser
extension on the frontend; Anthropic's Claude API for LLM-assisted
extraction. Single-user, no auth yet, free-text company/role fields by
deliberate choice (no normalized lookup tables at this stage).

## Getting started

```bash
cp .env.example .env
docker compose up --build
```

API docs: http://localhost:8000/docs
Dashboard: http://localhost:8080

`ANTHROPIC_API_KEY` in `.env` is optional, without it, the extension's
extraction falls back to page structured data and local heuristics
instead of an LLM call. See `extension/README.md` to load the browser
extension itself.

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

(Host port is 5433, not Postgres' default 5432 — a native Postgres
install commonly already owns 5432, so `docker-compose.yml`'s `db`
service avoids the collision.)

## Running tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

Defaults to in-memory SQLite. Run the same suite against real Postgres
for any change touching models, migrations, or ID/UUID handling:

```bash
DATABASE_URL=postgresql+psycopg2://signalhub:signalhub@localhost:5433/signalhub_test pytest
```

## Design notes / trade-offs

- **Free-text company/role**, not normalized lookup tables: simpler for
  an MVP. Revisit if/when company-level analytics or autocomplete matter
  enough to want a `companies` table.
- **No auth yet**: single-user assumption. Every model has room for a
  `user_id` column later without restructuring.
- **Two history tables, not one**: the timeline (`application_events`) is
  user-facing; the audit log is a stricter system trail (actor/action/
  before-after). Kept separate on purpose.
- **Email matching never guesses**: a deliberate privacy/trust property
  of the whole system, not a limitation to "fix" by making it more
  aggressive.
- **SQLite for fast tests, Postgres for fidelity**: SQLite hides real
  Postgres-only bugs (native `UUID` columns, `JSONB` behavior), that's
  why the suite can run against both.
