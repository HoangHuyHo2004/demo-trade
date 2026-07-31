"""Dataset builder — pulls point-in-time bars and computes features + labels.

Row layout (each row is one (asset, timestamp, horizon) triple):

  asset_canonical_id, bar_time, horizon, <features>, direction_label,
  future_return, future_vol, future_mdd

Every row is a self-contained training / inference example. Feature
values are computed using ONLY bars whose ``available_at <= bar_time``;
label values are computed using closes at bar_time and bar_time + H
(labels are naturally future-referencing, which is fine because they're
not fed to the model at inference).

Version: dataset_version is a deterministic hash of the inputs +
FEATURE_VERSION + TARGET_VERSION so re-running with identical inputs
produces the same version.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.ml import FEATURE_VERSION, TARGET_VERSION, UNIVERSE_VERSION
from app.ml.features import build_features, feature_names
from app.ml.labels import compute_labels
from app.models.asset import Asset
from app.models.market_data import PriceBar

log = get_logger(__name__)


@dataclass(frozen=True)
class BuildParams:
    market: str
    horizon_bars: int
    interval: str = "1d"
    cost_bps: float = 5.0
    from_time: datetime | None = None
    to_time: datetime | None = None
    warmup_bars: int = 200
    max_rows_per_asset: int = 3000


@dataclass
class DatasetTable:
    market: str
    interval: str
    horizon: int
    feature_names: list[str]
    rows: list[dict[str, Any]]
    dataset_version: str
    from_time: datetime | None
    to_time: datetime | None
    universe: list[str]


def compute_dataset_version(
    market: str, interval: str, horizon: int, cost_bps: float,
    from_time: datetime | None, to_time: datetime | None, universe: list[str],
) -> str:
    h = hashlib.blake2b(digest_size=12)
    h.update(FEATURE_VERSION.encode())
    h.update(TARGET_VERSION.encode())
    h.update(UNIVERSE_VERSION.encode())
    h.update(market.encode())
    h.update(interval.encode())
    h.update(f"{horizon}".encode())
    h.update(f"{cost_bps:.4f}".encode())
    if from_time:
        h.update(from_time.isoformat().encode())
    if to_time:
        h.update(to_time.isoformat().encode())
    h.update(",".join(sorted(universe)).encode())
    return f"ds-{h.hexdigest()}"


async def build_dataset(
    session: AsyncSession, params: BuildParams, benchmark_canonical: str | None = None,
) -> DatasetTable:
    """Load bars for every asset in the market, join a benchmark if
    provided, walk each series computing features + labels, return a
    single flat table.
    """
    stmt = select(Asset).where(Asset.market == params.market, Asset.is_active.is_(True))
    assets = list((await session.execute(stmt)).scalars().all())
    universe = [a.canonical_id for a in assets]
    if not assets:
        raise ValueError(f"no assets in market {params.market!r}")

    # Load benchmark closes once, keyed by bar_time.
    bench_closes_by_time: dict[datetime, float] = {}
    if benchmark_canonical:
        bench = (await session.execute(
            select(Asset).where(Asset.canonical_id == benchmark_canonical)
        )).scalar_one_or_none()
        if bench is not None:
            bench_rows = await _load_bars(
                session, bench.id, params.interval, params.from_time, params.to_time,
            )
            bench_closes_by_time = {b.bar_time: float(b.close) for b in bench_rows}

    fnames = feature_names()
    rows: list[dict[str, Any]] = []
    for asset in assets:
        bars = await _load_bars(
            session, asset.id, params.interval, params.from_time, params.to_time,
        )
        if len(bars) < params.warmup_bars + params.horizon_bars + 5:
            log.info("dataset_skip_short_series", asset=asset.canonical_id, bars=len(bars))
            continue

        closes = [float(b.close) for b in bars]
        highs = [float(b.high) for b in bars]
        lows = [float(b.low) for b in bars]
        volumes = [float(b.volume) for b in bars]
        bench_closes_aligned = None
        if bench_closes_by_time:
            bench_closes_aligned = [
                bench_closes_by_time.get(b.bar_time, float("nan")) for b in bars
            ]
            # If we have no benchmark overlap at all, treat as absent
            if all(bc != bc for bc in bench_closes_aligned):  # all NaN
                bench_closes_aligned = None

        # Walk from warmup_bars → n - horizon_bars, computing features up
        # to and including bar[t] and labels using bar[t..t+H].
        t_start = params.warmup_bars
        t_end = len(bars) - params.horizon_bars - 1
        step = max(1, (t_end - t_start) // params.max_rows_per_asset) \
               if (t_end - t_start) > params.max_rows_per_asset else 1
        for t in range(t_start, t_end + 1, step):
            feats = build_features(
                closes=closes[: t + 1],
                highs=highs[: t + 1],
                lows=lows[: t + 1],
                volumes=volumes[: t + 1],
                benchmark_closes=bench_closes_aligned[: t + 1] if bench_closes_aligned else None,
            )
            labels = compute_labels(closes, t, params.horizon_bars, cost_bps=params.cost_bps)
            if labels.direction is None:
                continue
            row: dict[str, Any] = {
                "asset_canonical_id": asset.canonical_id,
                "bar_time": bars[t].bar_time.isoformat(),
                "horizon": params.horizon_bars,
                **{k: feats.get(k, float("nan")) for k in fnames},
                "direction": labels.direction,
                "future_return": labels.future_return,
                "future_vol": labels.future_vol,
                "future_mdd": labels.future_mdd,
            }
            rows.append(row)

    dv = compute_dataset_version(
        params.market, params.interval, params.horizon_bars, params.cost_bps,
        params.from_time, params.to_time, universe,
    )
    return DatasetTable(
        market=params.market, interval=params.interval,
        horizon=params.horizon_bars, feature_names=fnames,
        rows=rows, dataset_version=dv,
        from_time=params.from_time, to_time=params.to_time,
        universe=universe,
    )


async def _load_bars(
    session: AsyncSession, asset_id: int, interval: str,
    from_time: datetime | None, to_time: datetime | None,
) -> list[PriceBar]:
    """Load bars where ``available_at <= to_time`` (or unbounded)."""
    stmt = select(PriceBar).where(
        PriceBar.asset_id == asset_id,
        PriceBar.interval == interval,
    )
    if from_time is not None:
        stmt = stmt.where(PriceBar.bar_time >= from_time)
    if to_time is not None:
        stmt = stmt.where(PriceBar.available_at <= to_time)
    stmt = stmt.order_by(PriceBar.bar_time.asc())
    rows = list((await session.execute(stmt)).scalars().all())
    # Normalize any naive datetimes (SQLite quirk) — the tz handling is
    # covered elsewhere too but doing it here keeps this function usable
    # from the ml_worker directly.
    from datetime import UTC
    for r in rows:
        if r.bar_time.tzinfo is None:
            r.bar_time = r.bar_time.replace(tzinfo=UTC)
        if r.available_at.tzinfo is None:
            r.available_at = r.available_at.replace(tzinfo=UTC)
    return rows


# ---------- walk-forward split (spec §Time-series validation) ----------

@dataclass(frozen=True)
class WalkForwardFold:
    train_from: datetime
    train_to: datetime
    val_from: datetime
    val_to: datetime
    test_from: datetime | None
    test_to: datetime | None


def make_walk_forward_folds(
    *, start: datetime, end: datetime,
    train_days: int, val_days: int, test_days: int, embargo_days: int = 5,
    step_days: int | None = None,
) -> list[WalkForwardFold]:
    """Emit expanding-train / rolling-val (+ optional test) folds with
    an embargo gap so labels that overlap the val/test boundary don't
    leak. Non-random.

    Example (train=730, val=180, test=180, embargo=5) on 5 years of data
    → three folds walking forward.
    """
    step = step_days or (val_days + test_days + embargo_days)
    folds: list[WalkForwardFold] = []
    cursor_train_end = start + timedelta(days=train_days)
    while cursor_train_end + timedelta(days=embargo_days + val_days) <= end:
        val_from = cursor_train_end + timedelta(days=embargo_days)
        val_to = val_from + timedelta(days=val_days)
        test_from: datetime | None = None
        test_to: datetime | None = None
        if val_to + timedelta(days=embargo_days + test_days) <= end:
            test_from = val_to + timedelta(days=embargo_days)
            test_to = test_from + timedelta(days=test_days)
        folds.append(WalkForwardFold(
            train_from=start, train_to=cursor_train_end,
            val_from=val_from, val_to=val_to,
            test_from=test_from, test_to=test_to,
        ))
        cursor_train_end += timedelta(days=step)
    return folds
