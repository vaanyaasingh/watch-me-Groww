"""Requirements 1 & 3 from the Phase 7 brief: no "stale" flag outside NSE
trading hours or on a holiday (market_closed takes priority instead), and a
feed that hasn't updated in >STALE_AFTER_MINUTES minutes *during* market
hours is correctly flagged stale.
"""

from datetime import datetime, timedelta

from app.staleness import STALE_AFTER_MINUTES, compute_display_status

# Thursday, 11:00 IST — a plain in-hours instant (see test_ingestion.py).
MARKET_OPEN_NOW = datetime(2026, 9, 3, 11, 0)
# Saturday — always closed regardless of the holiday list.
WEEKEND_NOW = datetime(2026, 9, 5, 11, 0)
# Ganesh Chaturthi (estimated) — a date in backend/app/market_calendar_data/nse_holidays_2026.json.
HOLIDAY_NOW = datetime(2026, 9, 14, 11, 0)


def test_fresh_snapshot_during_market_hours_is_live():
    captured_at = MARKET_OPEN_NOW - timedelta(minutes=2)
    assert compute_display_status(captured_at, MARKET_OPEN_NOW) == "live"


def test_old_snapshot_during_market_hours_is_stale():
    captured_at = MARKET_OPEN_NOW - timedelta(minutes=STALE_AFTER_MINUTES + 1)
    assert compute_display_status(captured_at, MARKET_OPEN_NOW) == "stale"


def test_same_staleness_gap_outside_market_hours_is_market_closed_not_stale():
    """Requirement 1: the exact same "old" gap that would be flagged
    stale during market hours must NOT be flagged stale on a weekend —
    it's market_closed instead."""
    captured_at = WEEKEND_NOW - timedelta(minutes=STALE_AFTER_MINUTES + 1)
    assert compute_display_status(captured_at, WEEKEND_NOW) == "market_closed"


def test_same_staleness_gap_on_a_holiday_is_market_closed_not_stale():
    """Requirement 1: same, but for an NSE holiday rather than a weekend —
    the holiday calendar must suppress the stale flag too, not just weekends."""
    captured_at = HOLIDAY_NOW - timedelta(minutes=STALE_AFTER_MINUTES + 1)
    assert compute_display_status(captured_at, HOLIDAY_NOW) == "market_closed"


def test_fresh_snapshot_outside_market_hours_is_still_market_closed():
    """Even a snapshot captured seconds ago reads as market_closed once the
    market itself is shut — freshness is irrelevant outside trading hours."""
    captured_at = WEEKEND_NOW - timedelta(minutes=1)
    assert compute_display_status(captured_at, WEEKEND_NOW) == "market_closed"


def test_exactly_at_the_threshold_is_not_yet_stale():
    captured_at = MARKET_OPEN_NOW - timedelta(minutes=STALE_AFTER_MINUTES)
    assert compute_display_status(captured_at, MARKET_OPEN_NOW) == "live"
