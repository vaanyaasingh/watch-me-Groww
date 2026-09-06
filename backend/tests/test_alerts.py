"""Feature 4's missing half (app/alerts.py): evaluate_alerts() must
actually flip an Alert to "triggered" when its stored condition is met by
a freshly-computed Diff/SignificanceScore, and must leave every other
alert (wrong instrument, wrong user, already non-active, condition not
met) untouched.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.alerts import evaluate_alerts
from app.db import Base
from app.models import Alert, Diff, SignificanceScore, User


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(User(id=1, firebase_uid="u1", email="u1@example.com"))
        s.add(User(id=2, firebase_uid="u2", email="u2@example.com"))
        s.commit()
        yield s


def _diff(instrument_id="RELIANCE.NS", before_price=100.0, after_price=105.0):
    return Diff(
        instrument_id=instrument_id,
        snapshot_before_id=1,
        snapshot_after_id=2,
        before_price=before_price,
        after_price=after_price,
        price_delta_pct=(after_price - before_price) / before_price,
        created_at=datetime(2026, 9, 6),
    )


def test_significant_change_alert_triggers_when_a_category_fired(session):
    alert = Alert(user_id=1, instrument_id="RELIANCE.NS", condition={"target_price": None, "notify_on_significant_change": True})
    session.add(alert)
    session.commit()

    scores = [SignificanceScore(diff_id=1, score=2.5, category="statistical")]
    fired = evaluate_alerts(session, user_id=1, instrument_id="RELIANCE.NS", diff=_diff(), scores=scores)

    assert fired == [alert]
    assert alert.status == "triggered"


def test_significant_change_alert_does_not_trigger_with_no_category(session):
    alert = Alert(user_id=1, instrument_id="RELIANCE.NS", condition={"target_price": None, "notify_on_significant_change": True})
    session.add(alert)
    session.commit()

    fired = evaluate_alerts(session, user_id=1, instrument_id="RELIANCE.NS", diff=_diff(), scores=[])

    assert fired == []
    assert alert.status == "active"


@pytest.mark.parametrize(
    "before_price,after_price,target,should_trigger",
    [
        (100.0, 105.0, 102.0, True),  # crossed upward through the target
        (105.0, 100.0, 102.0, True),  # crossed downward through the target
        (100.0, 101.0, 200.0, False),  # nowhere near the target
        (100.0, 105.0, 100.0, True),  # landing exactly on the target counts
    ],
)
def test_target_price_alert_triggers_on_a_real_crossing(session, before_price, after_price, target, should_trigger):
    alert = Alert(user_id=1, instrument_id="RELIANCE.NS", condition={"target_price": target, "notify_on_significant_change": False})
    session.add(alert)
    session.commit()

    fired = evaluate_alerts(
        session, user_id=1, instrument_id="RELIANCE.NS", diff=_diff(before_price=before_price, after_price=after_price), scores=[]
    )

    assert (fired == [alert]) is should_trigger
    assert alert.status == ("triggered" if should_trigger else "active")


def test_alert_for_a_different_user_is_not_touched(session):
    other_users_alert = Alert(user_id=2, instrument_id="RELIANCE.NS", condition={"target_price": None, "notify_on_significant_change": True})
    session.add(other_users_alert)
    session.commit()

    scores = [SignificanceScore(diff_id=1, score=3.0, category="threshold")]
    fired = evaluate_alerts(session, user_id=1, instrument_id="RELIANCE.NS", diff=_diff(), scores=scores)

    assert fired == []
    assert other_users_alert.status == "active"


def test_alert_for_a_different_instrument_is_not_touched(session):
    unrelated_alert = Alert(user_id=1, instrument_id="TCS.NS", condition={"target_price": None, "notify_on_significant_change": True})
    session.add(unrelated_alert)
    session.commit()

    scores = [SignificanceScore(diff_id=1, score=3.0, category="threshold")]
    fired = evaluate_alerts(session, user_id=1, instrument_id="RELIANCE.NS", diff=_diff(), scores=scores)

    assert fired == []
    assert unrelated_alert.status == "active"


def test_already_triggered_alert_is_not_re_evaluated(session):
    """Confirms the deliberate one-shot scope documented in
    evaluate_alerts' docstring — an alert that already fired doesn't get
    picked up again just because another significant diff comes in."""
    alert = Alert(
        user_id=1,
        instrument_id="RELIANCE.NS",
        condition={"target_price": None, "notify_on_significant_change": True},
        status="triggered",
    )
    session.add(alert)
    session.commit()

    scores = [SignificanceScore(diff_id=1, score=3.0, category="threshold")]
    fired = evaluate_alerts(session, user_id=1, instrument_id="RELIANCE.NS", diff=_diff(), scores=scores)

    assert fired == []
