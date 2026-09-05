"""Phase 7 requirement 2, the API-surfacing half: NSE/BSE disagreement
must show up in the actual digest response, not just in the pure
reconcile_exchange_prices() unit tests (tests/test_reconciliation.py).
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
import app.api as api_module
import app.main as main_module
from app.models import Instrument, Snapshot, User


@pytest.fixture
def client(monkeypatch):
    # StaticPool: the app under test opens a fresh SessionLocal() per
    # request (like real usage), and each of those needs to see data
    # committed by earlier ones — a plain "sqlite:///:memory:" engine
    # hands out a brand-new, empty in-memory DB per connection otherwise.
    engine = create_engine(
        "sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    # Route every SessionLocal() call (in app.api and app.seed) at this
    # in-memory engine instead of the real dev.db file, so the test never
    # touches disk and never depends on prior test/dev state.
    monkeypatch.setattr(api_module, "SessionLocal", TestSession)
    monkeypatch.setattr(main_module, "SessionLocal", TestSession)

    session = TestSession()
    session.add(User(id=1, firebase_uid="test-uid", email="test@example.com"))
    session.add(Instrument(id="RELIANCE.NS", type="equity", exchange="NSE", sector="Energy"))
    session.add(Instrument(id="RELIANCE.BO", type="equity", exchange="BSE", sector="Energy"))
    session.add(Snapshot(instrument_id="RELIANCE.NS", user_id=1, captured_at=datetime(2026, 9, 3, 11, 0), price=2500.0, status="live"))
    session.add(Snapshot(instrument_id="RELIANCE.BO", user_id=1, captured_at=datetime(2026, 9, 3, 11, 0), price=2470.0, status="live"))  # 1.2% apart
    session.commit()
    session.close()

    with TestClient(main_module.app) as test_client:
        yield test_client


def test_digest_surfaces_nse_bse_disagreement(client):
    response = client.get("/api/instruments/RELIANCE.NS/digest")
    assert response.status_code == 200
    body = response.json()

    reconciliation = body["exchange_reconciliation"]
    assert reconciliation is not None
    assert reconciliation["chosen_exchange"] == "NSE"
    assert reconciliation["chosen_price"] == 2500.0
    assert reconciliation["nse_price"] == 2500.0
    assert reconciliation["bse_price"] == 2470.0
    assert reconciliation["disagreement"] is True  # 1.2% > the 0.5% tolerance


def test_digest_for_counterpart_ticker_also_surfaces_it_with_nse_still_chosen(client):
    """Asking from the BSE side of the same pair must report the same
    NSE-wins outcome, not flip based on which ticker was queried."""
    response = client.get("/api/instruments/RELIANCE.BO/digest")
    body = response.json()

    reconciliation = body["exchange_reconciliation"]
    assert reconciliation["chosen_exchange"] == "NSE"
    assert reconciliation["chosen_price"] == 2500.0


def test_digest_omits_reconciliation_when_no_counterpart_listing_exists(client):
    """An instrument with no dual-exchange counterpart in the catalog at
    all (the common case) must not fabricate a reconciliation block."""
    # TCS.NS already exists as an Instrument via app/seed.py's startup
    # seeding from the fixture catalog — just give it a snapshot, no
    # counterpart (".BO") listing, unlike RELIANCE above.
    session = api_module.SessionLocal()
    session.add(Snapshot(instrument_id="TCS.NS", user_id=1, captured_at=datetime(2026, 9, 3, 11, 0), price=3700.0, status="live"))
    session.commit()
    session.close()

    response = client.get("/api/instruments/TCS.NS/digest")

    assert response.json()["exchange_reconciliation"] is None
