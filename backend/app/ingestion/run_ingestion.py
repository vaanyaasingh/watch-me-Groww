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

from app.alerts import evaluate_alerts
from app.db import SessionLocal
from app.diff_engine import compute_diff
from app.embeddings import EmbeddingProvider, get_embedding_provider
from app.market_calendar import is_market_open
from app.models import Diff, Instrument, NewsItem, Snapshot, WatchlistItem
from app.providers.base import MarketDataProvider, RawNewsItem
from app.providers.config import get_market_data_provider
from app.providers.exceptions import ProviderUnavailableError
from app.providers.google_news_rss import GoogleNewsRSSProvider
from app.seed import DEMO_USER_ID, REFERENCE_INSTRUMENT_IDS
from app.significance import score_significance
from app.subscription_tracker import refresh_subscription_window

# NIFTY 50 stands in for "the market" for every equity's relative/peer
# significance check (Category 4, app/significance.py) — always anchored
# to the fixed system user, same as every other reference instrument,
# since the index's own move isn't personal to whoever's watchlist we're
# scoring (see app/seed.py's REFERENCE_INSTRUMENT_IDS comment).
INDEX_INSTRUMENT_ID = "^NSEI"

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

# Comfortably above the 20-day minimum app/significance.py needs for the
# statistical check, with slack for weekends/holidays in the lookback.
HISTORICAL_LOOKBACK_DAYS = 60

# News ingestion looks back a few days on every run (not just "since last
# run") so a missed or delayed scheduler tick never permanently loses a
# story — dedup-by-url makes re-fetching the overlap harmless.
NEWS_INGESTION_LOOKBACK_DAYS = 3


@dataclass
class IngestionSummary:
    market_open: bool
    instruments_seen: int = 0
    instruments_failed: int = 0
    snapshots_created: int = 0
    diffs_created: int = 0
    significance_scores_created: int = 0
    news_items_created: int = 0
    alerts_triggered: int = 0
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


