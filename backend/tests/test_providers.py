"""Shared-interface test suite, run against all three MarketDataProvider
implementations.

MockProvider tests always run (zero network, zero credentials — the whole
point of Phase 1's mock provider). YFinanceProvider/AMFIProvider live tests
are skipped automatically when no network is available, e.g. in a sandboxed
CI runner, so this suite never fails for reasons unrelated to the code.
"""

import socket
from datetime import date

import pytest

from app.providers.amfi_provider import AMFIProvider
from app.providers.exceptions import InstrumentNotFoundError
from app.providers.mock_provider import MockProvider
from app.providers.yfinance_provider import YFinanceProvider

START = date(2024, 1, 1)
END = date(2024, 1, 31)


def _network_available() -> bool:
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2).close()
        return True
    except OSError:
        return False


requires_network = pytest.mark.skipif(
    not _network_available(), reason="no network access in this environment"
)


# --- MockProvider: must always run and pass, no network, no credentials ---


@pytest.fixture
def mock_provider() -> MockProvider:
    # Pin `today` so MockProvider's date-shift (see mock_provider.py) is a
    # no-op and every assertion below can keep using the fixture's original
    # Jan 2024 dates verbatim.
    return MockProvider(today=date(2024, 1, 30))


def test_mock_get_quote(mock_provider):
    quote = mock_provider.get_quote("RELIANCE.NS")
    assert quote.instrument_id == "RELIANCE.NS"
    assert quote.price > 0
    assert isinstance(quote.ratios, dict)


def test_mock_get_historical(mock_provider):
    bars = mock_provider.get_historical("RELIANCE.NS", START, END)
    assert len(bars) > 0
    assert all(b.close > 0 for b in bars)
    assert all(START <= b.date <= END for b in bars)


def test_mock_get_historical_respects_date_range(mock_provider):
    bars = mock_provider.get_historical("RELIANCE.NS", date(2024, 1, 1), date(2024, 1, 5))
    assert all(b.date <= date(2024, 1, 5) for b in bars)


def test_mock_get_news(mock_provider):
    news = mock_provider.get_news("RELIANCE.NS")
    assert isinstance(news, list)
    assert all(n.title for n in news)


def test_mock_get_fund_nav(mock_provider):
    nav = mock_provider.get_fund_nav("120503")
    assert nav.instrument_id == "120503"
    assert nav.nav > 0


def test_mock_unknown_equity_raises(mock_provider):
    with pytest.raises(InstrumentNotFoundError):
        mock_provider.get_quote("NOPE.NS")


def test_mock_unknown_fund_raises(mock_provider):
    with pytest.raises(InstrumentNotFoundError):
        mock_provider.get_fund_nav("999999")


def test_mock_fixture_covers_required_instrument_counts(mock_provider):
    equities = [
        v for v in mock_provider._data["instruments"].values() if v["type"] == "equity"
    ]
    etfs = [v for v in mock_provider._data["instruments"].values() if v["type"] == "etf"]
    assert len(equities) >= 5
    assert len(etfs) >= 2
    assert len(mock_provider._data["mutual_funds"]) >= 2


def test_mock_meaningful_change_scenario_present(mock_provider):
    """HDFCBANK.NS: mostly low, steady daily moves, then one day far outside
    that — the raw material for Phase 2's z-score/ATR significance test."""
    bars = mock_provider.get_historical("HDFCBANK.NS", START, END)
    closes = [b.close for b in bars]
    daily_returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
    assert max(abs(r) for r in daily_returns) > 0.05


def test_mock_corporate_action_scenario_present(mock_provider):
    """ICICIBANK.NS: a >30% single-day move only makes sense as a corporate
    action (here, a 1:1 bonus), never organic trading — Phase 2's exclusion
    logic needs a case like this to prove it doesn't get flagged as a crash."""
    bars = mock_provider.get_historical("ICICIBANK.NS", START, END)
    closes = [b.close for b in bars]
    daily_returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
    assert min(daily_returns) < -0.3


# --- AMFIProvider ---


def test_amfi_raises_for_equity_methods():
    provider = AMFIProvider()
    with pytest.raises(NotImplementedError):
        provider.get_quote("RELIANCE.NS")
    with pytest.raises(NotImplementedError):
        provider.get_historical("RELIANCE.NS", START, END)
    with pytest.raises(NotImplementedError):
        provider.get_news("RELIANCE.NS")


@requires_network
def test_amfi_get_fund_nav_live():
    provider = AMFIProvider()
    nav = provider.get_fund_nav("120503")
    assert nav.nav > 0


# --- YFinanceProvider ---


def test_yfinance_raises_for_fund_nav():
    provider = YFinanceProvider()
    with pytest.raises(NotImplementedError):
        provider.get_fund_nav("120503")


@requires_network
def test_yfinance_get_quote_live():
    provider = YFinanceProvider()
    quote = provider.get_quote("RELIANCE.NS")
    assert quote.price > 0


@requires_network
def test_yfinance_get_historical_live():
    provider = YFinanceProvider()
    bars = provider.get_historical("RELIANCE.NS", date(2024, 1, 1), date(2024, 1, 31))
    assert len(bars) > 0
