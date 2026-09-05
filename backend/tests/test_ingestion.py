"""End-to-end test of the Phase 3 ingestion job against MockProvider — zero
real API calls, an in-memory SQLite DB, and a fixed `now` so the test never
depends on the wall clock or network.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.ingestion.run_ingestion import run_ingestion
from app.models import Instrument, NewsItem, Snapshot, User, WatchlistItem
from app.providers.base import RawNewsItem
from app.providers.mock_provider import MockProvider

# Thursday, not in backend/app/market_calendar_data/nse_holidays_2026.json —
# a plain "market open" instant for the happy-path test.
MARKET_OPEN_NOW = datetime(2026, 9, 3, 11, 0)
# Saturday — always closed regardless of the holiday list.
WEEKEND_NOW = datetime(2026, 9, 5, 11, 0)


class _NoOpGoogleNews:
    """Stands in for GoogleNewsRSSProvider in tests that aren't about the
    news pipeline — keeps them at zero network calls instead of silently
    hitting the real Google News RSS endpoint every time run_ingestion()
    reaches its per-instrument news step."""

    def search(self, query, after, before):
        return []


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def no_news():
    return _NoOpGoogleNews()


def _seed_watchlist(session, instrument_id: str, instrument_type: str, sector: str | None = None):
    user = session.get(User, 1)
    if user is None:
        user = User(id=1, firebase_uid="test-uid", email="test@example.com")
        session.add(user)
    session.add(Instrument(id=instrument_id, type=instrument_type, sector=sector))
    session.add(WatchlistItem(user_id=1, instrument_id=instrument_id))
    session.commit()


def test_ingestion_creates_snapshot_when_no_prior_exists(session, no_news):
    _seed_watchlist(session, "TCS.NS", "equity")

    summary = run_ingestion(session, MockProvider(), MARKET_OPEN_NOW, google_news_provider=no_news)

    assert summary.market_open is True
    assert summary.instruments_seen == 1
    assert summary.snapshots_created == 1
    assert summary.diffs_created == 0  # nothing to diff against on a user's first view
    assert summary.significance_scores_created == 0
    assert session.query(Snapshot).count() == 1


def test_ingestion_computes_diff_and_significance_against_prior_snapshot(session, no_news):
    _seed_watchlist(session, "RELIANCE.NS", "equity", sector="Energy")

    # Simulate a prior session: seed a snapshot with a price far from the
    # fixture's current quote so this run's diff is a large, clearly
    # significant move (fixture historical data gives it 21 days of
    # low-volatility baseline to be significant against).
    reliance_quote = MockProvider().get_quote("RELIANCE.NS")
    prior = Snapshot(
        instrument_id="RELIANCE.NS",
        user_id=1,
        captured_at=datetime(2026, 9, 2, 11, 0),
        price=reliance_quote.price * 0.5,
        ratios={},
        status="live",
    )
    session.add(prior)
    session.commit()

    summary = run_ingestion(session, MockProvider(), MARKET_OPEN_NOW, google_news_provider=no_news)

    assert summary.market_open is True
    assert summary.snapshots_created == 1
    assert summary.diffs_created == 1
    assert summary.significance_scores_created >= 1

    snapshots = session.query(Snapshot).filter_by(instrument_id="RELIANCE.NS").all()
    assert len(snapshots) == 2  # the seeded prior + the newly ingested one


def test_ingestion_calls_provider_once_per_instrument_not_per_user(session, monkeypatch, no_news):
    session.add(Instrument(id="INFY.NS", type="equity"))
    session.add(User(id=1, firebase_uid="u1", email="u1@example.com"))
    session.add(User(id=2, firebase_uid="u2", email="u2@example.com"))
    session.add(WatchlistItem(user_id=1, instrument_id="INFY.NS"))
    session.add(WatchlistItem(user_id=2, instrument_id="INFY.NS"))
    session.commit()

    provider = MockProvider()
    call_count = {"quote": 0}
    original_get_quote = provider.get_quote

    def counting_get_quote(instrument_id):
        call_count["quote"] += 1
        return original_get_quote(instrument_id)

    monkeypatch.setattr(provider, "get_quote", counting_get_quote)

    summary = run_ingestion(session, provider, MARKET_OPEN_NOW, google_news_provider=no_news)

    assert call_count["quote"] == 1  # one instrument, two watching users — still one provider call
    assert summary.snapshots_created == 2  # but one Snapshot row per (instrument, user)


def test_ingestion_creates_news_items_and_dedupes_by_url(session):
    _seed_watchlist(session, "TCS.NS", "equity", sector="IT")

    same_url_from_two_queries = RawNewsItem(
        source="Reuters",
        url="https://example.com/story-1",
        title="TCS wins big contract",
        snippet="details",
        published_at=datetime(2026, 9, 2, 9, 0),
    )

    class _FakeGoogleNews:
        def search(self, query, after, before):
            # Both the company query and the sector query happen to surface
            # the same wire story — this is the in-batch duplicate the
            # dedup step must catch, on top of the DB-level one.
            return [same_url_from_two_queries]

    summary = run_ingestion(session, MockProvider(), MARKET_OPEN_NOW, google_news_provider=_FakeGoogleNews())

    # MockProvider.get_news("TCS.NS") contributes its own fixture item (a
    # distinct URL), plus the RSS story above — which the company query
    # AND the sector query both return, so in-batch dedup must collapse
    # those two into one row.
    assert summary.news_items_created == 2
    items = session.query(NewsItem).all()
    assert len(items) == 2
    urls = {item.url for item in items}
    assert "https://example.com/story-1" in urls
    assert all(item.embedding is not None for item in items)  # MockEmbeddingProvider ran (default, no EMBEDDING_PROVIDER set)

    # A second run with the same stories must not create duplicate rows.
    summary2 = run_ingestion(session, MockProvider(), MARKET_OPEN_NOW, google_news_provider=_FakeGoogleNews())
    assert summary2.news_items_created == 0
    assert session.query(NewsItem).count() == 2


def test_news_pipeline_failure_logs_and_continues_other_instruments(session, caplog):
    """Phase 7 requirement 5: if both yfinance-style news AND Google News
    RSS fail for one instrument's news step, the run must log and move on
    — not crash the batch, and not skip price/diff/significance work for
    that same instrument or for any other instrument in the run."""
    _seed_watchlist(session, "TCS.NS", "equity", sector="IT")
    session.add(Instrument(id="RELIANCE.NS", type="equity", sector="Energy"))
    session.add(WatchlistItem(user_id=1, instrument_id="RELIANCE.NS"))
    session.commit()

    class _NewsFailingProvider:
        """Wraps a real MockProvider so price/historical data still work
        normally — only get_news is broken, and only for TCS.NS, so we can
        prove the OTHER instrument (RELIANCE.NS) is unaffected."""

        def __init__(self, inner):
            self._inner = inner

        def get_quote(self, instrument_id):
            return self._inner.get_quote(instrument_id)

        def get_historical(self, instrument_id, start, end):
            return self._inner.get_historical(instrument_id, start, end)

        def get_news(self, instrument_id):
            if instrument_id == "TCS.NS":
                raise RuntimeError("yfinance news backend is down")
            return self._inner.get_news(instrument_id)

        def get_fund_nav(self, instrument_id):
            return self._inner.get_fund_nav(instrument_id)

    class _FailingGoogleNews:
        def search(self, query, after, before):
            raise RuntimeError("Google News RSS is unreachable")

    provider = _NewsFailingProvider(MockProvider())

    summary = run_ingestion(session, provider, MARKET_OPEN_NOW, google_news_provider=_FailingGoogleNews())

    # The run itself didn't raise (pytest would have failed above if it had).
    # Both news sources fail independently and are logged at the point of
    # failure (see app/ingestion/run_ingestion.py) rather than aborting the
    # instrument's whole news step, so summary.errors — which only tracks
    # whole-instrument price/diff failures — stays empty; the log is where
    # the failure is actually recorded.
    assert summary.instruments_seen == 2
    assert summary.instruments_failed == 0  # a news failure isn't a price/diff failure
    assert any("TCS.NS" in record.message for record in caplog.records)
    assert any("yfinance news backend is down" in record.message for record in caplog.records)
    assert any("Google News RSS is unreachable" in record.message for record in caplog.records)

    # Both instruments still got their real work done despite TCS.NS's
    # news step failing entirely.
    assert session.query(Snapshot).filter_by(instrument_id="TCS.NS").count() == 1
    assert session.query(Snapshot).filter_by(instrument_id="RELIANCE.NS").count() == 1
    # RELIANCE.NS's own news (unaffected by TCS.NS's failure) still ingests normally.
    assert session.query(NewsItem).filter_by(instrument_id="RELIANCE.NS").count() >= 1
    assert session.query(NewsItem).filter_by(instrument_id="TCS.NS").count() == 0


def test_ingestion_marks_market_closed_instead_of_fetching(session, monkeypatch):
    _seed_watchlist(session, "TCS.NS", "equity")
    session.add(Snapshot(instrument_id="TCS.NS", user_id=1, captured_at=datetime(2026, 9, 4, 15, 0), price=100.0, status="live"))
    session.commit()

    provider = MockProvider()

    def _unexpected_call(*args, **kwargs):
        raise AssertionError("provider must not be called while the market is closed")

    monkeypatch.setattr(provider, "get_quote", _unexpected_call)
    monkeypatch.setattr(provider, "get_historical", _unexpected_call)

    summary = run_ingestion(session, provider, WEEKEND_NOW)

    assert summary.market_open is False
    snapshot = session.query(Snapshot).filter_by(instrument_id="TCS.NS").one()
    assert snapshot.status == "market_closed"
