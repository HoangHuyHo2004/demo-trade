# Signal methodology

**Version: `ensemble-v1`.** Explainable, deterministic, rule-based ensemble.
Every score contribution is a named factor with a documented derivation.

> Educational / research use only. Not investment advice. Not personalized.

## Model interface

- Concrete models implement `app.quant.models_base.SignalModel`. They receive
  a `SignalInput` (asset id, market, calendar, aligned OHLCV + optional benchmark
  closes, all filtered to `available_at <= as_of`) and return a `ModelOutput`
  (raw score in [-100, 100], factor list, regime, data quality, warnings,
  optional reference levels).
- The **engine** wraps the model output in the API-facing payload
  (classification thresholds, confidence formula, risk classification,
  disclaimer, strategy version, data version).

## Factor derivation (ensemble-v1)

Weights sum to 1.0; each category is averaged internally then weighted.

| Category    | Weight | Factors                                                                          |
| ----------- | ------ | -------------------------------------------------------------------------------- |
| trend       | 0.30   | EMA20/EMA60 gap (scale ±5%); MACD histogram (scale ±1% of price)                 |
| momentum    | 0.25   | RSI(14) centered on 50 (scale ±25); 20-bar return (±10%); 60-bar return (±25%)   |
| volatility  | 0.15   | ATR% penalty (scale from 2% to 7% of price); 60-bar drawdown penalty (>20% only) |
| volume      | 0.15   | Relative-volume z-score(20) × sign of last-bar return                            |
| benchmark   | 0.15   | Relative strength vs market benchmark (20-bar, ±10%)                             |

Each factor is clipped to `[-1, 1]`. Category means are then weighted and
normalized by *covered* weight (categories with zero factors are ignored,
not counted).

Final score = `clip(weighted_mean, -1, 1) * 100`.

## Classification

Applied only after data-quality gating:

| Score        | Classification    |
| ------------ | ----------------- |
| ≥ 60         | STRONG_BULLISH    |
| 20 to 60     | BULLISH           |
| −20 to 20    | NEUTRAL           |
| −60 to −20   | BEARISH           |
| ≤ −60        | STRONG_BEARISH    |

If `data_quality < 0.4`, we return **INSUFFICIENT_DATA** regardless of score.
`data_quality` is `0.5 * category_coverage + 0.5 * min(1, n_bars / 90)`.

## Confidence

`confidence = 0.4 * agreement + 0.4 * data_quality + 0.2 * (0.5 * completeness + 0.5 * magnitude)`

- **agreement**: fraction of factors whose sign matches the final score sign
- **data_quality**: as above
- **completeness**: `min(1, n_bars / 200)`
- **magnitude**: `min(1, |score| / 60)`

Confidence is **not** a probability of being right. It is a floor that
prevents strong-looking signals with poor evidence base or contradictions
from being displayed as high-confidence. A production build should
recalibrate this against historical out-of-sample hit rates.

## Risk classification

| ATR%    | 60-bar MDD | Class    |
| ------- | ---------- | -------- |
| ≤ 3%    | ≤ 15%      | LOW      |
| ≤ 8%    | ≤ 30%      | MODERATE |
| > 8%    | or > 30%   | HIGH     |
| > 12%   | or > 45%   | SEVERE   |

## Reference levels

Emitted only when `score > 20` and enough bars exist:

- **entry_zone**: `[close − ATR14, close + 0.5 * ATR14]`
- **invalidation**: `min(close − 2 * ATR14, min(low[-20:]))`
- **take_profit**: `[close + 2 * ATR14, close + 4 * ATR14]`

These are **reference levels**, not orders. The UI copy makes this
explicit.

## Determinism

- All indicator calculations are pure functions of the input series
  (`app.quant.indicators`).
- The model reads only bars whose `available_at <= as_of`.
- The engine records a `data_version` (`bars-<hash of last bar time + close + count>`)
  and the model's `strategy_version` on every persisted signal.
- Same input → identical payload (verified by `test_signal_is_reproducible`).

## Known limitations (Phase 3)

- No fundamental overlays — requires point-in-time paid data.
- No cross-exchange crypto features (funding rate, open interest).
- Confidence is heuristic, not calibrated against a locked out-of-sample
  hit-rate table (Phase 3 backlog).
- Long-only. Short positions and pair trades are not modeled.
- Regime classification is asset-local (EMA20 slope). Market-breadth /
  multi-asset regime is a Phase 3 backlog item.
