"""Batch price+news ingestion job (docs/plan.md §4: Cloud Scheduler -> Cloud
Run job, one shared cadence). Designed to run as a Cloud Run job triggered
by Cloud Scheduler; also runnable locally for testing via
`python -m app.ingestion.run_ingestion`.

Scaling decision, stated explicitly per the Phase 3 brief: this job calls
the MarketDataProvider once per distinct watched Instrument, never once per
(user, instrument) pair. An instrument watched by 10,000 users still costs
exactly one provider call. That's what keeps ingestion cost — and any
future provider rate limit — tied to how many instruments exist, not how
many users exist; the two are free to grow independently.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.diff_engine import compute_diff
from app.market_calendar import is_market_open
from app.models import Instrument, Snapshot, WatchlistItem
from app.providers.base import MarketDataProvider
from app.providers.config import get_market_data_provider
from app.providers.exceptions import ProviderUnavailableError
from app.significance import score_significance

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

# Comfortably above the 20-day minimum app/significance.py needs for the
# statistical check, with slack for weekends/holidays in the lookback.
HISTORICAL_LOOKBACK_DAYS = 60


@dataclass
class IngestionSummary:
    market_open: bool
    instruments_seen: int = 0
    instruments_failed: int = 0
    snapshots_created: int = 0
    diffs_created: int = 0
    significance_scores_created: int = 0
    errors: list[str] = field(default_factory=list)


def _distinct_watched_instruments(session: Session) -> list[Instrument]:
    """Every Instrument at least one user is watching, queried once — this
    is the batching this job is built around (see module docstring)."""
    stmt = (
        select(Instrument)
        .join(WatchlistItem, WatchlistItem.instrument_id == Instrument.id)
        .distinct()
    )
    return list(session.scalars(stmt))


def _watching_user_ids(session: Session, instrument_id: str) -> list[int]:
    stmt = (
        select(WatchlistItem.user_id)
        .where(WatchlistItem.instrument_id == instrument_id)
        .distinct()
    )
    return list(session.scalars(stmt))


def _latest_snapshot(session: Session, instrument_id: str, user_id: int) -> Snapshot | None:
    stmt = (
        select(Snapshot)
        .where(Snapshot.instrument_id == instrument_id, Snapshot.user_id == user_id)
        .order_by(Snapshot.captured_at.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def _mark_latest_snapshots_market_closed(session: Session, instruments: list[Instrument]) -> None:
    """Outside trading hours we fetch nothing new — we just relabel each
    (instrument, user)'s most recent snapshot as "market closed" so a later
    staleness check (Phase 7) doesn't mistake old-but-expected data for a
    stuck feed. Older snapshots keep whatever status they were captured
    with; only the current latest one per (instrument, user) changes."""
    instrument_ids = [i.id for i in instruments]
    if not instrument_ids:
        return
    stmt = select(Snapshot).where(Snapshot.instrument_id.in_(instrument_ids))
    latest_by_key: dict[tuple[str, int], Snapshot] = {}
    for snap in session.scalars(stmt):
        key = (snap.instrument_id, snap.user_id)
        current = latest_by_key.get(key)
        if current is None or snap.captured_at > current.captured_at:
            latest_by_key[key] = snap
    for snap in latest_by_key.values():
        snap.status = "market_closed"
    session.commit()


def _fetch_current(
    provider: MarketDataProvider, instrument: Instrument
) -> tuple[float, dict]:
    if instrument.type == "mf":
        nav = provider.get_fund_nav(instrument.id)
        return nav.nav, {}
    quote = provider.get_quote(instrument.id)
    return quote.price, quote.ratios


def _fetch_historical(provider: MarketDataProvider, instrument: Instrument, now: datetime):
    if instrument.type == "mf":
        return []  # AMFIProvider has no historical-bars method (Phase 1)
    # Excludes "today" per app/significance.py's documented contract — the
    # historical baseline must not already contain the day being scored.
    end = now.date() - timedelta(days=1)
    start = end - timedelta(days=HISTORICAL_LOOKBACK_DAYS)
    return provider.get_historical(instrument.id, start, end)


def run_ingestion(session: Session, provider: MarketDataProvider, now: datetime) -> IngestionSummary:
    """Core ingestion logic, free of CLI/env concerns so it's directly
    testable with an in-memory session, MockProvider, and a fixed `now`
    (see tests/test_ingestion.py)."""
    instruments = _distinct_watched_instruments(session)

    if not is_market_open(now):
        _mark_latest_snapshots_market_closed(session, instruments)
        return IngestionSummary(market_open=False, instruments_seen=len(instruments))

    summary = IngestionSummary(market_open=True, instruments_seen=len(instruments))

    for instrument in instruments:
        user_ids = _watching_user_ids(session, instrument.id)

        try:
            price, ratios = _fetch_current(provider, instrument)
            historical = _fetch_historical(provider, instrument, now)
        except (ProviderUnavailableError, NotImplementedError) as exc:
            # One instrument's provider failure shouldn't sink the run for
            # every other instrument — log it and move on.
            logger.warning("skipping %s: %s", instrument.id, exc)
            summary.instruments_failed += 1
            summary.errors.append(f"{instrument.id}: {exc}")
            continue

        for user_id in user_ids:
            prior = _latest_snapshot(session, instrument.id, user_id)

            new_snapshot = Snapshot(
                instrument_id=instrument.id,
                user_id=user_id,
                captured_at=now,
                price=price,
                ratios=ratios,
                status="live",
            )
            session.add(new_snapshot)
            session.flush()  # assigns new_snapshot.id, needed below
            summary.snapshots_created += 1

            if prior is None:
                continue  # nothing to diff against yet — first time this user has seen it

            diff = compute_diff(prior, new_snapshot)
            session.add(diff)
            session.flush()  # assigns diff.id, needed by SignificanceScore
            summary.diffs_created += 1

            scores = score_significance(diff, instrument, historical, prior, new_snapshot)
            session.add_all(scores)
            summary.significance_scores_created += len(scores)

        # Commit per instrument: one instrument's failure (or the next
        # loop iteration's) never rolls back instruments already ingested
        # in this run.
        session.commit()

    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    session = SessionLocal()
    try:
        provider = get_market_data_provider()
        now_ist = datetime.now(timezone.utc).astimezone(IST).replace(tzinfo=None)
        summary = run_ingestion(session, provider, now_ist)
        logger.info("ingestion summary: %s", summary)
        print(summary)
    finally:
        session.close()


if __name__ == "__main__":
    main()
