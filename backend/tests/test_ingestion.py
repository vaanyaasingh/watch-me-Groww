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
from app.models import Instrument, Snapshot, User, WatchlistItem
from app.providers.mock_provider import MockProvider

# Thursday, not in backend/app/market_calendar_data/nse_holidays_2026.json —
# a plain "market open" instant for the happy-path test.
MARKET_OPEN_NOW = datetime(2026, 9, 3, 11, 0)
# Saturday — always closed regardless of the holiday list.
WEEKEND_NOW = datetime(2026, 9, 5, 11, 0)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _seed_watchlist(session, instrument_id: str, instrument_type: str, sector: str | None = None):
    user = session.get(User, 1)
    if user is None:
        user = User(id=1, firebase_uid="test-uid", email="test@example.com")
        session.add(user)
    session.add(Instrument(id=instrument_id, type=instrument_type, sector=sector))
    session.add(WatchlistItem(user_id=1, instrument_id=instrument_id))
    session.commit()


def test_ingestion_creates_snapshot_when_no_prior_exists(session):
    _seed_watchlist(session, "TCS.NS", "equity")

    summary = run_ingestion(session, MockProvider(), MARKET_OPEN_NOW)

    assert summary.market_open is True
    assert summary.instruments_seen == 1
    assert summary.snapshots_created == 1
    assert summary.diffs_created == 0  # nothing to diff against on a user's first view
    assert summary.significance_scores_created == 0
    assert session.query(Snapshot).count() == 1


def test_ingestion_computes_diff_and_significance_against_prior_snapshot(session):
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

    summary = run_ingestion(session, MockProvider(), MARKET_OPEN_NOW)

    assert summary.market_open is True
    assert summary.snapshots_created == 1
    assert summary.diffs_created == 1
    assert summary.significance_scores_created >= 1

    snapshots = session.query(Snapshot).filter_by(instrument_id="RELIANCE.NS").all()
    assert len(snapshots) == 2  # the seeded prior + the newly ingested one


def test_ingestion_calls_provider_once_per_instrument_not_per_user(session, monkeypatch):
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

    summary = run_ingestion(session, provider, MARKET_OPEN_NOW)

    assert call_count["quote"] == 1  # one instrument, two watching users — still one provider call
    assert summary.snapshots_created == 2  # but one Snapshot row per (instrument, user)


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
