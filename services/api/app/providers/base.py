"""Abstract provider interfaces.

Business code depends only on these types. Concrete adapters live in
sibling modules (``mock.py``, and future ``alpaca.py`` / ``ssi.py`` /
``coinbase.py``).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.asset_id import AssetId


@dataclass(frozen=True, slots=True)
class QuoteDTO:
    asset_id: AssetId
    price: Decimal
    currency: str
    event_time: datetime          # exchange-side time of last trade
    ingest_time: datetime         # when we received it
    source: str
    is_stale: bool


@dataclass(frozen=True, slots=True)
class BarDTO:
    asset_id: AssetId
    interval: str
    bar_time: datetime            # bar OPEN time, UTC
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adj_close: Decimal | None
    volume: Decimal
    event_time: datetime
    ingest_time: datetime
    available_at: datetime        # when strategies could see it (>= bar close + reporting lag)
    source: str


class MarketDataProvider(ABC):
    """Historical bars + last quote."""

    slug: str
    supports_markets: tuple[str, ...]

    @abstractmethod
    async def get_quote(self, asset: AssetId) -> QuoteDTO:  # pragma: no cover - abstract
        ...

    @abstractmethod
    async def get_bars(
        self,
        asset: AssetId,
        *,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[BarDTO]:  # pragma: no cover - abstract
        ...


class MarketStatusProvider(ABC):
    @abstractmethod
    def is_open(self, market: str, at: datetime) -> bool:  # pragma: no cover
        ...

    @abstractmethod
    def next_open(self, market: str, at: datetime) -> datetime | None:  # pragma: no cover
        ...

    @abstractmethod
    def next_close(self, market: str, at: datetime) -> datetime | None:  # pragma: no cover
        ...
