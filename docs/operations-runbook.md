# Operations runbook

## Health & readiness

| URL                                | Should return |
| ---------------------------------- | ------------- |
| `GET /health`                      | `{"status":"ok"}` |
| `GET /ready`                       | `{"status":"ready","checks":{"database":"ok"}}` |
| `GET /api/v1/providers/status`     | 200 with the mock adapter at minimum |
| `GET /api/v1/markets/status`       | 200 with 5 calendars |

If `/ready` returns 503, the container should be considered unhealthy
by the load balancer.

## Common incidents

### 1. `/ready` failing: database

Check the `checks.database` field for the error class.

- `OperationalError` → managed DB unreachable. Escalate to DBaaS status.
- `ProgrammingError` → migration drift. Run `alembic current` in the api
  container vs `alembic heads`.

Recovery: rollback the failing release; run `alembic upgrade head`
manually only when a DBA is present.

### 2. Bar ingest stalled

Symptom: freshness badges on the frontend are red across the board.

Check:
```sql
SELECT provider, status, count(*), max(started_at)
FROM bar_ingest_runs
WHERE started_at > now() - interval '1 hour'
GROUP BY 1, 2 ORDER BY 4 DESC;
```

If provider status is `error`, inspect the last row's `message` field.
The Celery worker (`worker.tasks.refresh_bars`) logs the exception with
`bar_fetch_failed`; pull the last hour of worker logs.

### 3. Agent turns failing / abstaining

`GET /api/v1/agent/runs/{id}` returns the full run. Look at:
- `status` — `budget_exceeded` / `error` / `abstained`
- `tool_call_count`, `input_tokens`, `output_tokens`, `cost_usd_micro`
- The linked `tool_calls` rows (join by `run_id`) for the specific
  tool that failed

If Anthropic is unreachable, the orchestrator returns a structured
abstain — this is expected, not a page-level incident.

### 4. Rate-limiter thundering herd

If a single client is repeatedly hitting `429`, verify from the audit:

```sql
SELECT actor, event, count(*)
FROM audit_logs
WHERE created_at > now() - interval '10 minutes'
GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 20;
```

Cap the offending client at the edge; a permanent block belongs in the
WAF, not in application code.

### 5. Cost / token spike (agent)

```sql
SELECT llm_provider, sum(cost_usd_micro) / 1e6 AS usd,
       sum(input_tokens) AS in_tok, sum(output_tokens) AS out_tok, count(*)
FROM agent_runs
WHERE started_at > now() - interval '1 hour'
GROUP BY 1;
```

Lower `max_output_tokens` and `max_tool_calls` in
`orchestrator.py::Budget` if a specific user or route is dominating.
The per-request overrides (`max_tool_calls`, `max_output_tokens` in the
chat request body) are additive on TOP of these — verify the client
isn't setting them higher than intended.

## Backups

- Managed Postgres snapshots handle everything.
- Weekly restore test: create a scratch DB from the latest snapshot,
  point `DATABASE_URL` at it, run `alembic upgrade head`, then
  `pytest tests/test_api_smoke.py`. Any failure blocks the on-call from
  going off-shift.

## Retention (recommended)

| Table                     | Retention  |
| ------------------------- | ---------- |
| `price_bars`              | keep forever (audit trail) |
| `bar_ingest_runs`         | 30 days    |
| `quotes`                  | 30 days    |
| `signals` + `signal_factors` | keep forever (research history) |
| `backtest_runs` + child rows | 90 days |
| `agent_runs` + `tool_calls` | 90 days  |
| `audit_logs`              | 400 days (compliance-friendly default) |

## Deployment cutover

Zero-downtime for the api: enable rolling restart in your orchestrator.
For migrations that add columns, deploy the migration in the release
BEFORE the code that uses it. For destructive changes, ship in two
releases (add-then-drop, one release apart), same as any production
schema change.

## Escalation

- On-call primary: engineer with commit access
- Data-provider outages: see `docs/data-providers.md` for the fallback
  order — the mock provider is always available.
- Compliance / legal question in a live incident: pause the affected
  flow and file a ticket; do not "just fix it".
