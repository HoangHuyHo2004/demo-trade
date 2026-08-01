# ML feature dictionary

**Feature pipeline version: `features-v1`** (`app/ml/features.py`).
Any change to a definition below requires bumping this constant, which
flows into `dataset_version` and therefore into every downstream model
and prediction record.

All 28 features are computed by `build_features()` from OHLCV arrays
truncated to the "as-of" bar (index `t`). None reads beyond index `t`.
**Leakage risk for every feature below is LOW** because the function
signature physically cannot see index `t+1` — the caller is
responsible for truncating (`app.ml.datasets.build_dataset` does this
correctly; tested in `tests/test_ml_features.py`).

Missing-value behavior is uniform: every feature returns `float('nan')`
when its lookback window isn't warmed up yet, rather than a
sentinel-value or zero-fill. Downstream, `training.py::features_matrix_from_rows`
drops any row containing a NaN feature — Phase 1 does not impute.

Applicable markets: all 28 features apply to US, VN, and crypto (they
are pure price/volume functions with no market-specific unit
assumptions). No fundamental, macro, or corporate-event features are
implemented in Phase 1 (see "Deferred feature groups" below).

## Returns

| Feature | Definition | Lookback | Pub. delay |
|---|---|---|---|
| `ret_1d` | `ln(close[t] / close[t-1])` | 2 bars | 0 (bar close) |
| `ret_5d` | `ln(close[t] / close[t-6])` | 6 bars | 0 |
| `ret_10d` | `ln(close[t] / close[t-11])` | 11 bars | 0 |
| `ret_20d` | `ln(close[t] / close[t-21])` | 21 bars | 0 |
| `ret_60d` | `ln(close[t] / close[t-61])` | 61 bars | 0 |

## Trend

| Feature | Definition | Lookback | Notes |
|---|---|---|---|
| `ema10_over_ema50` | `EMA(close,10)[t] / EMA(close,50)[t]` | 50 bars | ratio, NaN until EMA50 warm |
| `ema20_over_ema50` | `EMA(close,20)[t] / EMA(close,50)[t]` | 50 bars | |
| `ema20_over_ema200` | `EMA(close,20)[t] / EMA(close,200)[t]` | 200 bars | slow to warm — needs 200 bars |
| `price_over_ema50` | `close[t] / EMA(close,50)[t]` | 50 bars | |
| `price_over_ema200` | `close[t] / EMA(close,200)[t]` | 200 bars | |
| `ema20_slope_20` | `EMA20[t] / EMA20[t-20] - 1` | 40 bars (20 for EMA warm + 20 for slope lag) | |
| `breakout_hi_55` | `1.0` if close[t] is a new 55-bar high (Donchian), else `0.0` | 55 bars | binary |
| `breakdown_lo_55` | `1.0` if close[t] is a new 55-bar low, else `0.0` | 55 bars | binary |

## Momentum

| Feature | Definition | Lookback |
|---|---|---|
| `rsi_14` | Wilder RSI(14) | 15 bars |
| `macd_hist_pct_price` | `MACD_hist(12,26,9)[t] / close[t]` | 35 bars (26+9) |
| `mom_20` | `close[t]/close[t-20] - 1` | 20 bars |
| `mom_60` | `close[t]/close[t-60] - 1` | 60 bars |

## Volatility

| Feature | Definition | Lookback |
|---|---|---|
| `atr_pct_14` | `ATR(14)[t] / close[t]` | 15 bars |
| `realized_vol_20` | Annualized stdev of 20-bar log returns | 21 bars |
| `realized_vol_60` | Annualized stdev of 60-bar log returns | 61 bars |
| `mdd_60` | Max drawdown over the trailing 60 bars (or fewer if series shorter) | up to 60 bars |
| `gap_over_atr` | `abs(close[t]-close[t-1]) / ATR(14)[t]` | 15 bars |

## Volume

| Feature | Definition | Lookback |
|---|---|---|
| `rel_volume_20` | `volume[t] / mean(volume[t-19:t+1])` | 20 bars |
| `vol_z_20` | Rolling z-score of volume, 20-bar window | 20 bars |
| `vp_divergence` | `1.0` if sign(return[t]) ≠ sign(volume z-score[t]), else `0.0` | 20 bars |

## Benchmark-relative (only when a benchmark series is supplied)

| Feature | Definition | Lookback |
|---|---|---|
| `rel_strength_20` | `mom_20(asset) - mom_20(benchmark)` | 20 bars, both series |
| `bench_mom_20` | `mom_20(benchmark)` | 20 bars |
| `corr_bench_60` | Pearson correlation of last-60-bar log returns, asset vs benchmark | 61 bars, both series |

If no benchmark series is passed (or it doesn't overlap in time), all
three are `NaN`. Benchmarks used in Phase 1: `ETF:US:NYSE:SPY` (US),
`INDEX:VN:HOSE:VNINDEX` (VN), `CRYPTO:COINBASE:BTC-USD` (crypto —
used as the benchmark for crypto assets other than BTC itself).

## Deferred feature groups (spec lists these; not yet implemented)

- **Fundamental** (revenue growth, margins, ROE, valuation multiples) —
  requires point-in-time fundamentals data, which the app doesn't
  ingest yet (see `docs/data-providers.md`).
- **Corporate events** (earnings proximity, dividends, splits,
  buybacks) — requires a corporate-actions feed; `corporate_actions`
  table exists in the Phase 1 schema but is unpopulated.
- **Macro** (interest rates, FX, volatility indices) — no macro data
  source configured.
- **Crypto-specific** (funding rates, open interest, on-chain,
  exchange flows) — would require derivatives/on-chain data providers,
  explicitly called out in the spec as "optional provider-dependent
  modules."

Adding any of these is a matter of writing a new `build_*_features()`
function following the same "pure function of a truncated input" shape
and merging its output dict into `build_features()`'s return — no
architectural change needed, but each new group needs its own
point-in-time data source first.