def _latest_diff(session: Session, instrument_id: str, user_id: int) -> Diff | None:
    """Used for NIFTY 50's own most recent Diff (Category 4's index_diff,
    see score_significance's call site below) — same query shape as
    app/api.py's own _latest_diff, kept separate rather than shared since
    this module and the API layer don't otherwise import from each other."""
    stmt = (
        select(Diff)
        .join(Snapshot, Diff.snapshot_after_id == Snapshot.id)
        .where(Diff.instrument_id == instrument_id, Snapshot.user_id == user_id)
        .order_by(Diff.created_at.desc())
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


def _ingest_news_for_instrument(
    session: Session,
    instrument: Instrument,
    provider: MarketDataProvider,
    google_news_provider: GoogleNewsRSSProvider,
    embedding_provider: EmbeddingProvider,
    now: datetime,
) -> int:
    """One news pass per instrument per run — never per user, news isn't
    per-user data (docs/plan.md §6, "Ingestion"). Dedup is against every
    NewsItem already in the table, not just this run's batch, so the
    deliberate lookback overlap (NEWS_INGESTION_LOOKBACK_DAYS) never
    creates duplicate rows.
    """
    if instrument.type == "mf":
        return 0  # no company-style news source wired for mutual funds in this project

    after = now.date() - timedelta(days=NEWS_INGESTION_LOOKBACK_DAYS)
    before = now.date()

    # Each tuple carries the (instrument_id, sector_id) tag the resulting
    # NewsItem row should get — a sector-level story isn't about any one
    # company, so it's tagged sector-only (see models.py's NewsItem
    # docstring); a company-level story gets both, so it still surfaces for
    # a sector-wide query too.
    tagged: list[tuple[RawNewsItem, str | None, str | None]] = []

    # Each of the three fetch attempts below is independently guarded
    # against ANY exception (not just requests.RequestException/
    # ProviderUnavailableError) — Phase 7 requirement 5 explicitly covers
    # both yfinance news and Google News RSS failing in the same cycle, and
    # a narrower except here would let one source's failure abort the
    # others and discard whatever the earlier ones already fetched, rather
    # than each source degrading independently.
    try:
        tagged += [(raw, instrument.id, instrument.sector) for raw in provider.get_news(instrument.id)]
    except Exception as exc:
        logger.warning("skipping provider news for %s: %s", instrument.id, exc)

    company_query = instrument.id.split(".")[0]  # strip the exchange suffix for a cleaner search query
    try:
        tagged += [
            (raw, instrument.id, instrument.sector)
            for raw in google_news_provider.search(company_query, after=after, before=before)
        ]
    except Exception as exc:
        logger.warning("skipping company RSS search for %s: %s", instrument.id, exc)

    if instrument.sector:
        try:
            tagged += [
                (raw, None, instrument.sector)
                for raw in google_news_provider.search(instrument.sector, after=after, before=before)
            ]
        except Exception as exc:
            logger.warning("skipping sector RSS search for %s: %s", instrument.id, exc)

    created = 0
    seen_urls: set[str] = set()
    for raw, tagged_instrument_id, tagged_sector_id in tagged:
        if not raw.url or raw.url in seen_urls:
            continue
        seen_urls.add(raw.url)
        if session.scalar(select(NewsItem).where(NewsItem.url == raw.url)) is not None:
            continue  # already ingested by an earlier run (or another instrument sharing this sector)

        try:
            embedding = embedding_provider.embed(f"{raw.title} {raw.snippet}".strip())
        except Exception as exc:
            logger.warning("skipping embedding for %s: %s", raw.url, exc)
            continue

        session.add(
            NewsItem(
                instrument_id=tagged_instrument_id,
                sector_id=tagged_sector_id,
                source=raw.source,
                url=raw.url,
                title=raw.title,
                published_at=raw.published_at,
                embedding=embedding,
                ingested_at=now,
            )
        )
        created += 1
    return created


def run_ingestion(
    session: Session,
    provider: MarketDataProvider,
    now: datetime,
    google_news_provider: GoogleNewsRSSProvider | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> IngestionSummary:
    """Core ingestion logic, free of CLI/env concerns so it's directly
    testable with an in-memory session, MockProvider, and a fixed `now`
    (see tests/test_ingestion.py). google_news_provider/embedding_provider
    are injectable the same way for the same reason — tests substitute a
    no-op/deterministic fake instead of hitting real Google News/Gemini.
    """
    instruments = _distinct_watched_instruments(session)

    if not is_market_open(now):
        _mark_latest_snapshots_market_closed(session, instruments)
        return IngestionSummary(market_open=False, instruments_seen=len(instruments))

    google_news_provider = google_news_provider or GoogleNewsRSSProvider()
    embedding_provider = embedding_provider or get_embedding_provider()

    # Fetched once per run, not per instrument/user: NIFTY 50's own most
    # recent Diff (from whenever it was last ingested — this run's own
    # ^NSEI diff isn't computed yet at this point, since it's just another
    # instrument in the loop below) stands in for "the market" for every
    # other equity's relative significance check. None on a fresh instance
    # that's never ingested NIFTY yet — every instrument just scores three
    # categories instead of four until it has.
    index_diff = _latest_diff(session, INDEX_INSTRUMENT_ID, DEMO_USER_ID)

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

            # Reference instruments (NIFTY/SENSEX/USD-INR) never get
            # compared against NIFTY 50 — that's either meaningless (NIFTY
            # vs itself) or out of scope (SENSEX/USD-INR aren't equities
            # NIFTY is a peer benchmark for).
            scores = score_significance(
                diff,
                instrument,
                historical,
                prior,
                new_snapshot,
                index_diff=index_diff if instrument.id not in REFERENCE_INSTRUMENT_IDS else None,
            )
            session.add_all(scores)
            summary.significance_scores_created += len(scores)

            try:
                summary.alerts_triggered += len(evaluate_alerts(session, user_id, instrument.id, diff, scores))
            except Exception as exc:
                # An alert-evaluation bug shouldn't cost this user their
                # already-computed diff/significance for this instrument.
                logger.warning("alert evaluation failed for user %s / %s: %s", user_id, instrument.id, exc)
                summary.errors.append(f"{instrument.id} (alerts, user {user_id}): {exc}")

        try:
            summary.news_items_created += _ingest_news_for_instrument(
                session, instrument, provider, google_news_provider, embedding_provider, now
            )
        except Exception as exc:
            # News is a bonus signal, not the core digest — a news-pipeline
            # failure logs and moves on rather than losing this
            # instrument's price/diff/significance work already staged above.
            logger.warning("news ingestion failed for %s: %s", instrument.id, exc)
            summary.errors.append(f"{instrument.id} (news): {exc}")

        try:
            refresh_subscription_window(session, instrument, provider, google_news_provider, now)
        except Exception as exc:
            logger.warning("subscription-window refresh failed for %s: %s", instrument.id, exc)
            summary.errors.append(f"{instrument.id} (subscription window): {exc}")

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
