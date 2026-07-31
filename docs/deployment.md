# Deployment

This document is an **engineering checklist**, not a turnkey production
playbook. Anything marked "TODO" is a real blocker before non-demo use.

## Minimum production topology

```
                    ┌──────────┐
                    │  CDN /   │  (TLS termination, WAF, static assets)
                    │  Edge    │
                    └────┬─────┘
                         │
              ┌──────────▼──────────┐
              │   Reverse proxy     │  Caddy / nginx / envoy
              │   (per-service TLS) │
              └──┬──────────────┬───┘
                 │              │
        ┌────────▼────┐   ┌─────▼────────┐
        │  Next.js    │   │   FastAPI    │
        │  (web)      │   │   (api)      │
        └────────────┬┘   └───┬──────────┘
                     │        │
                     ▼        ▼
                 ┌───────────────────┐
                 │  Managed Postgres │
                 │  (backups + PITR) │
                 └─────────┬─────────┘
                           │
                 ┌─────────▼─────────┐
                 │      Redis        │
                 │  (rate-limit + Celery broker) │
                 └───────────────────┘
                           │
                 ┌─────────▼─────────┐
                 │   Celery worker   │
                 │     + beat        │
                 └───────────────────┘
```

## Environment variables

Copy `.env.example` and populate. **Never commit the resulting `.env`.**
See the reference in the repo root.

The variables that MUST be set differently for production:

- `APP_ENV=production` — enables HSTS and stricter defaults
- `DEMO_MODE=false` — refuses to auto-create the demo user
- `API_SECRET_KEY` — 32+ random bytes; rotate on incident
- `USE_MOCK_PROVIDERS_ONLY=false` — production must rely on real adapters
- `DATABASE_URL`, `ALEMBIC_DATABASE_URL` — pointing at managed Postgres
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` — separate DBs
- `API_CORS_ORIGINS` — comma-separated allow list (no `*` in production)
- `ANTHROPIC_API_KEY` (only if `LLM_PROVIDER=anthropic`)
- Provider keys as needed (`ALPACA_*`, `SSI_FC_*`)

## Build & run

Local dev remains:

```bash
docker compose up --build
```

For production, build the two service images and run them behind the
reverse proxy. Suggested tags:

```bash
docker build -t demo-trade/api:latest   -f infra/api.Dockerfile .
docker build -t demo-trade/web:latest   -f infra/web.Dockerfile .
```

Run the worker from the same api image (it already carries the worker
code):

```bash
docker run --env-file .env demo-trade/api:latest \
  celery -A worker.celery_app:app worker -B --loglevel=INFO
```

## TLS

Terminate at the edge (Caddy example):

```
demo-trade.example.com {
  reverse_proxy web:3000
}
api.demo-trade.example.com {
  reverse_proxy api:8000
}
```

The API middleware sets `Strict-Transport-Security` only when
`APP_ENV=production`.

## Database

- Managed Postgres 16+.
- Point-in-time recovery enabled; retention ≥ 7 days.
- Alembic migrations run on release from the api image:
  `alembic upgrade head`. Run once per release; CI verifies from-empty
  compatibility (`.github/workflows/ci.yml`).

## Authentication

Auth.js v5 in the Next.js app issues HS256-signed JWT session cookies
using a shared `AUTH_SECRET`. FastAPI (`app/core/auth.py`) verifies the
same token with PyJWT — no round-trip to the web app is needed.

Requirements for production:

- `AUTH_SECRET` — 32+ random bytes (`openssl rand -base64 32`). Must be
  **identical** in the web and api containers; docker-compose does this
  automatically via env-var interpolation.
- `AUTH_GITHUB_ID` + `AUTH_GITHUB_SECRET` — register a GitHub OAuth App
  with callback URL `https://your-host/api/auth/callback/github`.
- `AUTH_URL` — canonical origin of the web app (e.g. `https://demo-trade.example.com`).
- `DEMO_MODE=false` — closes the demo-login endpoint and the
  auto-provision fallback in `deps.get_current_user`.

Cookie flags:
- `HttpOnly`, `SameSite=Lax`, `Secure` in production (set automatically
  when `APP_ENV=production`).
- Cookie name is configurable via `AUTH_COOKIE_NAME`; defaults to
  `demo-trade.session`.

Cross-origin cookie: the web (e.g. `demo-trade.example.com`) and api
(`api.demo-trade.example.com`) must share an eTLD+1 so the browser sends
the session cookie to both. Set cookie `Domain=.demo-trade.example.com`
in `apps/web/src/auth.ts` when you promote past `localhost`. Same-origin
deployment (Next.js reverse-proxying `/api/v1/*` to FastAPI) sidesteps
this and is the simplest topology.

Adding another OIDC provider: import from `next-auth/providers/{name}`
and push into the `providers` array in `apps/web/src/auth.ts`. The API
side needs no changes — providers appear as the `provider` claim in the
JWT and are stored on `users.oauth_provider`.

## Observability

- Structured JSON logs (`app/core/logging.py`) — ship stdout to your log
  pipeline of choice.
- Request IDs are attached automatically (`RequestIdMiddleware`); pass
  them from the edge (`X-Request-Id`) and they'll be echoed back.
- Health: `GET /health` (liveness), `GET /ready` (readiness — checks DB).
- **TODO:** OpenTelemetry traces + Prometheus metrics endpoint. The
  middleware layout leaves clear insertion points.

## Rate limits

- `RateLimitMiddleware` uses Redis when available and falls back to an
  in-memory limiter otherwise. Multi-process deployments MUST have Redis
  reachable — the in-memory limiter is per-process and won't give a
  consistent global cap.
- Overrides live in the class-level `_RULES` dict. Change with a code
  release; a runtime config is a Phase 5.1 backlog item.

## Backups + restore

- Managed Postgres handles snapshot + PITR.
- Weekly test-restore into a scratch DB; run `alembic upgrade head` and
  a smoke pytest run against the restored data.
- `bar_ingest_runs` and `agent_runs` grow the fastest; plan retention
  (e.g. TTL 30 days for tool_calls, 90 days for agent_runs).

## Feature flags

None in Phase 5. When adding them, gate behavior server-side; the
frontend must never assume a feature is active based on client-side
config alone.

## Rollback

- Prefer **forward fixes** for shipped migrations. If you must roll back,
  the migration must be idempotently downgradable.
- App rollback is a container-tag change; DB rollback is a Postgres
  restore. Never do the DB restore automatically.
