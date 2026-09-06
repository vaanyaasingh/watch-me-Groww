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
from app.ingestion.run_ingestion import HISTORICAL_LOOKBACK_DAYS, _ingest_news_for_instrument
from app.models import Instrument, Snapshot, WatchlistItem
from app.providers.base import MarketDataProvider
from app.providers.config import get_market_data_provider
from app.providers.google_news_rss import GoogleNewsRSSProvider
from app.seed import DEMO_USER_ID, REFERENCE_INSTRUMENT_IDS
from app.significance import score_significance

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

    owned_instruments = [(instrument_id, user_id) for instrument_id in DEMO_SCENARIO_INSTRUMENTS] + [
        (instrument_id, DEMO_USER_ID) for instrument_id in REFERENCE_INSTRUMENT_IDS
    ]

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
            continue

        try:
            last_checked_at = now - timedelta(days=DAYS_AGO_LAST_CHECKED)
            # The "last checked" price is a real point from this
            # instrument's own historical series, not today's price
            # scaled by a made-up multiplier.
            historical = provider.get_historical(
                instrument_id, last_checked_at.date() - timedelta(days=10), last_checked_at.date()
            )
            prior_price = historical[-1].close if historical else provider.get_quote(instrument_id).price

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

            scores = score_significance(diff, instrument, current_historical, prior_snapshot, current_snapshot)
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
