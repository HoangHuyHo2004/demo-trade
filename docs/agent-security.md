# Agent security

The research agent is the highest-risk component in the app. This
document is the authoritative reference for the defenses in place and
the assumptions those defenses rest on. See also `AGENTS.md` §3-4.

## Threat model

An adversary may:

- Craft user prompts (prompt injection at the source).
- Plant instructions **inside** documents/news/filings/social posts we
  later retrieve (prompt injection at the tool boundary).
- Attempt to have the agent call an unapproved capability (shell, SQL,
  fetch arbitrary URL, place an order, mutate account state).
- Attempt to have the agent produce a fabricated citation, an invented
  price, or a signal number that overrides the quantitative engine.
- Attempt to exfiltrate secrets or another user's data.
- Cause resource exhaustion (runaway tool loops, huge outputs).

## Instruction source boundary

Only text authored by the signed-in user in the chat interface is treated
as instructions. Everything else — tool results, retrieved documents,
database contents — is **data**. This is enforced at two places:

1. **`_wrap_tool_result`** in `app/agent/orchestrator.py` wraps every
   tool result in a delimited `<untrusted_source tool="...">...</untrusted_source>`
   block **before** it reaches the LLM.
2. The system prompt (`SYSTEM_PROMPT` constant in the same file) states
   the boundary rule explicitly and instructs the model to ignore any
   directives found inside those blocks.

## Tool allowlist

Only tools registered in `app/agent/tools.py::ALLOWED_TOOLS` are
dispatchable. Any other tool name is a hard error at the executor level.

Current allowlist (Phase 4):

| Tool                        | Purpose                                     | Mutating? |
| --------------------------- | ------------------------------------------- | --------- |
| `resolve_asset`             | Canonical id lookup                         | No        |
| `get_market_status`         | Session state per market                    | No        |
| `get_quote`                 | Latest quote via provider registry          | No        |
| `get_historical_bars`       | OHLCV via `BarRepository` (cached, audited) | No (audit-only writes) |
| `get_calculated_indicators` | Deterministic indicator values              | No        |
| `calculate_signal`          | Signal engine `ensemble-v1` (persists)      | Writes signal + factors |
| `run_backtest`              | Walk-forward backtest (persists)            | Writes backtest rows |
| `compare_assets`            | Aligned closes over a window                | No |
| `search_sec_filings`        | **Skeleton** — always `not_available`       | No |
| `search_vietnam_disclosures`| **Skeleton** — always `not_available`       | No |
| `search_company_announcements` | **Skeleton** — always `not_available`     | No |
| `search_crypto_project_announcements` | **Skeleton** — always `not_available` | No |
| `search_approved_news_sources` | **Skeleton** — always `not_available`     | No |

There is **no** shell tool, arbitrary SQL tool, arbitrary URL fetch,
account-mutation tool, or order-placement tool. Adding one is an
explicit product decision + threat re-model.

## Argument validation

Every tool has a Pydantic argument schema (`app/agent/schemas.py`) with
`extra="forbid"`. Server-side execution rejects unknown fields, so a
hallucinated `override_price` or `shell_cmd` can never reach a handler.

Tests: `tests/test_agent_tools.py` covers unknown-tool rejection, extra-field
rejection, and out-of-range values.

## Signal-engine boundary

The agent may **request** a signal via `calculate_signal`, and it may
describe the returned payload. It **must not** synthesize scores,
confidence, or classifications. The mock LLM enforces this by
construction (it only echoes tool output). Tests:
`test_agent_orchestrator.py::test_agent_never_produces_a_score_the_engine_didnt_return`
and `test_prompt_injection_payload_in_tool_result_is_wrapped_and_ignored`.

For a production Claude deployment: the system prompt forbids overriding
the engine, and we recommend adding an offline evaluator that samples
turns and checks the response `signal_summary` against the tool-call
audit trail. That evaluator is a Phase 4.1 backlog item.

## Budgets

Per-turn caps enforced in `run_agent_turn`:

| Budget                | Default    |
| --------------------- | ---------- |
| `max_tool_calls`      | 10         |
| `max_output_tokens`   | 1500       |
| `max_wallclock_ms`    | 30,000     |
| `max_cost_micro_usd`  | 200,000 (~$0.20) |

Callers may lower any of these via the request; they cannot raise them
above the hard caps. Exceeding a budget aborts the turn with
`status="budget_exceeded"` and a structured abstain response.
Test: `test_budget_max_tool_calls_is_enforced`.

## Audit trail

Every turn writes:

- One row in `agent_runs` with provider + model + tokens + cost +
  wallclock + status + full response JSON.
- One row per tool call in `tool_calls` with the tool name, redacted
  args, a short result summary, duration, and status.
- One row in `audit_logs` with event `agent_turn_completed`.

Test: `test_tool_calls_are_audited_with_redacted_summaries`.

## Secret / PII handling

- The Anthropic API key is read only by `AnthropicProvider`. It never
  leaves the process.
- Tool call summaries pass through `app/core/redact.py` before being
  written to `tool_calls.result_summary`.
- The demo user's email address is never surfaced in
  `tool_calls.result_summary` — asserted by the audit test.
- No secret is embedded in the frontend bundle.

## URL / SSRF policy

Provider adapters (`app/providers/_http.py`) enforce a per-adapter host
allowlist. The agent has no free-form `fetch_url` capability. When the
`search_*` skeletons are eventually replaced by real ingestion, they
**must** go through the same allowlisted HTTP helper.

## Handling `search_*` skeletons

Because the search tools return `status="not_available"`, the system
prompt tells the model to abstain rather than fabricate a citation. If a
user asks "what did the CEO say last week?", the agent's expected
behavior is to return `abstained=true` with a reason. The UI renders an
amber "Agent abstained" banner in that case.

## Real-money order execution

**Not implemented and not planned for the MVP.** No agent tool mutates
account state on any venue. Adding a paper-portfolio tool (Phase 5) is
allowed only behind an explicit user confirmation UI, not as an
agent-callable tool.

## Known residual risks

- **Real LLM (Claude) has richer generation.** The mock LLM guarantees
  no fabrication because it doesn't free-text; a real LLM must be
  monitored with the offline evaluator described above.
- **The `search_*` skeletons could tempt a real LLM to invent a
  workaround** (e.g. by pretending its training data is a source). The
  system prompt forbids this, but a periodic evaluator sweep is the
  final check.
- **Cost accounting is a floor, not a source of truth.** Real spend is
  the vendor invoice; the `cost_usd_micro` column exists for budget
  enforcement + rate limiting only.
