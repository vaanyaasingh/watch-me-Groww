"""NSE trading-hours + holiday calendar.

This exists so the Phase 3 ingestion job can tell "market is shut" apart
from "the feed is stuck" — the former is expected and not worth flagging,
the latter is exactly what Feature 5's staleness indicator (Phase 7) needs
to catch. Getting this distinction right here is what makes that later
check meaningful instead of noisy.
"""

import json
from datetime import date, datetime, time
from pathlib import Path

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

HOLIDAYS_DIR = Path(__file__).resolve().parent / "market_calendar_data"


def _load_holidays(year: int) -> set[date]:
    path = HOLIDAYS_DIR / f"nse_holidays_{year}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No NSE holiday calendar for {year} at {path} — add one "
            f"(same shape as nse_holidays_2026.json) before running "
            f"ingestion for this year."
        )
    with open(path) as f:
        raw = json.load(f)
    return {date.fromisoformat(d) for d in raw["holidays"]}


def is_market_open(at: datetime) -> bool:
    """`at` is treated as IST local time, naive — every other datetime in
    this codebase is naive too (see app/models.py), so the caller (the
    ingestion job's entrypoint) is responsible for converting from UTC to
    IST before calling this, rather than this function silently assuming a
    timezone that may not match what was actually passed in."""
    if at.weekday() >= 5:  # Saturday/Sunday
        return False
    if at.date() in _load_holidays(at.year):
        return False
    return MARKET_OPEN <= at.time() <= MARKET_CLOSE
