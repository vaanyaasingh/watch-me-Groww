"""Unit tests for app/significance.py — each of the four categories from
docs/plan.md §3 is tested independently with synthetic (hand-constructed)
data, never a live provider call.
"""

from datetime import date, datetime, timedelta

import pytest

from app.diff_engine import compute_diff
from app.models import Diff, Instrument, Snapshot
from app.providers.base import PricePoint
from app.significance import (
    _check_discrete_event,
    _check_statistical_deviation,
    _check_threshold_crossing,
    score_significance,
)

# 21 daily returns with low, steady noise (~0.09% stdev) — a realistic
# "boring" baseline for an instrument that hasn't done anything unusual.
BASELINE_RETURNS = [
    0.001, -0.0012, 0.0009, -0.0007, 0.0011, -0.0009, 0.0006, -0.0011, 0.0008, -0.0006,
    0.0010, -0.0008, 0.0007, -0.0010, 0.0009, -0.0007, 0.0011, -0.0009, 0.0008, -0.0006, 0.0010,
]


def _bars(closes: list[float], start: date = date(2024, 1, 1)) -> list[PricePoint]:
    bars = []
    d = start
    for c in closes:
        bars.append(PricePoint(date=d, open=c, high=c * 1.002, low=c * 0.998, close=c, volume=1_000_000))
        d += timedelta(days=1)
    return bars


def _baseline_closes(start_price: float = 100.0) -> list[float]:
    closes = [start_price]
    for r in BASELINE_RETURNS:
        closes.append(round(closes[-1] * (1 + r), 4))
    return closes


def _snapshot(instrument_id: str, price: float, day: int, **kwargs) -> Snapshot:
    defaults = dict(
        id=day,
        instrument_id=instrument_id,
        user_id=1,
        captured_at=datetime(2024, 1, 1) + timedelta(days=day),
        price=price,
        volume=1_000_000,
        ratios={},
    )
    defaults.update(kwargs)
    return Snapshot(**defaults)


def _instrument(**kwargs) -> Instrument:
    defaults = dict(id="TEST.NS", type="equity", exchange="NSE", sector="Banking", corporate_action_history=None)
    defaults.update(kwargs)
    return Instrument(**defaults)


def _diff(before_price: float, after_price: float, instrument_id: str = "TEST.NS") -> Diff:
    before = _snapshot(instrument_id, before_price, day=0)
    after = _snapshot(instrument_id, after_price, day=1)
    diff = compute_diff(before, after)
    diff.id = 1  # not persisted in these tests; set manually so SignificanceScore.diff_id is populated
    return diff


# --- Category 1: statistical price deviation ---


def test_statistical_deviation_flags_large_outlier():
    closes = _baseline_closes()
    historical = _bars(closes)  # strictly before today, per the documented contract
    diff = _diff(before_price=closes[-1], after_price=closes[-1] * 1.08)  # +8%, no corp action

    result = _check_statistical_deviation(diff, historical, adjusted_return=diff.price_delta_pct)

    assert result is not None
    assert result.category == "statistical"
    assert result.score > 2.0


def test_statistical_deviation_ignores_ordinary_move():
    closes = _baseline_closes()
    historical = _bars(closes)
    diff = _diff(before_price=closes[-1], after_price=closes[-1] * 1.0005)  # tiny move, in line with baseline

    result = _check_statistical_deviation(diff, historical, adjusted_return=diff.price_delta_pct)

    assert result is None


def test_statistical_deviation_skips_when_insufficient_history():
    historical = _bars([100.0, 101.0, 102.0])  # far fewer than the 20-day minimum
    diff = _diff(before_price=102.0, after_price=120.0)

    result = _check_statistical_deviation(diff, historical, adjusted_return=diff.price_delta_pct)

    assert result is None


# --- Category 2: threshold/structural crossing ---


def test_threshold_flags_new_52_week_high():
    historical = _bars([100.0] * 30)
    diff = _diff(before_price=100.0, after_price=130.0)

    result = _check_threshold_crossing(diff, historical, action=None)

    assert result is not None
    assert result.category == "threshold"
    assert "high" in result.detail


def test_threshold_flags_sma_crossover():
    # 51 prior bars: an early spike (so 130 isn't a new high) then 50 flat
    # bars at 100, followed by one new closing price of 102 — verified by
    # hand (see phase notes) to push the 20-day SMA above the 50-day SMA
    # while the 50/50 SMAs were exactly equal beforehand.
    historical = _bars([130.0] + [100.0] * 50)
    diff = _diff(before_price=100.0, after_price=102.0)

    result = _check_threshold_crossing(diff, historical, action=None)

    assert result is not None
    assert result.category == "threshold"
    assert "SMA" in result.detail


