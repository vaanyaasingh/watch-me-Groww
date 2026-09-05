"""Requirement 2 from the Phase 7 brief: NSE/BSE price disagreement."""

import pytest

from app.reconciliation import (
    DISAGREEMENT_TOLERANCE_PCT,
    SOURCE_OF_TRUTH_EXCHANGE,
    reconcile_exchange_prices,
)


def test_prices_within_tolerance_are_not_flagged_as_disagreement():
    result = reconcile_exchange_prices(nse_price=1000.0, bse_price=1000.2)  # 0.02% apart

    assert result.disagreement is False
    assert result.chosen_price == 1000.0
    assert result.chosen_exchange == "NSE"


def test_prices_beyond_tolerance_are_flagged_and_nse_is_chosen():
    # 1% apart — well beyond DISAGREEMENT_TOLERANCE_PCT (0.5%).
    result = reconcile_exchange_prices(nse_price=1000.0, bse_price=990.0)

    assert result.disagreement is True
    assert result.chosen_price == 1000.0
    assert result.chosen_exchange == SOURCE_OF_TRUTH_EXCHANGE
    assert result.discrepancy_pct == pytest.approx(0.01, abs=1e-6)


def test_nse_is_chosen_even_when_bse_price_is_higher():
    """The source-of-truth rule is fixed (liquidity-based), not "pick
    whichever price looks more plausible" — NSE wins regardless of
    direction."""
    result = reconcile_exchange_prices(nse_price=990.0, bse_price=1000.0)

    assert result.chosen_price == 990.0
    assert result.chosen_exchange == "NSE"
    assert result.disagreement is True


def test_discrepancy_still_reported_when_prices_match_exactly():
    result = reconcile_exchange_prices(nse_price=500.0, bse_price=500.0)

    assert result.discrepancy_pct == 0.0
    assert result.disagreement is False


def test_boundary_at_exact_tolerance_is_not_a_disagreement():
    nse_price = 1000.0
    bse_price = nse_price * (1 + DISAGREEMENT_TOLERANCE_PCT)  # exactly at the threshold
    result = reconcile_exchange_prices(nse_price, bse_price)

    assert result.disagreement is False  # strictly-greater-than, per reconcile_exchange_prices
