# Backtesting methodology

## Non-negotiable safeguards

- **No lookahead.** At each simulated decision time `t` the model only
  sees bars whose `available_at <= t`. This is asserted in
  `tests/test_backtester.py::test_backtester_never_touches_bars_after_decision_time`.
- **Execution lag.** A decision made from information through bar `t` is
  filled at bar `t+1.open`. That is the same "future" a live strategy
  would face, and it is the only future the backtester touches.
- **Symmetric per-side costs.** Fees, slippage, and (where applicable)
  taxes are charged on both entry and exit.
- **No random splits.** Time series are evaluated in-sample chronologically;
  we do not use random train/test splits.
- **Determinism.** Given the same inputs the backtester returns the same
  metrics, trades, and equity curve.

## Cost profiles

Kept in `app/quant/costs.py`, per market:

| Market   | Fee (bps/side) | Slippage (bps/side) | Extra tax (bps/side) |
| -------- | -------------- | ------------------- | -------------------- |
| US       | 0              | 3                   | 0                    |
| VN       | 15             | 10                  | 5                    |
| COINBASE | 40             | 5                   | 0                    |
| KRAKEN   | 25             | 5                   | 0                    |
| BINANCE  | 10             | 5                   | 0                    |

The API accepts `cost_bps` and `slippage_bps` overrides so operators can
experiment without editing code. **These are engineering defaults, not
regulatory constants** — production must load dated profiles from the DB.

## Baselines

Every backtest reports the strategy alongside:

1. **Buy & hold** — equity curve of the underlying, same window.
2. **Cash** — 0% return over the window.
3. **SMA 50/200 crossover** — long when SMA50 > SMA200, flat otherwise;
   uses same-day close for the crossover check to keep it a fair baseline.
4. **Market benchmark** — if configured for the asset's market (SPY for US,
   VN-Index for VN, BTC for crypto), rebased over the same window.

## Metrics

- `total_return`, `cagr`, `volatility` (annualized), `sharpe`, `sortino`
- `max_drawdown`, `calmar` (`cagr / max_drawdown`)
- `win_rate`, `profit_factor` (gross_profit / gross_loss)
- `trades`, `avg_holding_bars`, `turnover` (trades / year), `exposure`
  (fraction of bars in position)
- Regime bar counts (bull / bear / neutral) as classified by the model
- All comparison returns (buy_hold, cash, sma_baseline, benchmark)

## What the backtester does **not** yet cover

- Walk-forward *parameter search*. This engine walk-forward *evaluates*
  the fixed rule parameters. A grid-search wrapper with locked
  out-of-sample verification is a Phase 3 backlog item.
- Point-in-time universe membership (VN delistings).
- Short-selling, leverage, options.
- Multi-asset portfolios (correlation constraints, sector caps).
- Regime-specific parameter sets.
- Tax lots and cost-basis accounting.

## Small-sample warnings

The backtester surfaces a warning when the evaluated bar count is below
200. Metrics on short windows are directional, not statistical evidence.
The UI shows the warning in a visible amber block.

## Reproducibility contract

Given `(asset, interval, start, end, horizon, model_code, thresholds, cost/slippage)`
the same DB state produces the same `metrics`, `trades`, and `equity`
records — verified by `tests/test_backtester.py::test_backtest_is_deterministic`.
