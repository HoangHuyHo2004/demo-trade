# DEMO-TRADE

AI-assisted, multi-market investment **research and trading-signal** platform.
Supports US equities, Vietnamese equities (HOSE/HNX/UPCOM), and spot crypto.

> **Educational/research use only.** Not investment advice. No real-money order execution
> is implemented, and none is planned for the MVP. See `docs/compliance-considerations.md`.

---

## Status: **Phase 1 — Foundation**

Implemented in this iteration:

- Monorepo layout (`apps/web`, `services/api`, `services/worker`, `packages/*`)
- Docker Compose local stack (Postgres + Redis + API + Worker + Web)
- Async FastAPI with structured logging, health/ready endpoints, versioned `/api/v1`
- SQLAlchemy 2.0 models + Alembic migrations for the Phase 1 entity set
- **Canonical asset identity** (`{ASSET_TYPE}:{MARKET}:{EXCHANGE}:{SYMBOL}`) and
  ambiguity-safe symbol resolution
- **Deterministic mock market-data provider** (US equity, VN equity, crypto,
  per-market benchmarks) — no external credentials required
- Watchlist CRUD (demo user)
- Market-status service with real market calendars (HOSE/HNX/UPCOM half-days deferred)
- Next.js 15 (App Router) + Tailwind + TanStack Query
- Dashboard, watchlist, asset detail (chart placeholder), i18n stubs (EN/VI)
- Mock auth (dev-mode demo user cookie)
- GitHub Actions CI (Python lint/type/test + web lint/type/build)
- Pytest suite for asset-id parsing, mock provider determinism, and API smoke

**Not yet implemented (deferred to later phases per spec §20):**

- Real provider adapters (Alpaca, SSI FastConnect, Coinbase) — interfaces exist,
  concrete adapters are placeholders that raise `NotImplementedError`
- Signal engine, backtester, signal laboratory (Phase 3)
- AI research agent, filings/news retrieval, prompt-injection defenses (Phase 4)
- Paper portfolio, VaR, stress tests (Phase 5)
- Playwright E2E, full a11y sweep, production auth (Auth.js/OIDC)
- pgvector, object storage

---

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- Web:      http://localhost:3000
- API:      http://localhost:8000
- OpenAPI:  http://localhost:8000/docs
- Health:   http://localhost:8000/health

The `api` service runs Alembic migrations and seeds demo assets on startup
(idempotent). The stack works entirely in **demo mode** — no external API keys.

## Local dev without Docker

Backend:

```bash
cd services/api
python -m venv .venv && . .venv/Scripts/activate   # or source .venv/bin/activate
pip install -e .[dev]
export DATABASE_URL=postgresql+asyncpg://demotrade:demotrade@localhost:5432/demotrade
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload
```

Frontend:

```bash
cd apps/web
pnpm install
pnpm dev
```

## Tests

```bash
# Python
cd services/api && pytest

# Web
cd apps/web && pnpm test
```

## Repository layout

```
apps/web              Next.js frontend
services/api          FastAPI backend (auth, providers, signals API surface)
services/worker       Celery worker + beat (ingest jobs)
packages/contracts    Shared TS types (asset id, signal payload shapes)
packages/config       Shared TS runtime config
infra                 Dockerfiles and infra manifests
docs                  Architecture, methodology, compliance docs
scripts               Repo-level utilities
tests                 Cross-service smoke tests
```

## Documents

- [`AGENTS.md`](AGENTS.md) — repo rules for AI collaborators & humans
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/data-providers.md`](docs/data-providers.md)
- [`docs/roadmap.md`](docs/roadmap.md)
- [`docs/compliance-considerations.md`](docs/compliance-considerations.md)
