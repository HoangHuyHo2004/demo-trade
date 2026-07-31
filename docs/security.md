# Security

This document is a **map** of the security controls in the app plus the
known residual risks. It cross-references, rather than duplicates,
`docs/agent-security.md` (agent-specific), `docs/compliance-considerations.md`
(regulatory posture), and `docs/model-risk-management.md` (signal models).

## What we protect

1. **User data** — email, portfolio composition, watchlist contents,
   agent chat history.
2. **Session credentials** — the shared `AUTH_SECRET`, the
   Auth.js-issued HS256 JWT, the demo-user cookie.
3. **Provider credentials** — `ALPACA_API_KEY/SECRET`, `SSI_FC_*`,
   `ANTHROPIC_API_KEY`. Must never appear in browser bundles or logs.
4. **DB integrity** — no cross-user reads of portfolios / agent runs /
   jobs.

## Boundaries

- **Browser** knows only `NEXT_PUBLIC_*` env vars. Every other secret
  is server-side.
- **Web (Next.js)** verifies session cookies + issues them via Auth.js.
  Never talks to provider APIs directly.
- **API (FastAPI)** verifies session cookies (HS256 JWT with shared
  `AUTH_SECRET`), enforces ownership on every state-changing route,
  and is the only tier that talks to market-data providers or the LLM.
- **Worker (Celery)** shares the API's SQLAlchemy models + provider
  registry. Same secret handling rules.

## Authentication

- Auth.js v5 in the web app. Providers registered based on env vars:
  GitHub OIDC (`AUTH_GITHUB_ID/SECRET`) and a "demo credentials"
  provider active only when `DEMO_MODE=true`.
- Custom `jwt.encode/decode` emits HS256-signed JWTs (not the default
  JWE) so the FastAPI backend can verify with PyJWT + the same
  `AUTH_SECRET`.
- Session cookie: `HttpOnly`, `SameSite=Lax`, `Secure` in production,
  name is configurable (`AUTH_COOKIE_NAME`, default
  `demo-trade.session`).
- Session TTL: 7 days by default (`AUTH_SESSION_MAX_AGE_S`). The API
  refuses tokens whose `exp` exceeds max_age by more than 60s (defense
  against a leaked secret minting long-lived tokens).
- Bearer JWT header (`Authorization: Bearer …`) also accepted for
  server-to-server clients and tests.

## Authorization

Every state-changing route reads `CurrentUserDep` (from `app/deps.py`).
Ownership is enforced in the handler:

- Watchlists: `user_id` unique constraint on `(user_id, name)`; a
  watchlist row is only returned/mutated when its `user_id` matches.
- Portfolios: same.
- Jobs: `GET /jobs/{id}` refuses if `job.user_id != current_user.id`
  (except anonymous jobs where `user_id` is null).
- Agent runs: same as jobs.
- Settings: implicit — the row is looked up by `user_id`.

## Transport + headers

Middleware chain (outermost first, see `app/main.py`):

1. `CORSMiddleware` — allowlisted origins from `API_CORS_ORIGINS`
2. `SecurityHeadersMiddleware` — sets `Content-Security-Policy`,
   `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
   `Referrer-Policy: no-referrer`, `Permissions-Policy` (camera / mic /
   geolocation / payment disabled), `Cross-Origin-Opener-Policy:
   same-origin`, `Cross-Origin-Resource-Policy: same-origin`. Adds
   `Strict-Transport-Security` in production only.
3. `RateLimitMiddleware` — Redis when reachable, in-memory fallback.
4. `RequestIdMiddleware` — echoes `X-Request-Id`, binds it into
   structured-log context.

## Input validation

- Every request body is a Pydantic model. `extra="forbid"` on agent
  tool schemas (see `docs/agent-security.md`).
- Path parameters use FastAPI's typing so `int` params can't be
  coerced from arbitrary strings.
- SQL: SQLAlchemy 2.0 async with parameterized queries only. No raw
  SQL from user input.

## Secrets

- No secret is committed. `.env.example` documents the shape.
- No secret is embedded in the browser bundle. Frontend reads
  `NEXT_PUBLIC_*` only.
- Logs and agent tool-call summaries pass through
  `app/core/redact.py` — regex-scrubs API keys, `Authorization:`
  headers, and email addresses.
- The demo user's email is scrubbed from tool-call result summaries
  (asserted by test).

## Agent-specific

See [`docs/agent-security.md`](agent-security.md) in full. Highlights:

- Tool allowlist enforced by the executor; unknown tools = hard error.
- Every tool result is wrapped in a delimited
  `<untrusted_source>...</untrusted_source>` block before the model
  sees it. The system prompt tells the model that content inside those
  blocks is **data**, never instructions.
- Per-turn budgets: max tool calls (10), max output tokens (1500), max
  wall-clock (30s), max cost (~$0.20). Exceeding aborts with a
  structured abstain.
- No shell tool. No arbitrary SQL. No portfolio-mutating tool. No
  order-placement tool.
- `search_*` tools are skeletons that return `status: not_available`
  so the agent abstains honestly rather than fabricating citations.

## Rate limiting

- Redis-backed (auto-fallback to in-memory if Redis is unreachable —
  which is unsafe across multiple replicas; multi-process production
  MUST have Redis).
- Bucket key: `demo_user` cookie value if present, else client IP.
- 429 responses carry a `Retry-After` header and a JSON body naming
  the rule and window.

## Audit

Written to `audit_logs` table:

- `portfolio_created`, `portfolio_transaction_added`
- `auth_demo_login`
- `agent_turn_completed` (with usage + status)

Rows carry `actor` (`user:{id}` or `agent` / `worker`), `event`,
`subject_type`, `subject_id`, JSON payload, timestamp.

## Prompt-injection defenses (tested)

- `tests/test_agent_orchestrator.py::test_prompt_injection_payload_in_tool_result_is_wrapped_and_ignored`
- `tests/test_agent_orchestrator.py::test_agent_never_produces_a_score_the_engine_didnt_return`

The mock LLM guarantees these by construction (it only echoes tool
results). A real Claude deployment additionally needs the offline
evaluator described in `docs/agent-security.md` — Phase 4.1 backlog.

## Known residual risks

- **Cross-origin session cookie in production.** Requires web + api on
  the same eTLD+1 with `Domain=.example.com`, or a Next.js reverse
  proxy for `/api/v1/*`. `docs/deployment.md` covers this.
- **In-memory rate limiter fallback** is per-process; use Redis in
  production for consistent global caps.
- **Confidence calibration is heuristic**, not empirical (Phase 5.3
  backlog).
- **No CSRF token** — the SameSite=Lax cookie is the current defense.
  Adding a token for state-changing routes is worth doing before a
  public launch.
- **No account lockout on repeated failed sign-ins** — deferred to
  Auth.js provider-level configuration.
- **No content-security-policy on the Next.js pages** — the API's CSP
  is strict, the web app's default is looser to allow Tailwind/JIT.
  Add a page-level policy before production traffic.
