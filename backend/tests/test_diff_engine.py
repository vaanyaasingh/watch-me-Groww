from datetime import datetime

import pytest

from app.diff_engine import compute_diff
from app.models import Snapshot


def _snapshot(**kwargs) -> Snapshot:
    defaults = dict(
        id=None,
        instrument_id="RELIANCE.NS",
        user_id=1,
        captured_at=datetime(2024, 1, 1),
        price=100.0,
        volume=1_000_000,
        ratios={"pe_ratio": 25.0},
    )
    defaults.update(kwargs)
    return Snapshot(**defaults)


def test_diff_computes_price_and_volume_delta():
    before = _snapshot(id=1, price=100.0, volume=1_000_000)
    after = _snapshot(id=2, price=110.0, volume=1_500_000)

    diff = compute_diff(before, after)

    assert diff.price_delta_pct == pytest.approx(0.10)
    assert diff.volume_delta_pct == pytest.approx(0.5)
    assert diff.before_price == 100.0
    assert diff.after_price == 110.0


def test_diff_computes_ratio_deltas_for_shared_keys_only():
    before = _snapshot(id=1, ratios={"pe_ratio": 20.0, "old_only": 5.0})
    after = _snapshot(id=2, ratios={"pe_ratio": 25.0, "new_only": 7.0})

    diff = compute_diff(before, after)

    assert diff.ratio_deltas == {"pe_ratio": pytest.approx(0.25)}


def test_diff_handles_missing_volume():
    before = _snapshot(id=1, volume=None)
    after = _snapshot(id=2, volume=1_000_000)

    diff = compute_diff(before, after)

    assert diff.volume_delta_pct is None


def test_diff_rejects_different_instruments():
    before = _snapshot(id=1, instrument_id="RELIANCE.NS")
    after = _snapshot(id=2, instrument_id="TCS.NS")

    with pytest.raises(ValueError):
        compute_diff(before, after)
