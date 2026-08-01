# ML targets (labels)

**Target version: `targets-v1`** (`app/ml/labels.py`). Computed by
`compute_labels(closes, t, horizon, cost_bps)`.

## Direction label

```
round_trip_cost = 2 * cost_bps / 10_000
fwd_return = ln(close[t+horizon] / close[t])

direction =  1  if fwd_return >  round_trip_cost
          = -1  if fwd_return < -round_trip_cost
          =  0  otherwise (neutral zone)
```

The neutral zone widens with `cost_bps` so noise inside the
transaction-cost band isn't labeled as a tradeable move. Cost defaults
per market come from the same `app/quant/costs.py` profiles the
backtester uses (US: 3bps, VN: 30bps [15 fee + 10 slippage + 5 tax],
crypto: varies 15-45bps by venue) — Phase 1's training endpoint takes
`cost_bps` as an explicit parameter rather than auto-resolving it from
market, so operators should pass the right value per market when
training (documented in the training-run's `config_json`).

Direction models are trained on a **binary** target: rows where
`direction == 0` (neutral) are dropped from the classifier's training
set (`app.ml.models.make_fit_class_mask`). This avoids teaching the
model to associate "flat, low-signal" feature patterns with either
class — better to abstain (low confidence, near 50%) than force a
neutral period into a binary bucket.

## Regression target (future return)

```
future_return = ln(close[t+horizon] / close[t])
```

Same formula as direction's numerator, stored unrounded. Phase 1 does
not yet train a regression model on this (only `ridge` is wired as a
`make_regression_model`, but no training endpoint calls it yet — the
shipped models are all direction/classification). The field exists in
`LabelSet` and in the `ml_predictions` schema
(`expected_return_median/lower/upper`) for when regression training is
added.

## Volatility target

```
log_rets = [ln(close[i]/close[i-1]) for i in path[t..t+horizon]]
future_vol = stdev(log_rets) * sqrt(252)     # annualized
```

Uses the full path within the horizon (not just the endpoint), so it
captures realized volatility along the way, not just the net drift.
Not yet trained on in Phase 1; reserved for a future volatility-
prediction model (spec lists this as a required objective).

## Drawdown target (max adverse move)

```
path = close[t : t+horizon+1]
future_mdd = (min(path[1:]) - close[t]) / close[t]
```

Negative fraction representing the worst point-in-time loss an
investor entering at `close[t]` would have experienced before the
horizon closes — captures intra-horizon dips even if the endpoint
recovers to flat or positive. Not yet trained on in Phase 1.

## No-lookahead guarantee

`compute_labels` takes the full `closes` array plus an index `t` and a
`horizon`; it only ever reads `closes[t : t+horizon+1]`. Appending
arbitrary garbage bars *after* `t+horizon` cannot change the label —
tested directly:
`tests/test_ml_labels.py::test_future_return_only_uses_closes_up_to_t_plus_horizon`.

The dataset builder (`app.ml.datasets.build_dataset`) only calls
`compute_labels` for `t` in `[warmup_bars, len(bars) - horizon - 1]`,
so every label always has a fully-realized horizon inside the loaded
bar series — no label is ever computed from a partially-elapsed
horizon.

## Horizon → bar count mapping

| Horizon | Bars (interval=1d) |
|---|---|
| `1D` | 1 |
| `5D` | 5 |
| `20D` | 20 |

Crypto uses the same bar-count horizons on daily bars (spec's
"equivalent calendar-based horizons" note applies to intraday
horizons, which Phase 1 doesn't yet support — only daily-bar training
is implemented).

## Sample-size discipline

Avoid labeling tiny random moves as meaningful — the cost-adjusted
neutral zone (above) is the primary defense. A secondary defense
(minimum 200 dataset rows before training proceeds) is enforced in
`mlw.tasks.train_model`.
