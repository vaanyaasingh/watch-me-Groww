"""Demo data seeding — runs once at startup (idempotent) so the frontend
has something real to render out of the box, without a separate manual
setup step. Only seeds catalog/reference data (instruments, one demo user,
placeholder subscription-window rows); it does NOT create Snapshots/Diffs
— those come from actually running the ingestion job
(python -m app.ingestion.run_ingestion) after adding instruments to a
watchlist through the UI.
"""

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Instrument, SubscriptionWindow, User, WatchlistItem

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "sample_market_data.json"

# The fixture (Phase 1) never carried a sector field — added here rather
# than editing that file, since Phase 4's news-retrieval tests already
# depend on its exact current shape. Index/commodity ETFs have no sector.
_DEMO_SECTORS = {
    "RELIANCE.NS": "Energy",
    "TCS.NS": "IT",
    "INFY.NS": "IT",
    "WIPRO.NS": "IT",
    "HDFCBANK.NS": "Banking",
    "ICICIBANK.NS": "Banking",
    "SBIN.NS": "Banking",
    "BAJFINANCE.NS": "Financial Services",
    "LT.NS": "Capital Goods",
    "ITC.NS": "FMCG",
    "MARUTI.NS": "Auto",
    "ASIANPAINT.NS": "Consumer Durables",
    "SUNPHARMA.NS": "Pharma",
}

# No auth system exists yet (Firebase Auth is still a later phase per
# docs/plan.md §4) — every route in app/api.py operates on this single
# demo user rather than a real per-session identity. Swapping this out for
# real auth later only touches app/api.py, not the frontend's shape.
DEMO_USER_ID = 1

# NIFTY 50, SENSEX, USD/INR — market-overview reference data, not part of
# any user's personal watchlist. Auto-watched by the demo user below so the
# regular ingestion job naturally keeps them fresh (reusing that machinery
# rather than building a separate one); app/api.py's /api/market-overview
# reads them back, and /api/watchlist filters them out of the personal
# watchlist view by Instrument.type.
REFERENCE_INSTRUMENT_IDS = ["^NSEI", "^BSESN", "USDINR=X"]


def seed_demo_data(session: Session) -> None:
    if session.get(User, DEMO_USER_ID) is None:
        session.add(User(id=DEMO_USER_ID, firebase_uid="demo-user", email="demo@example.com"))

    with open(FIXTURE_PATH) as f:
        fixture = json.load(f)

    for instrument_id, record in fixture["instruments"].items():
        if session.get(Instrument, instrument_id) is not None:
            continue
        exchange = instrument_id.split(".")[-1] if "." in instrument_id else None
        session.add(
            Instrument(
                id=instrument_id,
                type=record["type"],
                exchange={"NS": "NSE", "BO": "BSE"}.get(exchange),
                sector=_DEMO_SECTORS.get(instrument_id),
                corporate_action_history=record.get("corporate_actions"),
            )
        )

    for scheme_code, record in fixture["mutual_funds"].items():
        if session.get(Instrument, scheme_code) is not None:
            continue
        session.add(Instrument(id=scheme_code, type="mf"))

    session.flush()  # so the WatchlistItem foreign keys below can resolve the rows just added

    for instrument_id in REFERENCE_INSTRUMENT_IDS:
        if session.query(WatchlistItem).filter_by(user_id=DEMO_USER_ID, instrument_id=instrument_id).first() is not None:
            continue
        session.add(WatchlistItem(user_id=DEMO_USER_ID, instrument_id=instrument_id))

    # Placeholder subscription-window status: no provider in this project
    # actually sources RBI LRS subscription-window data yet (Feature 6 has
    # no ingestion path built for it in any prior phase) — these two rows
    # exist so the tracker view has something real to render, clearly
    # seeded rather than live-ingested.
    demo_windows = [
        ("120503", "open"),
        ("119551", "closing_soon"),
    ]
    for instrument_id, status in demo_windows:
        if session.query(SubscriptionWindow).filter_by(instrument_id=instrument_id).first() is not None:
            continue
        session.add(SubscriptionWindow(instrument_id=instrument_id, status=status))

    session.commit()
