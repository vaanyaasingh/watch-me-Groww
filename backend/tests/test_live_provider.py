"""LiveMarketDataProvider routing — verified with injected fake providers,
no network calls, so this suite never depends on live yfinance/AMFI access.
"""

from datetime import date

import pytest

from app.providers.base import FundNav, PricePoint, Quote
from app.providers.live_provider import LiveMarketDataProvider


class _FakeYFinance:
    def get_quote(self, instrument_id):
        return Quote(instrument_id=instrument_id, price=100.0, ratios={}, as_of=None)

    def get_historical(self, instrument_id, start, end):
        return [PricePoint(date=start, open=1, high=1, low=1, close=1, volume=1)]

    def get_news(self, instrument_id):
        return []

    def get_fund_nav(self, instrument_id):
        raise AssertionError("should never be routed to yfinance")


class _FakeAMFI:
    def get_quote(self, instrument_id):
        raise AssertionError("should never be routed to amfi")

    def get_historical(self, instrument_id, start, end):
        raise AssertionError("should never be routed to amfi")

    def get_news(self, instrument_id):
        raise AssertionError("should never be routed to amfi")

    def get_fund_nav(self, instrument_id):
        return FundNav(instrument_id=instrument_id, nav=42.0, as_of=date(2024, 1, 1))


@pytest.fixture
def live_provider():
    return LiveMarketDataProvider(yfinance_provider=_FakeYFinance(), amfi_provider=_FakeAMFI())


def test_ticker_routes_to_yfinance_for_quote(live_provider):
    quote = live_provider.get_quote("RELIANCE.NS")
    assert quote.price == 100.0


def test_scheme_code_routes_to_amfi_for_fund_nav(live_provider):
    nav = live_provider.get_fund_nav("120503")
    assert nav.nav == 42.0


def test_scheme_code_rejected_for_quote(live_provider):
    with pytest.raises(NotImplementedError):
        live_provider.get_quote("120503")


def test_ticker_rejected_for_fund_nav(live_provider):
    with pytest.raises(NotImplementedError):
        live_provider.get_fund_nav("RELIANCE.NS")


def test_scheme_code_rejected_for_historical_and_news(live_provider):
    with pytest.raises(NotImplementedError):
        live_provider.get_historical("120503", date(2024, 1, 1), date(2024, 1, 31))
    with pytest.raises(NotImplementedError):
        live_provider.get_news("120503")
