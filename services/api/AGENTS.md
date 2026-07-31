# AGENTS.md — services/api

Extends the root `AGENTS.md`. In case of conflict, the root wins.

## Structure

- `app/main.py` — FastAPI app + middleware + router registration.
- `app/core/` — config, logging, redaction; nothing here imports from `app/api/`.
- `app/db.py` — async engine + session; single source of truth for DB access.
- `app/domain/` — pure business types (canonical asset id). Zero I/O.
- `app/models/` — SQLAlchemy 2.0 ORM. Alembic migration must accompany changes.
- `app/providers/` — external data adapters + calendar helpers. Business
  code depends only on `providers/base.py`.
- `app/services/` — orchestration on top of models + providers.
- `app/schemas/` — Pydantic request/response envelopes.
- `app/api/v1/` — HTTP routes. No business logic beyond argument
  validation, calling a service, and shaping the response.

## Rules specific to this service

- All timestamps returned by the API are UTC ISO-8601.
- Numeric prices are transported as `Decimal` (JSON string) so precision
  is preserved.
- Provider calls happen only from `app/services/` or `app/api/`, not from
  request handlers via ad-hoc `httpx` calls.
- New endpoints must be added to a versioned prefix (`/api/v1`, `/api/v2`, …).
  A breaking change is a new prefix; do not mutate in place.
- Every route needs at least one integration test in `tests/`.
