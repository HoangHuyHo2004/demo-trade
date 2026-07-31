# AGENTS.md — apps/web

Extends the root `AGENTS.md`. In case of conflict, the root wins.

## Rules

- TypeScript `strict`. No `any` in exported surfaces. Reuse types from
  `@demo-trade/contracts`.
- Fetching goes through `src/lib/api.ts`, never a bare `fetch` in a
  component.
- Every surface that displays a price MUST also render:
  timestamp, source, market state, and (when applicable) a stale badge.
- No secrets in the browser bundle. Only `NEXT_PUBLIC_*` env vars are
  readable client-side.
- No unlabelled LLM output. When Phase 4 lands, agent-generated copy
  must be visually distinct from quantitative output.
- Signals are model output, not recommendations. Never use words like
  "guaranteed", "sure thing", or urgency copy.
