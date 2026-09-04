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

from app.models import Instrument, SubscriptionWindow, User

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "sample_market_data.json"

# The fixture (Phase 1) never carried a sector field — added here rather
# than editing that file, since Phase 4's news-retrieval tests already
# depend on its exact current shape. Index/commodity ETFs have no sector.
_DEMO_SECTORS = {
    "RELIANCE.NS": "Energy",
    "TCS.NS": "IT",
    "INFY.NS": "IT",
    "HDFCBANK.NS": "Banking",
    "ICICIBANK.NS": "Banking",
}

# No auth system exists yet (Firebase Auth is still a later phase per
# docs/plan.md §4) — every route in app/api.py operates on this single
# demo user rather than a real per-session identity. Swapping this out for
# real auth later only touches app/api.py, not the frontend's shape.
DEMO_USER_ID = 1


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
