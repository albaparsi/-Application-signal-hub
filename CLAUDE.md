# Application Signal Hub — Project Context

A privacy-first job application tracker. Detects recruiting-email signals
(interview invite, rejection, confirmation, offer) and proposes status
updates for user review — never applies them automatically.

This file exists so a fresh Claude Code session has the context that was
built up over a long planning conversation elsewhere. Read this before
making changes — several of the decisions below look arbitrary until you
know the reasoning.

## Stack

FastAPI + Python, PostgreSQL, SQLAlchemy 2.0, Alembic migrations, Docker
Compose, pytest. Single-user MVP — no auth yet. Free-text company/role
fields (no normalized lookup tables) by deliberate choice.

## Current status: Phases 1–3 complete, DB hardening done

- **Phase 1**: CRUD for `applications`, Docker Compose, base data model
  (`applications`, `application_events` timeline, `audit_log`).
- **Phase 2**: Status transition state machine (`app/transitions.py`) —
  invalid transitions return `409` unless `?force=true`. Search/filter/sort
  polish on `GET /applications`.
- **Phase 3**: Email signal pipeline — `app/classifier.py` (deterministic
  keyword rules, priority-ordered), `app/matcher.py` (conservative company
  inference + matching — never guesses), `app/email_service.py`
  (orchestration: dedup → classify → match → propose). New tables:
  `email_events`, `proposals`. Proposals require explicit approve/reject;
  approving goes through the same transition validation as Phase 2.
- **DB hardening**: Added `CHECK`/`UNIQUE` constraints to every model,
  mirroring the Python enums, then switched schema ownership from
  `Base.metadata.create_all()` to Alembic migrations entirely (see "Bugs
  already found" below for why this mattered).

## Not built yet (per original spec)

- Redis + async workers (Phase 5) — email ingestion is currently
  synchronous.
- Retries / dead-letter queue for failed processing (Phase 4).
- Structured logging / OpenTelemetry.
- Gmail OAuth — real email ingestion. Right now `/email-events/ingest`
  takes a JSON payload; there's a `sample_emails.json` +
  `scripts/seed_sample_emails.py` for synthetic testing.
- Browser extension (`activeTab` + manual "Save this application" flow —
  see original spec below).
- React dashboard.

## Real bugs already found and fixed — don't reintroduce these

1. **`create_all()` doesn't alter existing tables.** Early phases used
   `Base.metadata.create_all()` on app startup for dev convenience. When
   `CHECK` constraints were later added to the models, this silently did
   nothing on the already-running dev DB — the constraints were correct in
   Python and completely absent from Postgres. Fixed by moving to Alembic
   as the sole source of schema truth; `docker-compose.yml`'s `api`
   service now runs `alembic upgrade head` before starting the server.
   **Lesson: any future schema change needs an Alembic migration
   (`alembic revision --autogenerate -m "..."`), reviewed by hand, not a
   reliance on the ORM auto-creating things.**

2. **SQLite hides Postgres bugs.** `GET /applications/{malformed-id}`
   crashed with an unhandled `500` on real Postgres (native `UUID` column
   type rejects non-UUID strings before the query even runs) but appeared
   to work fine on SQLite (which degrades the column to a plain string).
   Fixed by validating path-param IDs as `UUID` at the FastAPI route level.
   **Lesson: the test suite can run against both engines
   (`DATABASE_URL=postgresql+psycopg2://... pytest`) — do that before
   trusting any change that touches ID handling or column types.**

## Design decisions worth knowing before changing things

- **Two history tables, not one**: `application_events` is the
  user-facing timeline; `audit_log` is a stricter system-facing trail
  (actor/action/before-after JSON). Keep this split — don't collapse them.
- **Status transitions are a real state machine**
  (`app/transitions.py`), not free-form. Terminal states (`rejected`,
  `withdrawn`) block outgoing transitions unless `force=true` is passed
  explicitly.
- **Email matching never guesses.** Zero matches → `unmatched`. Multiple
  candidates → `ambiguous`. Either way, no proposal is created. This is a
  deliberate privacy/trust property of the whole system — don't "improve"
  the matcher to be more aggressive without discussing it first.
- **`EmailEvent` never stores the full email body** — only a
  300-char `body_excerpt`, enforced both by column type (`VARCHAR(300)`,
  Postgres-only) and an explicit `CHECK (length(...) <= 300)` (works on
  both engines). This is intentional privacy minimization, not an
  oversight — don't widen it casually.
- **Proposals are never auto-applied.** Approving one runs through the
  exact same `validate_transition()` logic as a manual status change.

## Testing conventions

- `pytest` defaults to in-memory SQLite (fast).
- `DATABASE_URL=postgresql+psycopg2://signalhub:signalhub@localhost:5433/signalhub_test pytest`
  runs the same suite against real Postgres — do this for any change
  touching models, migrations, or ID/UUID handling. (Host port is 5433, not
  Postgres' default 5432 — see docker-compose.yml's comment: a native
  Postgres install commonly already owns 5432 on the host.)
- `tests/test_db_constraints.py` inserts invalid data directly through the
  ORM (bypassing Pydantic) specifically to prove DB-level constraints are
  real, not just app-level validation.

## Original product spec (for context on where this is headed)

Two opt-in integrations planned beyond the current API:

1. **Browser extension** — manual, user-triggered capture only.
   `activeTab` + `scripting` permissions (not broad host permissions).
   User clicks "Save this application" → extension extracts page data →
   shows a preview (company/role/url/location/date) → user confirms →
   record created. Never auto-saves invisibly.
2. **Email integration** — currently synthetic/manual POST via
   `/email-events/ingest`. Eventually Gmail OAuth with narrow permissions
   and a clear disconnect/delete-data flow.

Permission model philosophy: least privilege always. MVP extension uses
`activeTab` only; V2 adds optional host permissions for specific
supported job sites; V3 adds opt-in Gmail OAuth. Never request "read and
change all data on all websites."
