"""Trading-calendar holiday tests."""
from datetime import UTC, datetime

import pytz

from app.providers.calendars import is_open, next_transition
from app.providers.holidays import is_holiday


def test_xnys_new_years_day_2026():
    # 2026-01-01 is a Thursday and a US market holiday.
    assert is_holiday("XNYS", datetime(2026, 1, 1).date())
    ny = pytz.timezone("America/New_York")
    noon_local = ny.localize(datetime(2026, 1, 1, 12, 0)).astimezone(UTC)
    assert not is_open("XNYS", noon_local)


def test_xnys_weekday_open():
    ny = pytz.timezone("America/New_York")
    at = ny.localize(datetime(2026, 3, 4, 10, 30)).astimezone(UTC)  # Wed 10:30 ET
    assert is_open("XNYS", at)


def test_hose_tet_2026_closed():
    # Tet 2026 window
    for d in (datetime(2026, 2, 16), datetime(2026, 2, 17), datetime(2026, 2, 18)):
        assert is_holiday("XHOS", d.date()), f"expected VN holiday: {d.date()}"
    hcm = pytz.timezone("Asia/Ho_Chi_Minh")
    at = hcm.localize(datetime(2026, 2, 17, 10, 0)).astimezone(UTC)
    assert not is_open("XHOS", at)


def test_crypto_247_always_open():
    at = datetime(2026, 1, 1, 5, 0, tzinfo=UTC)  # Thursday early morning
    assert is_open("24x7", at)


def test_next_transition_skips_holiday():
    ny = pytz.timezone("America/New_York")
    # Wednesday after close 2025-12-31; next open should be Fri Jan 2 2026
    # (skipping New Year's Day on Thursday).
    at = ny.localize(datetime(2025, 12, 31, 17, 0)).astimezone(UTC)
    nxt = next_transition("XNYS", at, want_open=True)
    assert nxt is not None
    nxt_local = nxt.astimezone(ny)
    assert nxt_local.date().isoformat() == "2026-01-02"
    assert nxt_local.strftime("%H:%M") == "09:30"
