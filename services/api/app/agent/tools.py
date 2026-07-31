"""Server-side tool handlers.

Rules (see ``AGENTS.md`` §3-4 and ``docs/agent-security.md``):
  * Only tools listed in ``ALLOWED_TOOLS`` are dispatchable.
  * All arguments pass through the strict Pydantic schema in ``schemas.py``.
  * Tool results are structured dicts. They will be wrapped by the
    orchestrator in a delimited untrusted-content block before being fed
    back to the LLM.
  * Handlers must NEVER produce a directional trading signal or an
    absolute price — those come from the signal engine and providers
    respectively.
  * Handlers must NEVER read secrets. They only touch DB rows they were
    given permission to read.
"""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.schemas import (
    CalculateSignalArgs,
    CompareAssetsArgs,
    GetCalculatedIndicatorsArgs,
    GetHistoricalBarsArgs,
    GetMarketStatusArgs,
    GetQuoteArgs,
    ResolveAssetArgs,
    RunBacktestArgs,
    SearchStubArgs,
)
from app.core.logging import get_logger
from app.domain.asset_id import AssetId
from app.models.asset import Asset
from app.providers.registry import get_registry
from app.quant import indicators as ind
from app.services.backtester import BacktestParams, run_backtest
from app.services.bar_repository import BarRepository
from app.services.market_status import all_statuses, status_for
from app.services.signal_engine import calculate_signal
from app.services.symbol_resolver import search_assets

log = get_logger(__name__)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    schema_cls: type
    is_search_stub: bool = False


ALLOWED_TOOLS: dict[str, ToolSpec] = {
    "resolve_asset": ToolSpec(
        name="resolve_asset",
        description=(
            "Look up canonical asset ids by ticker or name across all "
            "supported markets. Returns ALL matches so ambiguity is "
            "explicit. Prefer this before calling any other tool that "
            "takes an asset_canonical_id."
        ),
        schema_cls=ResolveAssetArgs,
    ),
    "get_market_status": ToolSpec(
        name="get_market_status",
        description="Returns open/closed state and next transition for supported market calendars.",
        schema_cls=GetMarketStatusArgs,
    ),
    "get_quote": ToolSpec(
        name="get_quote",
        description=(
            "Fetch the last known quote for an asset from its configured "
            "provider. Always returns the source, event_time, currency, "
            "and staleness. Do NOT invent a current price."
        ),
        schema_cls=GetQuoteArgs,
    ),
    "get_historical_bars": ToolSpec(
        name="get_historical_bars",
        description="Fetch OHLCV bars for an asset over a lookback window. Cached and audited.",
        schema_cls=GetHistoricalBarsArgs,
    ),
    "get_calculated_indicators": ToolSpec(
        name="get_calculated_indicators",
        description=(
            "Compute deterministic technical indicators (SMA/EMA/RSI/MACD/"
            "ATR/realized-vol/momentum) over the requested lookback. "
            "Values are computed by the quantitative library, not by the "
            "language model."
        ),
        schema_cls=GetCalculatedIndicatorsArgs,
    ),
    "calculate_signal": ToolSpec(
        name="calculate_signal",
        description=(
            "Ask the versioned signal engine for a signal. This is the "
            "ONLY authoritative source of a directional signal, score, "
            "confidence, and risk class. The model must not synthesize "
            "these values from natural language."
        ),
        schema_cls=CalculateSignalArgs,
    ),
    "run_backtest": ToolSpec(
        name="run_backtest",
        description=(
            "Walk-forward backtest of ensemble-v1 with configurable "
            "thresholds. Returns metrics vs buy&hold, SMA baseline, and "
            "benchmark; costs applied per side."
        ),
        schema_cls=RunBacktestArgs,
    ),
    "compare_assets": ToolSpec(
        name="compare_assets",
        description=(
            "Compare 2-5 assets over the same window; returns aligned "
            "closes rebased to 100, plus per-asset period returns and "
            "quote currencies."
        ),
        schema_cls=CompareAssetsArgs,
    ),
    # ----- search tools: skeletons -----
    # Advertised so the model can plan queries, but they always return
    # status=not_available. When asked to cite filings/news, the agent
    # MUST abstain honestly rather than inventing sources.
    "search_sec_filings": ToolSpec(
        name="search_sec_filings",
        description="[Phase 4.1] SEC EDGAR filing search. Currently returns not_available.",
        schema_cls=SearchStubArgs, is_search_stub=True,
    ),
    "search_vietnam_disclosures": ToolSpec(
        name="search_vietnam_disclosures",
        description="[Phase 4.1] HOSE/HNX/UPCOM disclosure search. Currently returns not_available.",
        schema_cls=SearchStubArgs, is_search_stub=True,
    ),
    "search_company_announcements": ToolSpec(
        name="search_company_announcements",
        description="[Phase 4.1] Company IR / official announcement search. Currently returns not_available.",
        schema_cls=SearchStubArgs, is_search_stub=True,
    ),
    "search_crypto_project_announcements": ToolSpec(
        name="search_crypto_project_announcements",
        description="[Phase 4.1] Official crypto project / exchange announcement search. Currently returns not_available.",
        schema_cls=SearchStubArgs, is_search_stub=True,
    ),
    "search_approved_news_sources": ToolSpec(
        name="search_approved_news_sources",
        description="[Phase 4.1] Curated news source search. Currently returns not_available.",
        schema_cls=SearchStubArgs, is_search_stub=True,
    ),
}


