# Compliance considerations

**This is an engineering checklist, not legal advice.** Consult a
qualified attorney and, where applicable, a licensed compliance officer
before enabling any workflow that could be construed as investment
advice, brokerage, or a regulated financial service.

## Product positioning

- DEMO-TRADE is presented as an **educational / research** tool.
- **No real-money orders** are submitted or supported. There is no
  broker connection in the MVP and none is planned.
- Signal output is labeled as **model output**, not a recommendation.
  UI copy uses classifications like "buy candidate" / "avoid", never
  "buy now" / "guaranteed".

## Jurisdictional notes to walk through before launch

- Vietnam (SBV / SSC): licensing of data, restrictions on foreign
  data hosting, personal-data storage rules.
- United States (SEC / FINRA): "investment adviser" definitions,
  "solicitation" rules, publication of research.
- EU (MiFID II): research unbundling; "investment research" vs
  "marketing communication" labeling.
- Crypto: local rules on communications, promotion, and data display
  vary widely; do a per-country review.

## Required in-product surfaces

- Every price shows timestamp, source, market state, and (when
  applicable) staleness.
- Every signal shows horizon, confidence, risk class, factors,
  data-quality score, and strategy version.
- Every research response cites its sources.
- A short standing disclaimer is rendered on every page footer.

## Data-subject rights (privacy)

- Personal data is minimized (email + display name in Phase 1).
- Logs go through `services/api/app/core/redact.py` before persistence.
- Delete-account / export flows are a Phase 5 deliverable.

## Model risk

- Signal model versions are recorded on every signal record.
- Backtests must use walk-forward evaluation with a locked
  out-of-sample period (Phase 3).
- LLM-generated interpretation is separated from quantitative output
  in the UI. LLM output never overrides a signal.
