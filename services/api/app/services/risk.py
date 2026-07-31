"""Portfolio risk analytics.

Inputs are the ``PortfolioValuation`` from ``portfolio.py`` plus per-asset
close series. Everything here is a pure numeric transformation — no I/O
beyond fetching the close series through ``BarRepository``.

Metrics are informational only. See ``docs/model-risk-management.md``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.providers.registry import get_registry
from app.quant import indicators as ind
from app.services.bar_repository import BarRepository
from app.services.portfolio import PortfolioValuation


@dataclass
class RiskReport:
    portfolio_id: int
    base_currency: str
    as_of: datetime
    total_equity_base: float
    # Composition
    allocation_by_asset: dict[str, float]     # canonical_id → weight (0..1)
    allocation_by_market: dict[str, float]    # market → weight
    hhi_asset: float                          # Herfindahl-Hirschman Index (0..1)
    top_holding_weight: float
    n_holdings: int
    cash_weight: float
    # Historical
    lookback_days: int
    volatility_annualized: float | None
    max_drawdown: float | None
    var_95_1d: float | None                   # positive number = loss fraction of equity
    var_99_1d: float | None
    # Cross-sectional
    correlation_matrix: dict[str, dict[str, float]]
    # Stress
    stress_scenarios: dict[str, float]        # "-10% risk assets" → PnL fraction
    # Warnings
    warnings: list[str]


async def compute_risk(
    session: AsyncSession, val: PortfolioValuation, *, lookback_days: int = 180,
) -> RiskReport:
    equity = _to_float(val.equity_base)
    warnings: list[str] = list(val.warnings)

    # Allocations (positions only, weighted by base-currency market value)
    positions_with_mv = [
        p for p in val.positions
        if p.market_value_base is not None and p.market_value_base > 0
    ]
    total_positions_mv = sum(_to_float(p.market_value_base) for p in positions_with_mv)
    allocation_by_asset: dict[str, float] = {}
    allocation_by_market: dict[str, float] = {}
    if equity > 0:
        for p in positions_with_mv:
            w = _to_float(p.market_value_base) / equity
            allocation_by_asset[p.asset_canonical_id] = w
            allocation_by_market[p.market] = allocation_by_market.get(p.market, 0.0) + w
    cash_weight = 1.0 - (total_positions_mv / equity if equity > 0 else 0.0)

    hhi = sum(w * w for w in allocation_by_asset.values())
    top_w = max(allocation_by_asset.values(), default=0.0)

    # Historical returns per position — needed for portfolio series
    repo = BarRepository(session)
    reg = get_registry()
    end = val.as_of
    start = end - timedelta(days=lookback_days)
    closes_by_asset: dict[str, list[tuple[datetime, float]]] = {}
    for p in positions_with_mv:
        asset = _resolve_asset(session)  # placeholder; replaced below
        # Load the asset object properly for provider selection.
        from sqlalchemy import select as _select
        asset = (await session.execute(
            _select(Asset).where(Asset.canonical_id == p.asset_canonical_id)
        )).scalar_one_or_none()
        if asset is None:
            warnings.append(f"asset {p.asset_canonical_id} not in DB — skipping in risk analytics")
            continue
        provider = reg.market_data_for(asset.market)
        try:
            r = await repo.get_or_fetch(
                asset, provider, interval="1d", start=start, end=end,
            )
        except Exception as e:  # noqa: BLE001
            warnings.append(f"bar fetch failed for {p.asset_canonical_id}: {e}")
            continue
        closes_by_asset[p.asset_canonical_id] = [
            (b.bar_time, float(b.close)) for b in r.bars
        ]

    # Align by intersection of bar times
    aligned = _align_series(closes_by_asset)
    times, per_asset_closes = aligned
    # Per-asset daily log returns
    per_asset_returns: dict[str, list[float]] = {}
    for cid, closes in per_asset_closes.items():
        if len(closes) < 2:
            per_asset_returns[cid] = []
            continue
        import math
        per_asset_returns[cid] = [
            math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))
        ]

    # Portfolio returns (weighted sum, weights = current allocation)
    portfolio_returns: list[float] = []
    if per_asset_returns and any(len(v) for v in per_asset_returns.values()):
        n = min(len(v) for v in per_asset_returns.values() if v)
        for i in range(n):
            rp = 0.0
            for cid, weight in allocation_by_asset.items():
                series = per_asset_returns.get(cid)
                if not series:
                    continue
                rp += weight * series[-n + i]
            portfolio_returns.append(rp)

    # Historical metrics
    vol_ann: float | None = None
    var_95: float | None = None
    var_99: float | None = None
    mdd: float | None = None
    if portfolio_returns:
        import math
        mean = sum(portfolio_returns) / len(portfolio_returns)
        var = sum((r - mean) ** 2 for r in portfolio_returns) / max(1, len(portfolio_returns) - 1)
        vol_ann = math.sqrt(var) * math.sqrt(252)
        losses = sorted(portfolio_returns)
        # historical VaR: 5% worst return → loss fraction (positive)
        idx95 = max(0, int(0.05 * len(losses)) - 1)
        idx99 = max(0, int(0.01 * len(losses)) - 1)
        var_95 = -min(losses[idx95], 0.0)
        var_99 = -min(losses[idx99], 0.0)
        # Reconstruct equity curve for MDD
        equity_curve = [1.0]
        for r in portfolio_returns:
            equity_curve.append(equity_curve[-1] * math.exp(r))
        mdd = ind.max_drawdown(equity_curve)

    # Correlation matrix
    correlation_matrix: dict[str, dict[str, float]] = {}
    codes = list(per_asset_returns.keys())
    for i, a in enumerate(codes):
        correlation_matrix[a] = {}
        for j, b in enumerate(codes):
            correlation_matrix[a][b] = _corr(per_asset_returns[a], per_asset_returns[b])
            _ = j
        _ = i

    # Stress scenarios — a percentage shock to risk assets, cash unchanged
    stress: dict[str, float] = {}
    for label, shock in (("-5% risk assets", -0.05),
                        ("-10% risk assets", -0.10),
                        ("-20% risk assets", -0.20),
                        ("-30% risk assets", -0.30)):
        pnl_pct = (1 - cash_weight) * shock
        stress[label] = pnl_pct

    return RiskReport(
        portfolio_id=val.portfolio_id, base_currency=val.base_currency,
        as_of=val.as_of, total_equity_base=equity,
        allocation_by_asset=allocation_by_asset,
        allocation_by_market=allocation_by_market,
        hhi_asset=hhi, top_holding_weight=top_w,
        n_holdings=len(allocation_by_asset), cash_weight=max(0.0, cash_weight),
        lookback_days=lookback_days,
        volatility_annualized=vol_ann,
        max_drawdown=mdd,
        var_95_1d=var_95, var_99_1d=var_99,
        correlation_matrix=correlation_matrix,
        stress_scenarios=stress,
        warnings=warnings,
    )


def _to_float(x: Decimal | float | None) -> float:
    if x is None:
        return 0.0
    return float(x)


def _resolve_asset(session):
    return None  # placeholder; real resolution done inline (kept for symmetry with tests)


def _align_series(
    closes_by_asset: dict[str, list[tuple[datetime, float]]],
) -> tuple[list[datetime], dict[str, list[float]]]:
    if not closes_by_asset:
        return [], {}
    # Intersection of timestamps
    times_sets = [{t for t, _ in v} for v in closes_by_asset.values()]
    common = sorted(set.intersection(*times_sets)) if times_sets else []
    aligned: dict[str, list[float]] = {}
    for cid, series in closes_by_asset.items():
        m = dict(series)
        aligned[cid] = [m[t] for t in common if t in m]
    return common, aligned


def _corr(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    a = a[-n:]; b = b[-n:]
    ma = sum(a) / n
    mb = sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (n - 1)
    va = sum((a[i] - ma) ** 2 for i in range(n)) / (n - 1)
    vb = sum((b[i] - mb) ** 2 for i in range(n)) / (n - 1)
    import math
    sa = math.sqrt(va) if va > 0 else 0.0
    sb = math.sqrt(vb) if vb > 0 else 0.0
    if sa == 0 or sb == 0:
        return 0.0
    return cov / (sa * sb)


# used by unused-imports lint
_ = UTC
