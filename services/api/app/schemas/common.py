"""Common Pydantic response envelopes."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int


class Disclaimer(BaseModel):
    text: str = Field(
        default=(
            "Educational/research use only. Not investment advice. "
            "Signals are model output, not recommendations. Past performance "
            "does not indicate future results."
        )
    )


class AssetOut(ORMBase):
    id: int
    canonical_id: str
    asset_type: str
    market: str
    exchange_code: str
    symbol: str
    display_symbol: str
    name: str
    quote_currency: str
    market_timezone: str
    calendar: str
    is_active: bool
    is_benchmark: bool


class QuoteOut(BaseModel):
    asset_id: str
    price: Decimal
    currency: str
    event_time: datetime
    source: str
    is_stale: bool
    market_state: str  # OPEN | CLOSED | PRE | POST | UNKNOWN


class BarOut(BaseModel):
    t: datetime
    o: Decimal
    h: Decimal
    l: Decimal  # noqa: E741
    c: Decimal
    v: Decimal


class BarsOut(BaseModel):
    asset_id: str
    interval: str
    source: str
    from_cache: bool
    last_bar_time: datetime | None = None
    last_ingest_time: datetime | None = None
    bars: list[BarOut]