class ToolValidationError(Exception):
    pass


class ToolExecutor:
    """Validates args, dispatches to a handler, returns a plain dict."""

    def __init__(self, session: AsyncSession):
        self._s = session
        self._handlers: dict[str, Callable[[Any], Awaitable[dict]]] = {
            "resolve_asset": self._resolve_asset,
            "get_market_status": self._get_market_status,
            "get_quote": self._get_quote,
            "get_historical_bars": self._get_historical_bars,
            "get_calculated_indicators": self._get_calculated_indicators,
            "calculate_signal": self._calculate_signal,
            "run_backtest": self._run_backtest,
            "compare_assets": self._compare_assets,
        }

    async def execute(self, name: str, raw_args: dict) -> tuple[dict, int]:
        """Return ``(result_dict, duration_ms)``. Raises on invalid tool
        name or invalid args."""
        spec = ALLOWED_TOOLS.get(name)
        if spec is None:
            raise ToolValidationError(f"unknown tool: {name!r}")
        try:
            args = spec.schema_cls.model_validate(raw_args)
        except Exception as e:
            raise ToolValidationError(f"invalid args for {name}: {e}") from e

        started = time.perf_counter()
        if spec.is_search_stub:
            result = _search_stub_result(name, args.model_dump())
        else:
            result = await self._handlers[name](args)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return result, duration_ms

    # ---------- handlers ----------

    async def _resolve_asset(self, args: ResolveAssetArgs) -> dict:
        hits = await search_assets(
            self._s, query=args.query,
            market=args.market, asset_type=args.asset_type, limit=10,
        )
        return {
            "query": args.query,
            "match_count": len(hits),
            "matches": [
                {
                    "canonical_id": a.canonical_id,
                    "display_symbol": a.display_symbol,
                    "name": a.name,
                    "market": a.market,
                    "asset_type": a.asset_type,
                    "quote_currency": a.quote_currency,
                }
                for a in hits
            ],
            "ambiguous": len(hits) > 1,
        }

    async def _get_market_status(self, args: GetMarketStatusArgs) -> dict:
        rows = all_statuses()
        if args.market == "US":
            rows = [r for r in rows if r.market == "US"]
        elif args.market == "VN":
            rows = [r for r in rows if r.market == "VN"]
        elif args.market == "CRYPTO":
            rows = [r for r in rows if r.calendar == "24x7"]
        return {
            "markets": [
                {
                    "market": r.market, "calendar": r.calendar,
                    "state": r.state, "is_open": r.is_open,
                    "next_open_utc": r.next_open_utc.isoformat() if r.next_open_utc else None,
                    "next_close_utc": r.next_close_utc.isoformat() if r.next_close_utc else None,
                }
                for r in rows
            ],
        }

    async def _get_quote(self, args: GetQuoteArgs) -> dict:
        asset = await self._load_asset(args.asset_canonical_id)
        aid = AssetId.parse(asset.canonical_id)
        provider = get_registry().market_data_for(asset.market)
        q = await provider.get_quote(aid)
        ms = status_for(asset.calendar)
        market_state = ms.state if ms else "UNKNOWN"
        return {
            "asset_canonical_id": asset.canonical_id,
            "price": str(q.price),
            "currency": q.currency,
            "event_time": q.event_time.isoformat(),
            "source": q.source,
            "is_stale": q.is_stale,
            "market_state": market_state,
        }

    async def _get_historical_bars(self, args: GetHistoricalBarsArgs) -> dict:
        asset = await self._load_asset(args.asset_canonical_id)
        end = datetime.now(UTC)
        start = end - timedelta(days=args.lookback_days)
        provider = get_registry().market_data_for(asset.market)
        repo = BarRepository(self._s)
        result = await repo.get_or_fetch(
            asset, provider, interval=args.interval, start=start, end=end,
        )
        bars = result.bars
        # Cap the number of bars returned to the model for token safety.
        max_bars = 250
        head = bars[-max_bars:]
        return {
            "asset_canonical_id": asset.canonical_id,
            "interval": args.interval,
            "source": result.source,
            "from_cache": result.from_cache,
            "bar_count": len(bars),
            "returned_count": len(head),
            "last_bar_time": head[-1].bar_time.isoformat() if head else None,
            "bars": [
                {"t": b.bar_time.isoformat(),
                 "o": str(b.open), "h": str(b.high),
                 "l": str(b.low),  "c": str(b.close),
                 "v": str(b.volume)}
                for b in head
            ],
        }

    async def _get_calculated_indicators(self, args: GetCalculatedIndicatorsArgs) -> dict:
        asset = await self._load_asset(args.asset_canonical_id)
        end = datetime.now(UTC)
        start = end - timedelta(days=args.lookback_days)
        provider = get_registry().market_data_for(asset.market)
        repo = BarRepository(self._s)
        result = await repo.get_or_fetch(
            asset, provider, interval=args.interval, start=start, end=end,
        )
        closes = [float(b.close) for b in result.bars]
        highs  = [float(b.high) for b in result.bars]
        lows   = [float(b.low) for b in result.bars]
        vols   = [float(b.volume) for b in result.bars]
        wanted = set(args.indicators) or {
            "sma20", "sma50", "ema20", "ema60", "rsi14", "macd", "atr14",
            "realized_vol20", "momentum_20", "momentum_60",
        }
        out: dict[str, Any] = {}
        if "sma20" in wanted: out["sma20"]  = ind.last_finite(ind.sma(closes, 20))
        if "sma50" in wanted: out["sma50"]  = ind.last_finite(ind.sma(closes, 50))
        if "sma200" in wanted: out["sma200"] = ind.last_finite(ind.sma(closes, 200))
        if "ema20" in wanted: out["ema20"]  = ind.last_finite(ind.ema(closes, 20))
        if "ema60" in wanted: out["ema60"]  = ind.last_finite(ind.ema(closes, 60))
        if "rsi14" in wanted: out["rsi14"]  = ind.last_finite(ind.rsi(closes, 14))
        if "atr14" in wanted: out["atr14"]  = ind.last_finite(ind.atr(highs, lows, closes, 14))
        if "realized_vol20" in wanted:
            out["realized_vol20"] = ind.last_finite(ind.realized_vol(closes, 20))
        if "momentum_20" in wanted:
            out["momentum_20"] = ind.last_finite(ind.momentum(closes, 20))
        if "momentum_60" in wanted:
            out["momentum_60"] = ind.last_finite(ind.momentum(closes, 60))
        if "macd" in wanted:
            line, sig, hist = ind.macd(closes, 12, 26, 9)
            out["macd"] = {
                "line": ind.last_finite(line),
                "signal": ind.last_finite(sig),
                "hist": ind.last_finite(hist),
            }
        _ = vols  # reserved for future rvol computation
        return {
            "asset_canonical_id": asset.canonical_id,
            "interval": args.interval,
            "as_of": (result.bars[-1].bar_time.isoformat() if result.bars else None),
            "source": result.source,
            "indicators": out,
        }

    async def _calculate_signal(self, args: CalculateSignalArgs) -> dict:
        asset = await self._load_asset(args.asset_canonical_id)
        res = await calculate_signal(
            self._s, asset=asset, horizon=args.horizon,
            model_code=args.model, persist=True,
        )
        # Return the full payload — the model needs it, but must NOT
        # rewrite its numbers.
        return res.payload

    async def _run_backtest(self, args: RunBacktestArgs) -> dict:
        asset = await self._load_asset(args.asset_canonical_id)
        end = datetime.now(UTC)
        start = end - timedelta(days=args.lookback_days)
        outcome = await run_backtest(self._s, BacktestParams(
            asset=asset, interval=args.interval, start=start, end=end,
            horizon=args.horizon,
            entry_threshold=args.entry_threshold,
            exit_threshold=args.exit_threshold,
        ))
        m = outcome.metrics
        return {
            "asset_canonical_id": asset.canonical_id,
            "horizon": args.horizon,
            "interval": args.interval,
            "trades": m.trades,
            "total_return": m.total_return,
            "cagr": m.cagr,
            "sharpe": m.sharpe,
            "sortino": m.sortino,
            "max_drawdown": m.max_drawdown,
            "win_rate": m.win_rate,
            "profit_factor": (
                "inf" if m.profit_factor == float("inf") else m.profit_factor
            ),
            "buy_hold_return": m.buy_hold_return,
            "sma_baseline_return": m.sma_baseline_return,
            "benchmark_return": m.benchmark_return,
            "warnings": outcome.warnings,
        }

    async def _compare_assets(self, args: CompareAssetsArgs) -> dict:
        results = []
        currencies: set[str] = set()
        for cid in args.asset_canonical_ids:
            asset = await self._load_asset(cid)
            currencies.add(asset.quote_currency)
            end = datetime.now(UTC)
            start = end - timedelta(days=args.lookback_days)
            provider = get_registry().market_data_for(asset.market)
            repo = BarRepository(self._s)
            r = await repo.get_or_fetch(
                asset, provider, interval=args.interval, start=start, end=end,
            )
            closes = [float(b.close) for b in r.bars]
            first, last = (closes[0], closes[-1]) if len(closes) >= 2 else (None, None)
            period_return = None
            if first and last:
                period_return = (last - first) / first
            results.append({
                "asset_canonical_id": asset.canonical_id,
                "display_symbol": asset.display_symbol,
                "quote_currency": asset.quote_currency,
                "bar_count": len(closes),
                "period_return": period_return,
                "first_close": first,
                "last_close": last,
            })
        return {
            "interval": args.interval,
            "lookback_days": args.lookback_days,
            "mixed_currencies": len(currencies) > 1,
            "currencies": sorted(currencies),
            "series": results,
        }

    # ---------- helpers ----------

    async def _load_asset(self, canonical_id: str) -> Asset:
        row = (await self._s.execute(
            select(Asset).where(Asset.canonical_id == canonical_id)
        )).scalar_one_or_none()
        if row is None:
            raise ToolValidationError(f"asset not found: {canonical_id}")
        return row


def _search_stub_result(name: str, args: dict) -> dict:
    return {
        "status": "not_available",
        "tool": name,
        "reason": (
            "This search tool is a Phase 4.1 deliverable. Ingested source "
            "documents (SEC filings, VN disclosures, official IR/exchange "
            "announcements, curated news) are not yet indexed in this "
            "environment. If the user is asking for information that "
            "requires citing external sources, the agent MUST abstain and "
            "say so, rather than fabricating a citation."
        ),
        "matches": [],
        "args_echo": args,
    }
