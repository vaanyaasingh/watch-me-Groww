"""Feature 6's real half (app/subscription_tracker.py). Covers the
rule-based headline classifier directly, and refresh_subscription_window's
honesty contract: it must only ever change status on a real, matched
headline — never guess, never touch equities/ETFs, never fabricate a
result when the scheme name or the news search itself is unavailable.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Instrument, SubscriptionWindow
from app.providers.base import FundNav, RawNewsItem
from app.subscription_tracker import classify_headline, refresh_subscription_window


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


class _FakeProvider:
    def __init__(self, scheme_name="PGIM India Global Equity Opportunities Fund", raises=False):
        self._scheme_name = scheme_name
        self._raises = raises

    def get_fund_nav(self, instrument_id):
        if self._raises:
            raise RuntimeError("provider unavailable")
        return FundNav(instrument_id=instrument_id, nav=50.0, as_of=datetime(2026, 9, 6).date(), scheme_name=self._scheme_name)


class _FakeGoogleNews:
    def __init__(self, items):
        self._items = items

    def search(self, query, after, before):
        return self._items


def _headline(title, published_at=datetime(2026, 9, 5), source="Business Standard"):
    return RawNewsItem(source=source, url=f"https://example.com/{hash(title)}", title=title, snippet="", published_at=published_at)


@pytest.mark.parametrize(
    "title,expected",
    [
        ("PGIM India suspends fresh subscriptions in three international funds", "closed"),
        ("Nippon India pauses lumpsum investments in overseas fund", "closed"),
        ("Axis Mutual Fund resumes subscriptions in global fund", "open"),
        ("Kotak reopens SIP investments after RBI cap eases", "open"),
        ("Reliance Industries Q2 results beat estimates", None),
        ("HDFC Flexi Cap Fund NAV rises 2% this week", None),
    ],
)
def test_classify_headline(title, expected):
    assert classify_headline(title) == expected


def test_refresh_ignores_non_mf_instruments(session):
    instrument = Instrument(id="RELIANCE.NS", type="equity")
    session.add(instrument)
    session.commit()

    result = refresh_subscription_window(session, instrument, _FakeProvider(), _FakeGoogleNews([]), datetime(2026, 9, 6))

    assert result is None


def test_refresh_sets_status_from_a_real_matching_headline(session):
    instrument = Instrument(id="999001", type="mf")
    session.add(instrument)
    session.commit()

    news = _FakeGoogleNews([_headline("PGIM India suspends fresh subscriptions in three international funds")])
    window = refresh_subscription_window(session, instrument, _FakeProvider(), news, datetime(2026, 9, 6))

    assert window.status == "closed"
    assert window.scheme_name == "PGIM India Global Equity Opportunities Fund"
    assert "suspends fresh subscriptions" in window.evidence


def test_refresh_leaves_status_untouched_when_no_headline_matches(session):
    """The honesty contract: a fund with no real subscription-status news
    must not have its status guessed or defaulted — it stays whatever it
    already was (the seed-time default here)."""
    instrument = Instrument(id="999002", type="mf")
    session.add(instrument)
    existing = SubscriptionWindow(instrument_id="999002", status="open", last_changed_at=datetime(2026, 9, 1))
    session.add(existing)
    session.commit()

    news = _FakeGoogleNews([_headline("HDFC Flexi Cap Fund NAV rises 2% this week")])
    window = refresh_subscription_window(session, instrument, _FakeProvider(scheme_name="HDFC Flexi Cap Fund"), news, datetime(2026, 9, 6))

    assert window.status == "open"
    assert window.last_changed_at == datetime(2026, 9, 1)  # unchanged — no real signal found


def test_refresh_prefers_the_most_recent_matching_headline(session):
    instrument = Instrument(id="999003", type="mf")
    session.add(instrument)
    session.commit()

    news = _FakeGoogleNews(
        [
            _headline("Fund X suspends subscriptions", published_at=datetime(2026, 8, 20)),
            _headline("Fund X resumes subscriptions after RBI cap eases", published_at=datetime(2026, 9, 4)),
        ]
    )
    window = refresh_subscription_window(session, instrument, _FakeProvider(), news, datetime(2026, 9, 6))

    assert window.status == "open"


def test_refresh_survives_a_provider_failure(session):
    instrument = Instrument(id="999004", type="mf")
    session.add(instrument)
    session.commit()

    window = refresh_subscription_window(session, instrument, _FakeProvider(raises=True), _FakeGoogleNews([]), datetime(2026, 9, 6))

    assert window is not None  # still returns/creates the row, just can't search without a name
    assert window.scheme_name is None


def test_refresh_survives_a_news_search_failure(session):
    instrument = Instrument(id="999005", type="mf")
    session.add(instrument)
    session.commit()

    class _RaisingGoogleNews:
        def search(self, query, after, before):
            raise RuntimeError("network error")

    window = refresh_subscription_window(session, instrument, _FakeProvider(), _RaisingGoogleNews(), datetime(2026, 9, 6))

    assert window is not None
    assert window.status == "open"  # untouched default from _get_or_create
