"""Walk-forward backtester with no-lookahead safeguards.

Design:
  * At each bar ``t`` we build a ``SignalInput`` restricted to bars whose
    ``available_at <= bar_time[t]``. The model output determines the
    action for bar ``t+1``.
  * Fills happen at bar ``t+1``'s open (a realistic delay). This is the
    only place where "the future" is touched, and it's the same future
    the strategy would see live.
  * Costs are charged per side on entry and exit. Fees, slippage, and
    taxes come from ``costs.profile_for(market)`` unless overridden by
    the request.
  * Long-only in Phase 3. Position sizing is fully invested when in the
    market, cash when flat; leverage is not modeled.
  * We compare vs (a) buy-and-hold, (b) cash (0% return), (c) a simple
    SMA baseline, and (d) an aligned market benchmark when available.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.market_data import PriceBar
from app.providers.registry import get_registry
from app.quant import indicators as ind
from app.quant.costs import CostProfile, profile_for
from app.quant.ensemble import RuleBasedEnsemble
from app.quant.models_base import ModelOutput, SignalInput, SignalModel
from app.services.bar_repository import BarRepository
from app.services.signal_engine import (
    _BENCHMARK_BY_MARKET,
    _align_by_time,
    get_model,
)

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BacktestParams:
    asset: Asset
    interval: str = "1d"
    start: datetime | None = None
    end: datetime | None = None
    horizon: str = "5D"
    model_code: str = RuleBasedEnsemble.code
    entry_threshold: float = 20.0        # score >= this triggers/holds a long
    exit_threshold: float = -5.0         # score <= this exits
    cost_bps_override: float | None = None
    slippage_bps_override: float | None = None
    warmup_bars: int = 60                 # min bars before first decision


@dataclass(frozen=True, slots=True)
class TradeRecord:
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    bars_held: int
    pnl_pct: float
    cost_pct: float
    reason: str


@dataclass(frozen=True, slots=True)
class EquityPoint:
    bar_time: datetime
    strategy_equity: float
    buy_hold_equity: float
    in_position: bool


@dataclass(frozen=True, slots=True)
class Metrics:
    total_return: float
    cagr: float
    volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    win_rate: float
    profit_factor: float
    turnover: float          # trades per year (average)
    trades: int
    avg_holding_bars: float
    exposure: float          # fraction of bars in position
    hit_rate: float          # win rate again for the top-level UI
    # comparisons
    buy_hold_return: float
    cash_return: float
    sma_baseline_return: float
    benchmark_return: float | None
    # regime breakdown
    bars_bull: int
    bars_bear: int
    bars_neutral: int


@dataclass(frozen=True, slots=True)
class BacktestOutcome:
    params: BacktestParams
    cost_profile: CostProfile
    trades: list[TradeRecord]
    equity: list[EquityPoint]
    metrics: Metrics
    warnings: list[str]


async def run_backtest(session: AsyncSession, params: BacktestParams) -> BacktestOutcome:
    if params.horizon not in ("1D", "5D", "20D"):
        raise ValueError("horizon must be 1D, 5D, or 20D")
    profile = profile_for(params.asset.market)
    cost_bps = (
        params.cost_bps_override if params.cost_bps_override is not None else profile.fee_bps + profile.tax_bps
    )
    slippage_bps = (
        params.slippage_bps_override if params.slippage_bps_override is not None else profile.slippage_bps
    )
    per_side_cost = (cost_bps + slippage_bps) / 10_000.0

    end = (params.end or datetime.now(UTC)).astimezone(UTC)
    start = (params.start or (end - timedelta(days=365 * 2))).astimezone(UTC)

    reg = get_registry()
    repo = BarRepository(session)
    provider = reg.market_data_for(params.asset.market)
    # Fetch bars for the full window + a healthy pre-warmup so factors
    # can compute on the first evaluated bar.
    warmup_pad = timedelta(days=_days_for_warmup(params.interval, 300))
    await repo.get_or_fetch(
        params.asset, provider,
        interval=params.interval, start=start - warmup_pad, end=end,
    )
    bars = await _load_bars(session, params.asset.id, params.interval,
                            start - warmup_pad, end)

    # Load + align benchmark (never fetched with future data at decision time —
    # we filter benchmark by available_at within the loop).
    bench_id = _BENCHMARK_BY_MARKET.get(params.asset.market)
    bench_bars: list[PriceBar] = []
    benchmark_asset: Asset | None = None
    if bench_id and bench_id != params.asset.canonical_id:
        benchmark_asset = (await session.execute(
            select(Asset).where(Asset.canonical_id == bench_id)
        )).scalar_one_or_none()
        if benchmark_asset is not None:
            bp = reg.market_data_for(benchmark_asset.market)
            await repo.get_or_fetch(
                benchmark_asset, bp,
                interval=params.interval, start=start - warmup_pad, end=end,
            )
            bench_bars = await _load_bars(
                session, benchmark_asset.id, params.interval,
                start - warmup_pad, end,
            )

    if len(bars) < params.warmup_bars + 10:
        raise ValueError(
            f"insufficient bars for backtest: {len(bars)} (need >= "
            f"{params.warmup_bars + 10})"
        )

    model = get_model(params.model_code)

    # Truncate initial warmup so all decisions have factor coverage.
    eval_bars = bars[params.warmup_bars :]

    equity_curve: list[EquityPoint] = []
    trades: list[TradeRecord] = []
    warnings: list[str] = []
    if len(eval_bars) < 200:
        warnings.append(
            f"only {len(eval_bars)} evaluated bars — small sample; treat "
            f"results as directional, not statistical evidence"
        )

    starting_equity = 1.0
    strategy_equity = starting_equity
    buy_hold_start_price = float(eval_bars[0].close)
    in_position = False
    entry_price = 0.0
    entry_time = eval_bars[0].bar_time
    bars_in_pos = 0

    bull_bars = bear_bars = neut_bars = 0
    per_bar_returns: list[float] = []

    # Iterate over bars — decision uses info up to (and including) bar[i]
    # (which represents info AVAILABLE at bar[i].bar_time), execution
    # happens at bar[i+1].open.
    for i in range(len(eval_bars) - 1):
        decision_bar = eval_bars[i]
        exec_bar = eval_bars[i + 1]

        # Assemble decision-time window (STRICTLY <= decision_bar.bar_time)
        history_end = decision_bar.bar_time
        history = [b for b in bars if b.available_at <= history_end]
        if len(history) < params.warmup_bars:
            equity_curve.append(EquityPoint(
                bar_time=decision_bar.bar_time,
                strategy_equity=strategy_equity,
                buy_hold_equity=float(decision_bar.close) / buy_hold_start_price,
                in_position=in_position,
            ))
            continue
        bench_at_decision = [b for b in bench_bars if b.available_at <= history_end]
        si = _build_input(params.asset, params.interval, history_end, history,
                          bench_at_decision, benchmark_asset)
        out: ModelOutput = model.compute(si, horizon=params.horizon)
        _bump_regime_counter(out.regime, bull_bars_ref := [bull_bars, bear_bars, neut_bars])
        bull_bars, bear_bars, neut_bars = bull_bars_ref

        want_long = out.score >= params.entry_threshold
        want_exit = out.score <= params.exit_threshold

        fill_price = float(exec_bar.open)
        # Bar-return on the strategy: if we entered position at the start
        # of exec_bar we are exposed to (exec_bar.close / fill_price - 1)
        # for this bar. If we're already in position, exposure is
        # (exec_bar.close / decision_bar.close - 1). Cost applied on
        # entry & exit.
        prior_equity = strategy_equity
        if not in_position and want_long:
            # Enter at exec_bar.open with cost.
            entry_price = fill_price * (1 + per_side_cost)
            entry_time = exec_bar.bar_time
            in_position = True
            bars_in_pos = 0
            # Mark to end of this bar
            ret = (float(exec_bar.close) - entry_price) / entry_price
            strategy_equity *= 1 + ret
        elif in_position and want_exit:
            exit_price = fill_price * (1 - per_side_cost)
            # Mark holding to fill first, then close.
            hold_ret = (fill_price - float(decision_bar.close)) / float(decision_bar.close)
            strategy_equity *= 1 + hold_ret
            pnl = (exit_price - entry_price) / entry_price
            trades.append(TradeRecord(
                entry_time=entry_time, entry_price=entry_price,
                exit_time=exec_bar.bar_time, exit_price=exit_price,
                bars_held=bars_in_pos + 1,
                pnl_pct=pnl,
                cost_pct=2 * per_side_cost,
                reason="signal_exit",
            ))
            in_position = False
            bars_in_pos = 0
        elif in_position:
            # Continue holding; mark to market at exec_bar.close
            ret = (float(exec_bar.close) - float(decision_bar.close)) / float(decision_bar.close)
            strategy_equity *= 1 + ret
            bars_in_pos += 1
        # else: flat and staying flat — no P&L

        per_bar_returns.append(strategy_equity / prior_equity - 1.0)
        equity_curve.append(EquityPoint(
            bar_time=exec_bar.bar_time,
            strategy_equity=strategy_equity,
            buy_hold_equity=float(exec_bar.close) / buy_hold_start_price,
            in_position=in_position,
        ))

    # Close any open trade at the last bar
    if in_position:
        exit_price = float(eval_bars[-1].close) * (1 - per_side_cost)
        pnl = (exit_price - entry_price) / entry_price
        trades.append(TradeRecord(
            entry_time=entry_time, entry_price=entry_price,
            exit_time=eval_bars[-1].bar_time, exit_price=exit_price,
            bars_held=bars_in_pos + 1, pnl_pct=pnl, cost_pct=2 * per_side_cost,
            reason="eob_close",
        ))
        in_position = False

    metrics = _compute_metrics(
        params=params, eval_bars=eval_bars, equity=equity_curve, trades=trades,
        per_bar_returns=per_bar_returns,
        bench_bars=bench_bars, benchmark_asset=benchmark_asset,
        bull_bars=bull_bars, bear_bars=bear_bars, neut_bars=neut_bars,
    )

    return BacktestOutcome(
        params=params, cost_profile=profile, trades=trades,
        equity=equity_curve, metrics=metrics, warnings=warnings,
    )


# -------------- helpers --------------

def _days_for_warmup(interval: str, bars: int) -> int:
    per_day = {"1m": 390, "15m": 26, "1h": 7, "1d": 1, "1w": 1/5, "1mo": 1/22}
    return max(60, int(bars / per_day.get(interval, 1)) + 5)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


async def _load_bars(session, asset_id, interval, start, end) -> list[PriceBar]:
    stmt = (
        select(PriceBar)
        .where(
            PriceBar.asset_id == asset_id,
            PriceBar.interval == interval,
            PriceBar.bar_time >= start,
            PriceBar.bar_time <= end,
        )
        .order_by(PriceBar.bar_time.asc())
    )
    rows = list((await session.execute(stmt)).scalars().all())
    for r in rows:
        r.bar_time = _as_utc(r.bar_time)
        r.available_at = _as_utc(r.available_at)
        r.ingest_time = _as_utc(r.ingest_time)
        r.event_time = _as_utc(r.event_time)
    return rows


def _build_input(
    asset: Asset, interval: str, as_of: datetime,
    bars: list[PriceBar], bench_bars: list[PriceBar],
    benchmark_asset: Asset | None,
) -> SignalInput:
    aligned = _align_by_time(bars, bench_bars) if bench_bars else None
    return SignalInput(
        asset_canonical_id=asset.canonical_id,
        market=asset.market,
        quote_currency=asset.quote_currency,
        calendar=asset.calendar,
        is_benchmark=asset.is_benchmark,
        interval=interval,
        as_of=as_of,
        times=[b.bar_time for b in bars],
        open_=[float(b.open) for b in bars],
        high=[float(b.high) for b in bars],
        low=[float(b.low) for b in bars],
        close=[float(b.close) for b in bars],
        volume=[float(b.volume) for b in bars],
        benchmark_close=aligned,
        benchmark_symbol=(benchmark_asset.display_symbol if benchmark_asset else None),
    )


def _bump_regime_counter(regime: str, counters: list[int]) -> None:
    # counters is [bull, bear, neutral]
    if regime == "BULL": counters[0] += 1
    elif regime == "BEAR": counters[1] += 1
    else: counters[2] += 1


def _compute_metrics(
    *, params: BacktestParams, eval_bars: list[PriceBar],
    equity: list[EquityPoint], trades: list[TradeRecord],
    per_bar_returns: list[float], bench_bars: list[PriceBar],
    benchmark_asset: Asset | None,
    bull_bars: int, bear_bars: int, neut_bars: int,
) -> Metrics:
    total_return = equity[-1].strategy_equity - 1.0 if equity else 0.0
    span_days = max(1.0, (eval_bars[-1].bar_time - eval_bars[0].bar_time).days)
    years = span_days / 365.25
    cagr = (equity[-1].strategy_equity ** (1.0 / years) - 1.0) if equity and years > 0 else 0.0

    periods_per_year = _periods_per_year(params.interval)
    if per_bar_returns:
        mean = sum(per_bar_returns) / len(per_bar_returns)
        var = sum((r - mean) ** 2 for r in per_bar_returns) / max(1, len(per_bar_returns) - 1)
        vol_bar = math.sqrt(var)
        vol_ann = vol_bar * math.sqrt(periods_per_year)
        sharpe = (mean * periods_per_year) / vol_ann if vol_ann > 0 else 0.0
        downside = [min(0.0, r) for r in per_bar_returns]
        down_var = sum(r * r for r in downside) / max(1, len(downside) - 1)
        down_ann = math.sqrt(down_var * periods_per_year)
        sortino = (mean * periods_per_year) / down_ann if down_ann > 0 else 0.0
    else:
        vol_ann = sharpe = sortino = 0.0

    mdd = ind.max_drawdown([e.strategy_equity for e in equity]) if equity else 0.0
    calmar = (cagr / mdd) if mdd > 0 else 0.0

    wins = [t for t in trades if t.pnl_pct > 0]
    losses = [t for t in trades if t.pnl_pct <= 0]
    win_rate = (len(wins) / len(trades)) if trades else 0.0
    gross_profit = sum(t.pnl_pct for t in wins)
    gross_loss = -sum(t.pnl_pct for t in losses)
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if wins else 0.0)
    turnover = (len(trades) / years) if years > 0 else 0.0
    avg_hold = (sum(t.bars_held for t in trades) / len(trades)) if trades else 0.0
    exposure = (sum(1 for e in equity if e.in_position) / len(equity)) if equity else 0.0

    buy_hold_return = equity[-1].buy_hold_equity - 1.0 if equity else 0.0

    # SMA-crossover baseline (200-vs-50 SMA on the same eval window)
    closes = [float(b.close) for b in eval_bars]
    sma_short = ind.sma(closes, 50)
    sma_long = ind.sma(closes, 200)
    sma_baseline_eq = 1.0
    in_pos = False
    for i in range(1, len(closes)):
        if math.isnan(sma_short[i - 1]) or math.isnan(sma_long[i - 1]):
            continue
        want = sma_short[i - 1] > sma_long[i - 1]
        if want:
            r = closes[i] / closes[i - 1] - 1.0
            sma_baseline_eq *= 1 + r
        in_pos = want
    _ = in_pos
    sma_baseline_return = sma_baseline_eq - 1.0

    benchmark_return: float | None = None
    if bench_bars:
        aligned_first = next((b for b in bench_bars if b.bar_time >= eval_bars[0].bar_time), None)
        aligned_last = None
        for b in reversed(bench_bars):
            if b.bar_time <= eval_bars[-1].bar_time:
                aligned_last = b
                break
        if aligned_first and aligned_last and float(aligned_first.close) > 0:
            benchmark_return = float(aligned_last.close) / float(aligned_first.close) - 1.0

    return Metrics(
        total_return=total_return, cagr=cagr,
        volatility=vol_ann, sharpe=sharpe, sortino=sortino,
        max_drawdown=mdd, calmar=calmar,
        win_rate=win_rate, profit_factor=profit_factor,
        turnover=turnover, trades=len(trades),
        avg_holding_bars=avg_hold, exposure=exposure,
        hit_rate=win_rate,
        buy_hold_return=buy_hold_return,
        cash_return=0.0,
        sma_baseline_return=sma_baseline_return,
        benchmark_return=benchmark_return,
        bars_bull=bull_bars, bars_bear=bear_bars, bars_neutral=neut_bars,
    )


def _periods_per_year(interval: str) -> int:
    return {
        "1m": 252 * 390,
        "15m": 252 * 26,
        "1h": 252 * 7,
        "1d": 252,
        "1w": 52,
        "1mo": 12,
    }.get(interval, 252)


# Silence "imported but unused" — keep public reference stable
_ = SignalModel
