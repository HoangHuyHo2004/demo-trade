# Local development

## Prerequisites

- Docker + Docker Compose
- (Optional, for non-container dev) Python 3.12, Node 20+, pnpm 9

## Full stack, one command

```bash
cp .env.example .env
docker compose up --build
```

Then:

- Web:  http://localhost:3000
- API:  http://localhost:8000
- OpenAPI: http://localhost:8000/docs
- Health / Readiness: `/health`, `/ready`

The `api` container runs `alembic upgrade head` and `python -m scripts.seed`
on startup (idempotent), so a fresh Postgres volume works out of the box.

## Demo mode (default)

`DEMO_MODE=true` in `.env` gives you:

- The seeded demo user (`demo@demo-trade.local`)
- "Continue as demo user" button on `/signin` (Auth.js credentials provider)
- Deterministic mock market-data provider (US / VN / crypto + benchmarks)
- No paid API keys required

Turn it off (`DEMO_MODE=false`) for a production-shaped run — Auth.js
requires a real OIDC provider, the API refuses the demo cookie, and the
mock provider is not auto-selected.

## Backend only (Python)

```bash
cd services/api
python -m venv .venv
. .venv/Scripts/activate    # or `source .venv/bin/activate`
pip install -e .[dev]

# In another shell start Postgres + Redis via compose
docker compose up -d postgres redis

export DATABASE_URL=postgresql+asyncpg://demotrade:demotrade@localhost:5432/demotrade
export ALEMBIC_DATABASE_URL=postgresql://demotrade:demotrade@localhost:5432/demotrade
alembic upgrade head
python -m scripts.seed

uvicorn app.main:app --reload
```

## Frontend only (Next.js)

```bash
corepack enable    # first time
cd apps/web
pnpm install --no-frozen-lockfile
pnpm dev
```

Requires the API to be reachable at `NEXT_PUBLIC_API_BASE_URL`
(defaults to http://localhost:8000).

## Tests

Backend:

```bash
cd services/api
pytest
```

Frontend typecheck + lint + build:

```bash
pnpm -r typecheck
pnpm --filter web lint
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 AUTH_SECRET=dev-only-change-me-32chars-min-xxxxxxxxxx DEMO_MODE=true pnpm --filter web build
```

Playwright critical-flow E2E (needs the full stack running):

```bash
cd apps/web
pnpm e2e:install       # first-time: install Chromium
docker compose up -d   # bring up the stack in the background
pnpm e2e               # run the critical-flow suite
```

## Regenerating Alembic migrations

Never edit a migration once merged. To add a new one:

```bash
cd services/api
alembic revision -m "your description" \
  --autogenerate --rev-id "$(date -u +%Y%m%d)_$(printf '%04d' <next-number>)"
```

Review the generated file — SQLAlchemy autogenerate is a starting
point, not an authority. Every migration ships with a test that runs
`alembic upgrade head` from an empty DB (CI enforces this).

## Common issues

**pnpm complains about a version conflict.** Delete `~/.local/share/pnpm`
(or Windows equivalent) and re-enable Corepack: `corepack enable`. The
repo's `packageManager` field pins pnpm 9.12.0.

**"AUTH_SECRET not set" on the web build.** Set it in `.env`. Any random
32+ char string works for local development.

**Signal returns INSUFFICIENT_DATA.** By design when fewer than 10 bars
are available. The mock provider needs a lookback of at least ~90 days
to produce useful indicators.

**Anthropic tests hitting real API.** They shouldn't — tests set
`LLM_PROVIDER=mock` in conftest. If you see an outbound network call in
tests, that's a bug.

## Directory tour

- `apps/web` — Next.js 15 App Router UI
- `services/api` — FastAPI backend
- `services/worker` — Celery worker + beat
- `packages/contracts` — shared TS types
- `packages/config` — shared runtime config
- `infra/` — Dockerfiles
- `docs/` — everything you're reading
- `scripts/` — repo-level utilities

Under `services/api/app`:

- `api/v1/` — HTTP handlers (thin)
- `core/` — cross-cutting: config, logging, auth, middleware, redact
- `db.py` — async engine + session
- `domain/` — pure business types (asset id)
- `models/` — SQLAlchemy 2.0 ORM
- `providers/` — market-data adapters + calendars + registry
- `quant/` — pure indicator + model library (no I/O)
- `agent/` — LLM abstraction + tool executor + orchestrator
- `services/` — orchestration on top of models + providers
- `schemas/` — Pydantic request/response envelopes
