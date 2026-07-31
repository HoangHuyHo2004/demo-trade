"""Static holiday tables (2025-2027).

Simplified — production would use ``exchange_calendars`` or the venue's
published calendar CSV. Reviewed against public sources; half-day
sessions are not modeled in Phase 2 (deferred to a follow-up ticket).
"""
from __future__ import annotations

from datetime import date

XNYS_HOLIDAYS: set[date] = {
    # 2025
    date(2025, 1, 1),   # New Year's Day
    date(2025, 1, 9),   # Nat'l Day of Mourning (proclaimed)
    date(2025, 1, 20),  # MLK Jr. Day + Inauguration Day
    date(2025, 2, 17),  # Presidents' Day
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 26),  # Memorial Day
    date(2025, 6, 19),  # Juneteenth
    date(2025, 7, 4),   # Independence Day
    date(2025, 9, 1),   # Labor Day
    date(2025, 11, 27), # Thanksgiving
    date(2025, 12, 25), # Christmas
    # 2026
    date(2026, 1, 1),
    date(2026, 1, 19),  # MLK
    date(2026, 2, 16),  # Presidents'
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),   # observed for July 4
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
    # 2027
    date(2027, 1, 1),
    date(2027, 1, 18),
    date(2027, 2, 15),
    date(2027, 3, 26),  # Good Friday
    date(2027, 5, 31),
    date(2027, 6, 18),  # observed
    date(2027, 7, 5),   # observed
    date(2027, 9, 6),
    date(2027, 11, 25),
    date(2027, 12, 24), # observed
}

# HOSE/HNX/UPCOM share the Vietnam public-holiday base plus SSC-specific
# closures. We intentionally simplify — production must reconcile with
# each exchange's annual notice.
VN_HOLIDAYS: set[date] = {
    # 2025 — Tet spans ~1 week
    date(2025, 1, 1),
    *(date(2025, 1, d) for d in (27, 28, 29, 30, 31)),
    date(2025, 4, 7),   # Hung Kings observed
    date(2025, 4, 30),  # Reunification Day
    date(2025, 5, 1),   # Labour Day
    date(2025, 9, 2),   # National Day
    # 2026
    date(2026, 1, 1),
    *(date(2026, 2, d) for d in (16, 17, 18, 19, 20)),
    date(2026, 4, 27),  # Hung Kings
    date(2026, 4, 30),
    date(2026, 5, 1),
    date(2026, 9, 2),
    # 2027
    date(2027, 1, 1),
    *(date(2027, 2, d) for d in (5, 8, 9, 10, 11)),
    date(2027, 4, 15),
    date(2027, 4, 30),
    date(2027, 5, 3),   # Labour Day observed (falls on Sat)
    date(2027, 9, 2),
}


def is_holiday(calendar: str, d: date) -> bool:
    if calendar == "XNYS":
        return d in XNYS_HOLIDAYS
    if calendar in ("XHOS", "XHNX", "UPCOM"):
        return d in VN_HOLIDAYS
    return False
