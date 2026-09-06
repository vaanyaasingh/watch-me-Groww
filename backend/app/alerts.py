"""Feature 4 (Adaptive Alerts) — the missing half.

app/api.py already lets a person create/list/delete an Alert row, and its
own comment says it "reuses app/significance.py's own flags directly...
rather than a separate alerting system" — true of the *condition* it
stores, but until this module nothing ever actually read that condition
back against a new Diff/SignificanceScore. An alert could be created and
then nothing would ever happen, no matter how the price moved. This is
the evaluation half: called once per (user, instrument) right after
run_ingestion.py computes that pair's Diff and SignificanceScore.

Delivery (push/email) is deliberately out of scope here — see the README
for why: Firebase Cloud Messaging and email both need real infrastructure
(a service worker + VAPID keys, or an SMTP/provider account) this project
doesn't have set up, and bolting either on this close to a deadline was
judged riskier than leaving Alert.status as the visible signal a person
checks (GET /api/alerts, already returns it) rather than something pushed
at them.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, Diff, SignificanceScore


def _target_price_crossed(condition: dict, diff: Diff) -> bool:
    target = condition.get("target_price")
    if target is None:
        return False
    lo, hi = sorted((diff.before_price, diff.after_price))
    # A closed interval so landing exactly on the target still counts —
    # crossing, not "strictly passing", is what a person setting a target
    # price actually means.
    return lo <= target <= hi


def evaluate_alerts(
    session: Session,
    user_id: int,
    instrument_id: str,
    diff: Diff,
    scores: list[SignificanceScore],
) -> list[Alert]:
    """Checks every one of this user's active alerts on this instrument
    against the diff/scores run_ingestion.py just computed for that same
    (user, instrument) pair, flipping status to "triggered" for any whose
    condition is met. Returns the alerts that fired this call (empty list
    most of the time — most diffs trigger nothing). A triggered alert
    stays triggered rather than re-arming; today's smallest-honest scope is
    "did this condition ever fire", not a re-notify policy, which is a
    reasonable product decision to defer rather than an oversight."""
    alerts = session.scalars(
        select(Alert).where(
            Alert.user_id == user_id,
            Alert.instrument_id == instrument_id,
            Alert.status == "active",
        )
    ).all()

    fired = []
    for alert in alerts:
        condition = alert.condition or {}
        significant_change_fired = bool(condition.get("notify_on_significant_change")) and len(scores) > 0
        if significant_change_fired or _target_price_crossed(condition, diff):
            alert.status = "triggered"
            fired.append(alert)
    return fired
