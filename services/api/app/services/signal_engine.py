"""Signal engine.

Loads bars + benchmark bars up to ``as_of``, filters them by
``available_at``, runs the selected model, wraps the output in the API
envelope, and persists a signal + factor rows for later inspection.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import blake2b

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.asset_id import AssetId
from app.models.asset import Asset
from app.models.market_data import PriceBar
from app.models.signal import Signal, SignalFactor, SignalModelVersion
from app.providers.registry import get_registry
from app.quant.ensemble import RuleBasedEnsemble
from app.quant.models_base import ModelOutput, SignalInput, SignalModel
from app.services.bar_repository import BarRepository

log = get_logger(__name__)


_DISCLAIMER = (
    "Model output for research/educational purposes only. Not investment "
    "advice. Signals are not recommendations. Past performance does not "
    "indicate future results."
)

_BENCHMARK_BY_MARKET = {
    "US": "ETF:US:NYSE:SPY",
    "VN": "INDEX:VN:HOSE:VNINDEX",
    "COINBASE": "CRYPTO:COINBASE:BTC-USD",
}

_HORIZONS = ("1D", "5D", "20D")

# Registry of installed models. New models plug in here.
_MODEL_INSTANCES: dict[str, SignalModel] = {
    RuleBasedEnsemble.code: RuleBasedEnsemble(),
}


@dataclass(frozen=True, slots=True)
class SignalResult:
    payload: dict
    signal_row: Signal


def available_models() -> list[SignalModel]:
    return list(_MODEL_INSTANCES.values())


def get_model(code: str) -> SignalModel:
    if code not in _MODEL_INSTANCES:
        raise KeyError(f"unknown signal model: {code!r}")
    return _MODEL_INSTANCES[code]


async def calculate_signal(
    session: AsyncSession,
    *,
    asset: Asset,
    horizon: str,
    as_of: datetime | None = None,
    model_code: str = RuleBasedEnsemble.code,
    interval: str = "1d",
    lookback_bars: int = 300,
    persist: bool = True,
) -> SignalResult:
    if horizon not in _HORIZONS:
        raise ValueError(f"horizon must be one of {_HORIZONS}")
    as_of = (as_of or datetime.now(UTC)).astimezone(UTC)
    model = get_model(model_code)

    # Load bars for the asset + benchmark, filtered by available_at.
    reg = get_registry()
    repo = BarRepository(session)
    provider = reg.market_data_for(asset.market)

    lookback_days = _days_for_lookback(interval, lookback_bars)
    start = as_of - timedelta(days=lookback_days)
    await repo.get_or_fetch(asset, provider, interval=interval, start=start, end=as_of)
    bars = await _load_available_bars(session, asset.id, interval, start, as_of)

    benchmark_asset: Asset | None = None
    benchmark_bars: list[PriceBar] = []
    bench_id = _BENCHMARK_BY_MARKET.get(asset.market)
    if bench_id and bench_id != asset.canonical_id:
        benchmark_asset = (await session.execute(
            select(Asset).where(Asset.canonical_id == bench_id)
        )).scalar_one_or_none()
        if benchmark_asset is not None:
            bench_provider = reg.market_data_for(benchmark_asset.market)
            await repo.get_or_fetch(
                benchmark_asset, bench_provider,
                interval=interval, start=start, end=as_of,
            )
            benchmark_bars = await _load_available_bars(
                session, benchmark_asset.id, interval, start, as_of,
            )

    aligned_bench_close = _align_by_time(bars, benchmark_bars)

    si = SignalInput(
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
        benchmark_close=aligned_bench_close,
        benchmark_symbol=(benchmark_asset.display_symbol if benchmark_asset else None),
    )

    if len(bars) < 10:
        payload = _insufficient_data_payload(asset, as_of, horizon, model, len(bars))
        signal_row: Signal | None = None
        if persist:
            signal_row = await _persist(
                session, asset=asset, model=model, as_of=as_of, horizon=horizon,
                classification=payload["classification"],
                score=Decimal("0"), confidence=Decimal("0.000"),
                risk=payload["risk"], data_quality=Decimal("0.000"),
                regime="UNKNOWN", data_version=_data_version(bars),
                payload=payload, factors=[],
            )
        return SignalResult(payload=payload, signal_row=signal_row or _dummy_signal(asset))

    out = model.compute(si, horizon=horizon)

    classification = _classify(out.score, out.data_quality)
    confidence = _confidence(out, len(bars))
    risk = _risk(out, bars)
    payload = _build_payload(
        asset=asset, as_of=as_of, horizon=horizon, model=model,
        out=out, classification=classification, confidence=confidence,
        risk=risk, data_version=_data_version(bars), bars=bars,
    )

    signal_row = None
    if persist:
        signal_row = await _persist(
            session, asset=asset, model=model, as_of=as_of, horizon=horizon,
            classification=classification,
            score=Decimal(f"{out.score:.2f}"),
            confidence=Decimal(f"{confidence:.3f}"),
            risk=risk,
            data_quality=Decimal(f"{out.data_quality:.3f}"),
            regime=out.regime, data_version=_data_version(bars),
            payload=payload, factors=out.factors,
        )

    return SignalResult(payload=payload, signal_row=signal_row or _dummy_signal(asset))


# ---------- helpers ----------

def _days_for_lookback(interval: str, bars: int) -> int:
    per_day = {"1m": 390, "15m": 26, "1h": 7, "1d": 1, "1w": 1/5, "1mo": 1/22}
    d = per_day.get(interval, 1)
    return max(30, int(bars / d) + 5)


def _as_utc(dt: datetime) -> datetime:
    """Coerce a naive datetime (as returned by SQLite) to UTC-aware.
    Postgres returns aware datetimes already; this is a no-op there.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


