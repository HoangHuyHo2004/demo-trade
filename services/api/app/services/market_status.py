"""Market-status service using the calendars module."""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from app.providers.calendars import RULES, is_open, next_transition


class MarketStatus(BaseModel):
    market: str
    calendar: str
    timezone: str
    is_open: bool
    now_utc: datetime
    next_open_utc: datetime | None
    next_close_utc: datetime | None
    state: str  # OPEN | CLOSED


def status_for(calendar: str, at: datetime | None = None) -> MarketStatus | None:
    if calendar not in RULES:
        return None
    at = at or datetime.now(UTC)
    rule = RULES[calendar]
    open_now = is_open(calendar, at)
    return MarketStatus(
        market=_market_for_calendar(calendar),
        calendar=calendar,
        timezone=rule.tz,
        is_open=open_now,
        now_utc=at,
        next_open_utc=None if open_now else next_transition(calendar, at, want_open=True),
        next_close_utc=next_transition(calendar, at, want_open=False) if open_now else None,
        state="OPEN" if open_now else "CLOSED",
    )


def _market_for_calendar(calendar: str) -> str:
    return {
        "XNYS": "US",
        "XHOS": "VN",
        "XHNX": "VN",
        "UPCOM": "VN",
        "24x7": "CRYPTO",
    }.get(calendar, calendar)


def all_statuses() -> list[MarketStatus]:
    return [s for cal in RULES if (s := status_for(cal)) is not None]