def test_threshold_skipped_when_corporate_action_present():
    historical = _bars([100.0] * 30)
    diff = _diff(before_price=100.0, after_price=130.0)
    action = {"action_type": "bonus", "ex_date": "2024-01-02", "ratio": 2.0, "amount": None}

    result = _check_threshold_crossing(diff, historical, action=action)

    assert result is None


# --- Category 3: discrete event ---


def test_discrete_event_flags_rating_change():
    diff = _diff(before_price=100.0, after_price=100.5)
    snapshot_after = _snapshot("TEST.NS", 100.5, day=1, rating_change="upgraded to Buy by CRISIL")

    result = _check_discrete_event(diff, snapshot_after, action=None)

    assert result is not None
    assert result.category == "event"
    assert "rating change" in result.detail


def test_discrete_event_flags_earnings_date():
    diff = _diff(before_price=100.0, after_price=100.5)
    snapshot_after = _snapshot("TEST.NS", 100.5, day=1, earnings_date=date(2024, 1, 2))

    result = _check_discrete_event(diff, snapshot_after, action=None)

    assert result is not None
    assert "earnings date" in result.detail


def test_discrete_event_none_when_nothing_present():
    diff = _diff(before_price=100.0, after_price=100.5)
    snapshot_after = _snapshot("TEST.NS", 100.5, day=1)

    result = _check_discrete_event(diff, snapshot_after, action=None)

    assert result is None


# --- Corporate-action exclusion (the specific required test) ---


def test_corporate_action_excludes_statistical_flag_for_bonus_issue():
    """A recorded 1:1 bonus issue causes a 40%+ raw price drop. The
    significance engine must NOT report this as a meaningful statistical
    deviation — it's a mechanical share-count change, not a valuation move
    (docs/plan.md §3). It's fine (expected) for it to show up under the
    "event" category, since it genuinely is a discrete corporate action.
    """
    closes = _baseline_closes(start_price=1048.0)  # 21 steady days, ~1050 by the end
    historical = _bars(closes)
    pre_bonus_price = closes[-1]
    post_bonus_price = round(pre_bonus_price / 2, 2)  # 1:1 bonus halves the price

    before = _snapshot("ICICIBANK.NS", pre_bonus_price, day=21)
    after = _snapshot("ICICIBANK.NS", post_bonus_price, day=22)
    diff = compute_diff(before, after)
    diff.id = 1

    assert diff.price_delta_pct < -0.4  # sanity check: this really is a 40%+ raw drop

    instrument = _instrument(
        id="ICICIBANK.NS",
        corporate_action_history=[
            {"action_type": "bonus", "ex_date": after.captured_at.date().isoformat(), "ratio": 2.0, "amount": None}
        ],
    )

    scores = score_significance(diff, instrument, historical, before, after)

    categories = {s.category for s in scores}
    assert "statistical" not in categories
    assert "threshold" not in categories  # same reasoning — see _check_threshold_crossing
    assert "event" in categories  # it *is* correctly flagged as a discrete event


def test_corporate_action_exclusion_generalizes_to_a_stock_split():
    """Phase 7 requirement: the exclusion rule must not be special-cased to
    the bonus-issue shape already covered above. A 1:3 stock split (ratio
    3.0, a ~67% mechanical drop — a different ratio and a different
    action_type than the bonus test) must be excluded the same way, proving
    the rule is generic to any recorded ratio-based corporate action."""
    closes = _baseline_closes(start_price=900.0)
    historical = _bars(closes)
    pre_split_price = closes[-1]
    post_split_price = round(pre_split_price / 3, 2)  # 1:3 split

    before = _snapshot("TCS.NS", pre_split_price, day=21)
    after = _snapshot("TCS.NS", post_split_price, day=22)
    diff = compute_diff(before, after)
    diff.id = 2

    assert diff.price_delta_pct < -0.6  # sanity check: a ~67% raw drop

    instrument = _instrument(
        id="TCS.NS",
        corporate_action_history=[
            {"action_type": "split", "ex_date": after.captured_at.date().isoformat(), "ratio": 3.0, "amount": None}
        ],
    )

    scores = score_significance(diff, instrument, historical, before, after)

    categories = {s.category for s in scores}
    assert "statistical" not in categories
    assert "threshold" not in categories
    assert "event" in categories
