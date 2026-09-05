"""Stale-vs-closed detection (docs/plan.md §2, Feature 5: Data Integrity &
Corporate Action Layer — "staleness indicators (market-closed vs
feed-stuck)").

A snapshot that's simply old because NSE is shut is expected and not worth
flagging; a snapshot that's old *while the market is open* means the feed
is stuck, and that distinction is the entire point of this module. "How
old is old" only makes sense relative to the moment someone is looking at
it, not the moment the snapshot was captured — so this is computed at
read/request time (called from app/api.py), not baked into
Snapshot.status by the ingestion job (which only ever writes "live" or
"market_closed" at capture time, see app/ingestion/run_ingestion.py).
"""

from datetime import datetime, timedelta

from app.market_calendar import is_market_open

# How long a snapshot can go without updating, during market hours, before
# it's flagged "stale" rather than "live" — a small multiple of a plausible
# ingestion cadence (a few minutes) so one missed scheduler tick doesn't
# immediately cry wolf.
STALE_AFTER_MINUTES = 15


def compute_display_status(captured_at: datetime, now: datetime) -> str:
    """"live" | "stale" | "market_closed" — what a client should actually
    show for a snapshot's freshness right now, independent of whatever
    Snapshot.status was stored at capture time.

    `captured_at` and `now` must both be naive IST local datetimes, same
    convention as the rest of this codebase (see app/market_calendar.py).
    """
    if not is_market_open(now):
        return "market_closed"
    if now - captured_at > timedelta(minutes=STALE_AFTER_MINUTES):
        return "stale"
    return "live"
