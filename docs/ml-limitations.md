# ML limitations

Read this before trusting any number the ML subsystem produces. It
applies to every model trained in this codebase (`logreg`, `rf`,
`gbm` — Phase 1 baselines only) regardless of market or horizon.

## This is not a claim that the model "learns the market"

Per the spec's final constraint: financial relationships change over
time. A pattern that was historically associated with positive
forward returns can disappear because of regime changes, competition,
regulation, liquidity changes, transaction costs, data-provider
changes, structural market shifts, or plain random chance. Every
prediction the API returns is a **probabilistic estimate conditioned
on historical data**, not a forecast guarantee, and the API's
`disclaimer` field says so on every response.

## Training-data honesty

**US and VN model families in this repository, by default, train on
the deterministic mock provider's synthetic GBM bars unless real
provider credentials (`ALPACA_API_KEY`, `SSI_FC_*`) are configured.**
Synthetic GBM data has autocorrelation structure a model can genuinely
fit (the drift term is real), but that structure has zero relationship
to real market dynamics. A US/VN model trained without real
credentials configured is a **pipeline correctness demo**, not a
usable prediction system, no matter how good its validation metrics
look.

Crypto models trained against real Coinbase historical data (available
without credentials — see `docs/data-providers.md`) are the only
models in Phase 1 with a legitimate claim to reflect real market
structure, and even those are subject to every other limitation below.

**How to check what a specific model trained on**: `ml_models.dataset_version`
→ `ml_datasets` row → `from_time`/`to_time` → cross-reference
`price_bars.source` for that asset/window (`"mock"` vs `"coinbase"` vs
`"alpaca"` vs `"ssi-fc"`).

## Sample size

Phase 1's default demo deployment has roughly 1-2 years of daily bars
per asset. After the 200-bar warmup and the `warmup_bars +
horizon_bars` truncation at each series' start/end, a single asset
contributes on the order of a few hundred rows. A market-wide dataset
(all active assets in a market) is the union of these — still small by
ML standards, and the walk-forward split further divides it into
train/validation subsets. Metrics computed on validation sets this
small have wide confidence intervals that Phase 1 does not compute or
display. Treat any single model's `roc_auc`/`brier` number as a rough
signal, not a precise estimate.

## No point-in-time universe / survivorship bias

The dataset builder queries `Asset WHERE market = X AND is_active =
true` — i.e., **today's** active-asset list, applied uniformly across
the entire training history. Any asset that was delisted, renamed, or
otherwise removed from "active" status during the training window is
entirely absent from that window's training data, even for the dates
when it was actively trading. This is textbook survivorship bias and
will make historical performance look better than an honest
point-in-time universe would.

## No fundamental, corporate-event, or macro features

Phase 1 ships 28 price/volume-derived features only (see
`docs/ml-feature-dictionary.md`). The spec's fundamental (revenue
growth, margins, valuation), corporate-event (earnings, dividends,
splits), and macro (rates, FX, breadth) feature groups require
point-in-time data sources this app doesn't yet ingest. A model that
doesn't know an earnings announcement is imminent tomorrow cannot
account for the volatility spike that typically follows one.

## No out-of-distribution detection

Every asset with ≥60 bars of history gets a prediction from every
active `SHADOW`/`CHAMPION` model, regardless of whether its current
feature vector resembles anything the model saw during training. A
sudden market-structure break (e.g. a new listing, a stock split not
yet reflected in adjusted prices, a flash-crash-adjacent session) can
produce a feature vector far outside the training distribution with
no warning attached to the resulting prediction.

## Calibration is measured, not gated

Training computes reliability bins and standard calibration metrics
(Brier score, log loss) per fold and stores them. **Nothing currently
blocks promotion of a poorly-calibrated model.** A `SHADOW` model with
visibly bad calibration bins (e.g., predictions clustering near 50%
regardless of the bucket, or systematic over/under-confidence) can
still be manually promoted to `CHAMPION` — see `docs/ml-model-risk.md`
§4.

## Tree-model contributions are unsigned

As documented in `docs/ml-explainability.md`, `rf`/`gbm` predictions
report their top-5 factors by unsigned importance magnitude only — an
empty `negative_contributors` list for a tree-based model means "no
signed decomposition was computed," not "nothing pushed the prediction
down." Check the prediction's `warnings` field, which explicitly flags
this for tree-based models. Only `logreg`/`ridge` predictions have a
mathematically correct positive/negative split.

## No hyperparameter search, no advanced models

Every model uses one fixed, documented hyperparameter set (see
`docs/ml-validation.md`). No XGBoost, LightGBM, CatBoost, or any deep
learning model is implemented — per spec, these are explicitly gated
behind the simple baselines proving reliable out-of-sample improvement
after costs first, which Phase 1 has not yet established (no promoted
`CHAMPION` model exists in a fresh deployment).

## No ensemble with the rule-based engine

ML predictions and rule-based signals are computed, stored, and served
completely independently in Phase 1. There is no code that blends
them, no "ML agrees with the rule engine, increase confidence" logic,
no risk-override logic connecting the two. Anyone reading both a
`Signal` and an `MLPrediction` for the same asset should treat them as
two separate, uncombined opinions — exactly as the UI presents them
(separate cards, separate disclaimers).

## Reporting predictions honestly

If you build any downstream reporting on `ml_prediction_outcomes`,
remember: outcomes are only written once a prediction's horizon has
fully elapsed (`evaluate_outcomes` runs daily and only scores expired
predictions). A model that has only been running for a few days will
have zero or near-zero outcome rows — don't compute "live" accuracy
from a sample too small to mean anything, and always report the
`n` behind any realized-performance number.
