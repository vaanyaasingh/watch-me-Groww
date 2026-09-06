"""A freshly-added instrument has no Snapshot yet (no ingestion run has
touched it for this user) — before this, both /api/watchlist and
/api/instruments/{id}/digest hardcoded price=None in that case forever,
even though the *current* price doesn't depend on having a prior snapshot
to diff against. app/api.py's _live_price() fetches it directly instead.
"""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api as api_module
import app.main as main_module
from app.auth import get_current_user_id
from app.db import Base
from app.models import Instrument, User, WatchlistItem
from app.providers.base import FundNav, Quote


class _FakeProvider:
    def get_quote(self, instrument_id):
        return Quote(instrument_id=instrument_id, price=1234.5, ratios={}, as_of=datetime(2026, 9, 6))

    def get_fund_nav(self, instrument_id):
        return FundNav(instrument_id=instrument_id, nav=42.0, as_of=date(2026, 9, 6))

    def get_historical(self, *a, **k):
        return []

    def get_news(self, *a, **k):
        return []


class _RaisingProvider:
    def get_quote(self, instrument_id):
        raise RuntimeError("provider unavailable")

    def get_fund_nav(self, instrument_id):
        raise RuntimeError("provider unavailable")


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr(api_module, "SessionLocal", TestSession)
    monkeypatch.setattr(main_module, "SessionLocal", TestSession)
    monkeypatch.setattr(api_module, "get_market_data_provider", lambda: _FakeProvider())

    session = TestSession()
    session.add(User(id=1, firebase_uid="test-uid", email="test@example.com"))
    session.add(Instrument(id="INFY.NS", type="equity", sector="IT"))
    session.add(Instrument(id="999999", type="mf"))
    session.add(WatchlistItem(user_id=1, instrument_id="INFY.NS"))
    session.add(WatchlistItem(user_id=1, instrument_id="999999"))
    session.commit()
    session.close()

    main_module.app.dependency_overrides[get_current_user_id] = lambda: 1
    try:
        with TestClient(main_module.app) as test_client:
            yield test_client
    finally:
        main_module.app.dependency_overrides.pop(get_current_user_id, None)


def test_digest_shows_a_live_price_for_an_instrument_with_no_snapshot_yet(client):
    response = client.get("/api/instruments/INFY.NS/digest")
    body = response.json()

    assert body["price"] == 1234.5
    assert body["status"] == "live"
    assert body["price_delta_pct"] is None  # still no diff — that genuinely needs two points over time


def test_digest_uses_fund_nav_for_a_mutual_fund_with_no_snapshot_yet(client):
    response = client.get("/api/instruments/999999/digest")
    body = response.json()

    assert body["price"] == 42.0
    assert body["status"] == "live"


def test_watchlist_shows_a_live_price_for_an_instrument_with_no_snapshot_yet(client):
    response = client.get("/api/watchlist")
    body = {item["instrument_id"]: item for item in response.json()}

    assert body["INFY.NS"]["price"] == 1234.5
    assert body["INFY.NS"]["status"] == "live"


def test_digest_falls_back_to_none_when_the_live_provider_also_fails(client, monkeypatch):
    monkeypatch.setattr(api_module, "get_market_data_provider", lambda: _RaisingProvider())

    response = client.get("/api/instruments/INFY.NS/digest")
    body = response.json()

    assert body["price"] is None
    assert body["status"] is None
