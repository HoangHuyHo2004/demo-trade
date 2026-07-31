# AI research agent

This document explains **what the agent does and how a user experiences
it**. For the security threat model + defenses, see
[`docs/agent-security.md`](agent-security.md).

## What the agent is

A single research agent (spec §13) driven by an LLM through an
allowlisted, typed tool interface. It can:

- Resolve an asset by ticker or company name
- Look up the last quote, historical bars, computed indicators
- Ask the **quantitative signal engine** for a directional signal (it
  cannot generate one itself)
- Run a walk-forward backtest
- Compare 2–5 assets
- Explain the result to the user, distinguishing verified facts from
  its own interpretation

## What the agent is **not**

- **Not** a source of prices or signals. All numeric output is a copy
  of what a tool returned. The mock LLM guarantees this by construction
  (it never free-texts on top of tool results); a production Claude
  deployment enforces it via the system prompt and the offline evaluator
  (backlog).
- **Not** an autonomous trader. There is no order-placement tool. No
  portfolio-mutating tool. The `search_*` tools that would introduce
  external content are Phase 4.1 skeletons that return
  `status: not_available` today, so the agent abstains honestly rather
  than fabricating citations.

## LLM providers

Configured via `LLM_PROVIDER`:

| Value       | Model                | Default when                                    |
| ----------- | -------------------- | ----------------------------------------------- |
| `mock`      | `mock-agent-v1`      | Demo mode + CI. Deterministic script. No key.   |
| `anthropic` | `claude-sonnet-5`    | `ANTHROPIC_API_KEY` set. Real tool-use loop.    |

The `mock` provider is the CI default because it runs offline and is
deterministic — tests can assert exact behavior. It is also the demo
default so `docker compose up` needs no key.

## Tool allowlist

Registered in `services/api/app/agent/tools.py::ALLOWED_TOOLS`. Every
tool has a Pydantic argument schema with `extra="forbid"`.

**Live** (backed by real handlers):

- `resolve_asset` — search across US / VN / crypto
- `get_market_status`
- `get_quote`
- `get_historical_bars`
- `get_calculated_indicators`
- `calculate_signal` — the only source of directional signals
- `run_backtest`
- `compare_assets`

**Skeletons** (spec §13 — return `status: not_available` in this build):

- `search_sec_filings`
- `search_vietnam_disclosures`
- `search_company_announcements`
- `search_crypto_project_announcements`
- `search_approved_news_sources`

When these tools ship for real (Phase 4.1), they will:

1. Fetch through the SSRF-safe HTTP helper (`app/providers/_http.py`)
   with a per-adapter host allowlist.
2. Persist retrieved documents in the `sources` table (already in
   the schema since 20260803_0004) + `document_chunks` with pgvector
   embeddings.
3. Return citations that reference `sources.id`, so the agent's
   `ResearchResponse.citations` are traceable in the DB.

## Structured response

Every agent turn returns a `ResearchResponse` (schema in
`services/api/app/agent/schemas.py`). Fields:

- `asset_canonical_id`
- `executive_summary` (1-2 sentences, non-recommendation language)
- `current_trend` (from the signal engine's regime output)
- `signal_summary` (formatted signal engine output)
- `bull_case[]`, `bear_case[]` (from signal factors)
- `key_risks[]`, `upcoming_catalysts[]`, `data_quality_warnings[]`
- `verified_facts[]` — anything that came directly from a tool
- `interpretation[]` — the agent's synthesis; visually distinct in UI
- `assumptions[]`, `unknowns[]`
- `suggested_questions[]`
- `citations[]` — `SourceCitation` with `kind` = `system` |
  `quantitative` | `filing` | `disclosure` | `news` | `project`
- `abstained`, `abstention_reason`

## Abstention

The agent is instructed to abstain (`abstained: true`) when:

- Sources conflict materially
- A `search_*` tool returned `not_available` but the user asked for
  filings/news
- The signal engine returned `INSUFFICIENT_DATA`
- The model output isn't a valid `ResearchResponse` JSON
- A per-turn budget is exceeded (`status: budget_exceeded`)

The UI shows an amber "Agent abstained" banner in these cases with the
reason.

## User surfaces

- **Research chat** (`/research`) — free-form conversation, one turn
  per submit. Includes an "Agent · run #N · status ok" header per turn.
- **Asset detail** — "Research chat →" link jumps to
  `/research?asset={id}`, pre-selecting the asset context.
- **Signal card** — the quantitative output is rendered separately
  from any AI interpretation. Factor contributions come from the
  signal engine, never the LLM.

## Audit trail

Every turn writes:

- One row in `agent_runs` — provider, model, token usage, cost, wall
  time, status, full response JSON.
- One row per tool call in `tool_calls` — tool name, redacted args,
  result summary, duration, status.
- One row in `audit_logs` — event `agent_turn_completed`.

Retention (recommended): 90 days for `agent_runs` + `tool_calls`.

## Cost + budget accounting

Per-turn caps (defaults in `Budget` dataclass):

- `max_tool_calls`: 10
- `max_output_tokens`: 1500
- `max_wallclock_ms`: 30 000
- `max_cost_micro_usd`: 200 000 (~$0.20)

`AgentChatRequest` can lower any of these; it cannot raise them above
the hard defaults.

## Failure modes + expected UI behavior

| Situation                             | Response `status`  | UI                              |
| ------------------------------------- | ------------------ | ------------------------------- |
| Tool result invalid                   | `error`            | Red error card                  |
| Budget exceeded                       | `budget_exceeded`  | Amber "abstained" banner        |
| Model returned non-JSON               | `abstained`        | Amber "abstained" banner        |
| Signal engine INSUFFICIENT_DATA       | `abstained`        | Amber banner + engine reason    |
| Anthropic unreachable                 | `error`            | Red error card (fallback later) |
| Prompt asks about news / filings only | `abstained`        | Amber banner + skeleton reason  |

## What to add next (Phase 4.1)

1. Real ingestion for SEC EDGAR (public REST) and VN disclosures.
2. pgvector similarity search from the agent's `search_*` tools.
3. Offline evaluator that samples 100 turns/day and audits
   `signal_summary` consistency against the tool-call trail.
4. Streaming responses in the UI (Anthropic supports SSE).
