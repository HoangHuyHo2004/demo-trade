"""Trading calendars for market-status.

Regular sessions + static holidays for 2025-2027 (see ``holidays.py``).
Half-day sessions are not modeled in Phase 2 — a follow-up ticket adds
them.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

import pytz

from app.providers.holidays import is_holiday


@dataclass(frozen=True)
class SessionRule:
    tz: str
    open_local: time
    close_local: time
    weekdays: tuple[int, ...]  # 0 = Monday ... 6 = Sunday


RULES: dict[str, SessionRule] = {
    "XNYS":  SessionRule("America/New_York",  time(9, 30), time(16, 0),   (0, 1, 2, 3, 4)),
    "XHOS":  SessionRule("Asia/Ho_Chi_Minh",  time(9,  0), time(14, 45), (0, 1, 2, 3, 4)),
    "XHNX":  SessionRule("Asia/Ho_Chi_Minh",  time(9,  0), time(14, 30), (0, 1, 2, 3, 4)),
    "UPCOM": SessionRule("Asia/Ho_Chi_Minh",  time(9,  0), time(15, 0),  (0, 1, 2, 3, 4)),
    "24x7":  SessionRule("UTC",               time(0,  0), time(23, 59, 59), (0, 1, 2, 3, 4, 5, 6)),
}


def is_open(calendar: str, at: datetime) -> bool:
    rule = RULES.get(calendar)
    if rule is None:
        return False
    local = at.astimezone(pytz.timezone(rule.tz))
    if local.weekday() not in rule.weekdays:
        return False
    if is_holiday(calendar, local.date()):
        return False
    return rule.open_local <= local.time() < rule.close_local


def next_transition(calendar: str, at: datetime, want_open: bool) -> datetime | None:
    rule = RULES.get(calendar)
    if rule is None:
        return None
    tz = pytz.timezone(rule.tz)
    local = at.astimezone(tz)
    target = rule.open_local if want_open else rule.close_local
    for offset in range(0, 14):
        candidate = local + timedelta(days=offset)
        weekday = candidate.weekday()
        if weekday not in rule.weekdays:
            continue
        if is_holiday(calendar, candidate.date()):
            continue
        candidate_local = tz.localize(datetime.combine(candidate.date(), target))
        if candidate_local > local:
            return candidate_local.astimezone(pytz.UTC)
    return None
