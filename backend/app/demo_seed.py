"""One-command realistic demo scenario: seeds a "last checked N days ago"
snapshot for a few instruments (using each instrument's own historical
close from that many days back, not an arbitrary multiplier), then
computes a real diff, real significance score, and real retrieved news for
"today" — so the digest view actually shows a since-you-last-checked story
instead of an empty/placeholder one.

Deliberately bypasses app/ingestion/run_ingestion.py's top-level
is_market_open() gate: that check is correct for the real scheduled
ingestion job, but this is an explicit, user-triggered "populate demo data"
action that should work regardless of what time it happens to be when
someone clicks it, not simulate a specific trading session. It reuses the
same lower-level diff/significance/news logic directly (compute_diff,
score_significance, _ingest_news_for_instrument) rather than duplicating it.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.diff_engine import compute_diff
from app.embeddings import get_embedding_provider
from app.ingestion.run_ingestion import HISTORICAL_LOOKBACK_DAYS, _ingest_news_for_instrument, _latest_diff
from app.models import Instrument, Snapshot, WatchlistItem
from app.providers.base import MarketDataProvider
from app.providers.config import get_market_data_provider
from app.providers.google_news_rss import GoogleNewsRSSProvider
from app.seed import DEMO_USER_ID, REFERENCE_INSTRUMENT_IDS
from app.significance import score_significance

# Same stand-in for "the market" as app/ingestion/run_ingestion.py's own
# Category 4 wiring — see that module for why NIFTY specifically.
INDEX_INSTRUMENT_ID = "^NSEI"

# Picked for a mix of significance categories and because they're large,
# frequently-covered companies with real Google News RSS results — not the
# full catalog, so the demo stays legible rather than a wall of numbers.
# Reference instruments (NIFTY 50/SENSEX/USD-INR) are seeded separately,
# always under the fixed system user (see the owner-selection loop below),
# since /api/market-overview isn't per-user and reads that one account.
DEMO_SCENARIO_INSTRUMENTS = ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "ICICIBANK.NS"]

DAYS_AGO_LAST_CHECKED = 4


def seed_demo_scenario(
    session: Session,
    user_id: int = DEMO_USER_ID,
    provider: MarketDataProvider | None = None,
    now: datetime | None = None,
) -> dict:
    """user_id is whichever real, authenticated person clicked "populate
    demo data" (app/api.py's post_seed_demo_scenario) — defaults to
    DEMO_USER_ID only for direct/test callers that don't have a real user in
    play. Reference instruments always seed under DEMO_USER_ID regardless,
    since they're shared market data, not personal to whoever asked."""
    provider = provider or get_market_data_provider()
    now = now or datetime.utcnow()
    google_news_provider = GoogleNewsRSSProvider()
    embedding_provider = get_embedding_provider()

    result = {"instruments_seeded": [], "instruments_skipped": [], "errors": []}

    # Reference instruments first, not last: NIFTY 50's own diff (computed
    # inside this same loop, captured into index_diff below) needs to
    # exist before the personal-story equities are scored, so their
    # Category 4 (relative-to-the-market) check has something real to
    # compare against on a completely fresh run.
    owned_instruments = [(instrument_id, DEMO_USER_ID) for instrument_id in REFERENCE_INSTRUMENT_IDS] + [
        (instrument_id, user_id) for instrument_id in DEMO_SCENARIO_INSTRUMENTS
    ]
    index_diff = None

    for instrument_id, owner_id in owned_instruments:
        instrument = session.get(Instrument, instrument_id)
        if instrument is None:
            result["instruments_skipped"].append(f"{instrument_id} (not in catalog)")
            continue

        if session.query(WatchlistItem).filter_by(user_id=owner_id, instrument_id=instrument_id).first() is None:
            session.add(WatchlistItem(user_id=owner_id, instrument_id=instrument_id))
            session.commit()

        already_seeded = (
            session.query(Snapshot).filter_by(instrument_id=instrument_id, user_id=owner_id).first()
        )
        if already_seeded is not None:
            result["instruments_skipped"].append(f"{instrument_id} (already has snapshot history)")
            if instrument_id == INDEX_INSTRUMENT_ID:
                # NIFTY was seeded by an earlier call (e.g. a different
                # user ran this before) — its diff still exists, just not
                # freshly computed by *this* call, so fetch it rather than
                # leaving later equities with no index to compare against.
                index_diff = _latest_diff(session, INDEX_INSTRUMENT_ID, DEMO_USER_ID)
            continue

        try:
            last_checked_at = now - timedelta(days=DAYS_AGO_LAST_CHECKED)
            # The "last checked" price is a real point from this
            # instrument's own historical series, not today's price
            # scaled by a made-up multiplier.
            historical = provider.get_historical(
                instrument_id, last_checked_at.date() - timedelta(days=10), last_checked_at.date()
            )
            # The OLDEST bar in this window, not the newest: MockProvider's
            # fixture sets each instrument's "quote" (the "current" price
            # below) equal to its own last historical close, by convention
            # (a static fixture's "live price" naturally is its most recent
            # bar) — so historical[-1] here is frequently that exact same
            # bar, silently producing a real-but-guaranteed 0.00% diff on
            # every run regardless of the real day-to-day prices this
            # fixture actually has. historical[0] is far enough back in the
            # window to reliably differ, without needing to fabricate or
            # scale anything — still a real, unmodified point from this
            # instrument's own series.
            prior_price = historical[0].close if historical else provider.get_quote(instrument_id).price

            prior_snapshot = Snapshot(
                instrument_id=instrument_id,
                user_id=owner_id,
                captured_at=last_checked_at,
                price=prior_price,
                status="live",
            )
            session.add(prior_snapshot)
            session.flush()

            quote = provider.get_quote(instrument_id)
            current_historical = provider.get_historical(
                instrument_id, now.date() - timedelta(days=1 + HISTORICAL_LOOKBACK_DAYS), now.date() - timedelta(days=1)
            )
            current_snapshot = Snapshot(
                instrument_id=instrument_id,
                user_id=owner_id,
                captured_at=now,
                price=quote.price,
                ratios=quote.ratios,
                status="live",
            )
            session.add(current_snapshot)
            session.flush()

            diff = compute_diff(prior_snapshot, current_snapshot)
            session.add(diff)
            session.flush()

            if instrument_id == INDEX_INSTRUMENT_ID:
                index_diff = diff  # this run's own fresh NIFTY diff — available to every equity scored after it

            scores = score_significance(
                diff,
                instrument,
                current_historical,
                prior_snapshot,
                current_snapshot,
                index_diff=index_diff if instrument_id not in REFERENCE_INSTRUMENT_IDS else None,
            )
            session.add_all(scores)

            news_created = _ingest_news_for_instrument(
                session, instrument, provider, google_news_provider, embedding_provider, now
            )

            session.commit()
            result["instruments_seeded"].append(
                {"instrument_id": instrument_id, "significance_categories": len(scores), "news_items": news_created}
            )
        except Exception as exc:  # a demo-seeding failure for one instrument shouldn't sink the rest
            session.rollback()
            result["errors"].append(f"{instrument_id}: {exc}")

    return result
