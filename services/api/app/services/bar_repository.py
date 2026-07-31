"""Historical-bar repository.

Strategy: read from ``price_bars`` for the requested window. If we don't
have enough coverage, fetch from the provider, upsert into the table,
then return the merged, chronologically-sorted result.

Coverage heuristic: we consider a window "covered" when we have at least
90% of the number of bars the interval implies for the calendar (rough,
per market). This lets us serve cached responses fast while still
back-filling gaps automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.asset_id import AssetId
from app.models.asset import Asset
from app.models.ingest import BarIngestRun
from app.models.market_data import PriceBar
from app.providers.base import BarDTO, MarketDataProvider

log = get_logger(__name__)


@dataclass(frozen=True)
class BarWindowResult:
    bars: list[BarDTO]
    source: str
    from_cache: bool


_INTERVAL_APPROX_PER_DAY = {
    "1m": 390,   # US session-ish; we only use this for heuristic
    "15m": 26,
    "1h": 7,
    "1d": 1,
    "1w": 1 / 5,
    "1mo": 1 / 22,
}


def _row_from_dto(asset_pk: int, b: BarDTO) -> dict:
    return {
        "asset_id": asset_pk,
        "interval": b.interval,
        "bar_time": b.bar_time,
        "open": b.open,
        "high": b.high,
        "low": b.low,
        "close": b.close,
        "adj_close": b.adj_close,
        "volume": b.volume,
        "source": b.source,
        "event_time": b.event_time,
        "ingest_time": b.ingest_time,
        "available_at": b.available_at,
    }


def _upsert_stmt(dialect: str, rows: list[dict]):
    """Cross-dialect INSERT ... ON CONFLICT DO UPDATE for the unique key."""
    if dialect == "postgresql":
        stmt = pg_insert(PriceBar).values(rows)
        update_cols = {
            c: getattr(stmt.excluded, c)
            for c in ("open", "high", "low", "close", "adj_close",
                      "volume", "event_time", "ingest_time", "available_at")
        }
        return stmt.on_conflict_do_update(
            constraint="uq_price_bars_asset_interval_time_source",
            set_=update_cols,
        )
    # sqlite (tests) — same shape
    stmt = sqlite_insert(PriceBar).values(rows)
    update_cols = {
        c: getattr(stmt.excluded, c)
        for c in ("open", "high", "low", "close", "adj_close",
                  "volume", "event_time", "ingest_time", "available_at")
    }
    return stmt.on_conflict_do_update(
        index_elements=["asset_id", "interval", "bar_time", "source"],
        set_=update_cols,
    )


class BarRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def load_from_db(
        self, asset: Asset, interval: str, start: datetime, end: datetime
    ) -> list[PriceBar]:
        stmt = (
            select(PriceBar)
            .where(
                and_(
                    PriceBar.asset_id == asset.id,
                    PriceBar.interval == interval,
                    PriceBar.bar_time >= start,
                    PriceBar.bar_time <= end,
                )
            )
            .order_by(PriceBar.bar_time.asc())
        )
        result = await self._s.execute(stmt)
        return list(result.scalars().all())

    async def get_or_fetch(
        self,
        asset: Asset,
        provider: MarketDataProvider,
        *,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> BarWindowResult:
        cached = await self.load_from_db(asset, interval, start, end)
        expected = self._expected_count(interval, start, end)
        # coverage threshold: keep it loose (60%) so we amortize fetches
        if expected == 0 or len(cached) >= 0.6 * expected:
            return BarWindowResult(
                bars=[self._bar_from_row(asset, r) for r in cached],
                source=cached[0].source if cached else provider.slug,
                from_cache=True,
            )

        aid = AssetId.parse(asset.canonical_id)
        started = datetime.now(UTC)
        run = BarIngestRun(
            asset_id=asset.id, provider=provider.slug, interval=interval,
            started_at=started, status="ok",
        )
        self._s.add(run)
        await self._s.flush()

        try:
            fetched = await provider.get_bars(aid, interval=interval, start=start, end=end)
        except Exception as e:  # noqa: BLE001
            run.finished_at = datetime.now(UTC)
            run.status = "error"
            run.message = f"{type(e).__name__}: {e}"[:500]
            await self._s.commit()
            log.warning("bar_fetch_failed", asset=asset.canonical_id, err=str(e))
            # fall back to whatever cache we had
            return BarWindowResult(
                bars=[self._bar_from_row(asset, r) for r in cached],
                source=cached[0].source if cached else provider.slug,
                from_cache=True,
            )

        rows = [_row_from_dto(asset.id, b) for b in fetched]
        inserted = updated = 0
        if rows:
            dialect = self._s.bind.dialect.name if self._s.bind else "postgresql"
            stmt = _upsert_stmt(dialect, rows)
            # For accounting: count rows already present as "updated".
            existing_times = {r.bar_time for r in cached if r.source == provider.slug}
            for r in rows:
                if r["bar_time"] in existing_times:
                    updated += 1
                else:
                    inserted += 1
            await self._s.execute(stmt)

        run.finished_at = datetime.now(UTC)
        run.bars_inserted = inserted
        run.bars_updated = updated
        await self._s.commit()

        # Re-load post-upsert so ordering is authoritative.
        merged = await self.load_from_db(asset, interval, start, end)
        return BarWindowResult(
            bars=[self._bar_from_row(asset, r) for r in merged],
            source=provider.slug,
            from_cache=False,
        )

    @staticmethod
    def _expected_count(interval: str, start: datetime, end: datetime) -> int:
        per_day = _INTERVAL_APPROX_PER_DAY.get(interval, 1)
        days = max(1, (end - start).total_seconds() / 86400)
        return int(days * per_day * 0.7)  # weekdays/session-days approximation

    @staticmethod
    def _bar_from_row(asset: Asset, r: PriceBar) -> BarDTO:
        return BarDTO(
            asset_id=AssetId.parse(asset.canonical_id),
            interval=r.interval,
            bar_time=r.bar_time,
            open=r.open, high=r.high, low=r.low, close=r.close,
            adj_close=r.adj_close, volume=r.volume,
            event_time=r.event_time, ingest_time=r.ingest_time,
            available_at=r.available_at, source=r.source,
        )