async def _load_available_bars(
    session: AsyncSession, asset_id: int, interval: str,
    start: datetime, as_of: datetime,
) -> list[PriceBar]:
    stmt = (
        select(PriceBar)
        .where(
            PriceBar.asset_id == asset_id,
            PriceBar.interval == interval,
            PriceBar.bar_time >= start,
            PriceBar.bar_time <= as_of,
            PriceBar.available_at <= as_of,   # <-- no-lookahead safeguard
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


def _align_by_time(asset_bars: list[PriceBar], bench_bars: list[PriceBar]) -> list[float] | None:
    if not bench_bars:
        return None
    by_time = {b.bar_time: float(b.close) for b in bench_bars}
    aligned: list[float] = []
    last = float("nan")
    for b in asset_bars:
        v = by_time.get(b.bar_time)
        if v is not None:
            last = v
        aligned.append(last)
    # If we never had a valid benchmark close, treat as absent
    if all(v != v for v in aligned):
        return None
    return aligned


def _classify(score: float, data_quality: float) -> str:
    if data_quality < 0.4:
        return "INSUFFICIENT_DATA"
    if score >= 60: return "STRONG_BULLISH"
    if score >= 20: return "BULLISH"
    if score <= -60: return "STRONG_BEARISH"
    if score <= -20: return "BEARISH"
    return "NEUTRAL"


def _confidence(out: ModelOutput, n_bars: int) -> float:
    # (1) factor agreement: fraction of factors whose sign matches the score sign
    if not out.factors:
        return 0.0
    same_sign = sum(1 for f in out.factors if _sign(f.contribution) == _sign(out.score))
    agreement = same_sign / len(out.factors)
    # (2) data completeness
    completeness = min(1.0, n_bars / 200.0)
    # (3) magnitude — a very small |score| means we're barely off neutral
    magnitude = min(1.0, abs(out.score) / 60.0)
    raw = 0.4 * agreement + 0.4 * out.data_quality + 0.2 * (0.5 * completeness + 0.5 * magnitude)
    return round(max(0.0, min(1.0, raw)), 3)


def _sign(x: float) -> int:
    if x > 0: return 1
    if x < 0: return -1
    return 0


def _risk(out: ModelOutput, bars: list[PriceBar]) -> str:
    # crude: ATR% + drawdown drive risk class
    if len(bars) < 20 or bars[-1].close <= 0:
        return "MODERATE"
    from app.quant.indicators import atr, max_drawdown
    a = atr([float(b.high) for b in bars], [float(b.low) for b in bars],
            [float(b.close) for b in bars], 14)
    last_atr = 0.0
    for v in reversed(a):
        if v == v:
            last_atr = v
            break
    atr_pct = last_atr / float(bars[-1].close)
    mdd = max_drawdown([float(b.close) for b in bars[-60:]])
    if atr_pct > 0.08 or mdd > 0.30:
        return "SEVERE" if (atr_pct > 0.12 or mdd > 0.45) else "HIGH"
    if atr_pct > 0.03 or mdd > 0.15:
        return "MODERATE"
    return "LOW"


def _data_version(bars: list[PriceBar]) -> str:
    """Deterministic hash of (last bar time, count) so a repeat call
    with the same inputs produces the same version tag.
    """
    if not bars:
        return "empty"
    h = blake2b(digest_size=6)
    h.update(str(len(bars)).encode())
    h.update(bars[-1].bar_time.isoformat().encode())
    h.update(str(float(bars[-1].close)).encode())
    return f"bars-{h.hexdigest()}"


def _build_payload(
    *, asset: Asset, as_of: datetime, horizon: str, model: SignalModel,
    out: ModelOutput, classification: str, confidence: float, risk: str,
    data_version: str, bars: list[PriceBar],
) -> dict:
    last_bar_time = bars[-1].bar_time if bars else None
    data_fresh_seconds = int((as_of - last_bar_time).total_seconds()) if last_bar_time else -1
    expected_holding = {"1D": 1, "5D": 5, "20D": 20}[horizon]
    data_source = bars[-1].source if bars else "unknown"
    # Spec §9: data_freshness as an enum. Thresholds: <2h = CURRENT,
    # <7d = STALE, else UNAVAILABLE. Crypto (24/7) uses a tighter bound.
    if data_fresh_seconds < 0:
        data_freshness = "UNAVAILABLE"
    elif asset.calendar == "24x7":
        data_freshness = "CURRENT" if data_fresh_seconds < 3600 else "STALE"
    else:
        data_freshness = (
            "CURRENT" if data_fresh_seconds < 26 * 3600  # ~1 trading day
            else "STALE"
        )
    expected_holding_period = {"1D": "1 trading day", "5D": "3-7 trading days",
                                "20D": "10-30 trading days"}[horizon]
    combined_warnings = list(out.liquidity_warnings) + list(out.contradictions)
    return {
        "asset_id": asset.canonical_id,
        "as_of": as_of.isoformat(),
        # Spec §9 field names (canonical going forward)
        "model_version": model.code,
        "data_source": data_source,
        "data_freshness": data_freshness,
        "expected_holding_period": expected_holding_period,
        "warnings": combined_warnings,
        # Existing / aliased fields (kept for back-compat with the current UI)
        "data_fresh_seconds": data_fresh_seconds,
        "horizon": horizon,
        "classification": classification,
        "score": round(out.score, 2),
        "confidence": confidence,
        "risk": risk,
        "expected_holding_days": expected_holding,
        "entry_zone": (
            [f"{out.entry_zone[0]:.6f}", f"{out.entry_zone[1]:.6f}"]
            if out.entry_zone else None
        ),
        "invalidation": f"{out.invalidation:.6f}" if out.invalidation is not None else None,
        "take_profit": [f"{x:.6f}" for x in out.take_profit] or None,
        "positive_factors": [
            {"code": f.code, "label": f.label, "contribution": round(f.contribution, 3),
             "detail": f.detail}
            for f in out.positive_factors
        ],
        "negative_factors": [
            {"code": f.code, "label": f.label, "contribution": round(f.contribution, 3),
             "detail": f.detail}
            for f in out.negative_factors
        ],
        "contradictions": out.contradictions,
        "liquidity_warnings": out.liquidity_warnings,
        "data_quality_score": out.data_quality,
        "regime": out.regime,
        "backtest": None,   # attached by the backtest API when requested
        "strategy_version": model.code,   # alias of model_version
        "data_version": data_version,
        "generated_at": datetime.now(UTC).isoformat(),
        "disclaimer": _DISCLAIMER,
    }


def _insufficient_data_payload(
    asset: Asset, as_of: datetime, horizon: str, model: SignalModel, n_bars: int,
) -> dict:
    period = {"1D": "1 trading day", "5D": "3-7 trading days",
              "20D": "10-30 trading days"}[horizon]
    warn = [f"only {n_bars} bars available; need >= 10"]
    return {
        "asset_id": asset.canonical_id,
        "as_of": as_of.isoformat(),
        "model_version": model.code,
        "data_source": "none",
        "data_freshness": "UNAVAILABLE",
        "expected_holding_period": period,
        "warnings": list(warn),
        "data_fresh_seconds": -1,
        "horizon": horizon,
        "classification": "INSUFFICIENT_DATA",
        "score": 0,
        "confidence": 0,
        "risk": "MODERATE",
        "expected_holding_days": {"1D": 1, "5D": 5, "20D": 20}[horizon],
        "entry_zone": None, "invalidation": None, "take_profit": None,
        "positive_factors": [], "negative_factors": [],
        "contradictions": [],
        "liquidity_warnings": warn,
        "data_quality_score": 0.0,
        "regime": "UNKNOWN",
        "backtest": None,
        "strategy_version": model.code,
        "data_version": "empty",
        "generated_at": datetime.now(UTC).isoformat(),
        "disclaimer": _DISCLAIMER,
    }


def _dummy_signal(asset: Asset) -> Signal:
    """Placeholder for the return type when persist=False (not persisted).

    We keep the API of ``calculate_signal`` uniform. Callers that need
    the row read from persist=True.
    """
    s = Signal()
    s.asset_id = asset.id
    return s


async def _get_or_create_model_version(
    session: AsyncSession, model: SignalModel,
) -> SignalModelVersion:
    existing = (await session.execute(
        select(SignalModelVersion).where(SignalModelVersion.code == model.code)
    )).scalar_one_or_none()
    if existing is not None:
        return existing
    row = SignalModelVersion(
        code=model.code,
        family=model.family,
        description=model.description,
        params_json=json.dumps({}, sort_keys=True),
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return row


async def _persist(
    session: AsyncSession, *,
    asset: Asset, model: SignalModel, as_of: datetime, horizon: str,
    classification: str, score: Decimal, confidence: Decimal, risk: str,
    data_quality: Decimal, regime: str, data_version: str,
    payload: dict, factors,
) -> Signal:
    mv = await _get_or_create_model_version(session, model)
    sig = Signal(
        asset_id=asset.id,
        model_version_id=mv.id,
        as_of=as_of,
        horizon=horizon,
        classification=classification,
        score=score,
        confidence=confidence,
        risk=risk,
        data_quality=data_quality,
        regime=regime,
        data_version=data_version,
        payload_json=json.dumps(payload, default=str),
        generated_at=datetime.now(UTC),
    )
    session.add(sig)
    await session.flush()
    for f in factors:
        session.add(SignalFactor(
            signal_id=sig.id,
            code=f.code, label=f.label, category=f.category,
            contribution=Decimal(f"{f.contribution:.3f}"),
            detail=f.detail,
        ))
    await session.commit()
    return sig


# Ensure the imported AssetId symbol isn't flagged as unused when the
# type isn't referenced at call sites but is part of the public API.
_ = AssetId
