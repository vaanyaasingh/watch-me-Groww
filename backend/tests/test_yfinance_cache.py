"""YFinanceProvider.get_quote()'s throttling cache (app/providers/
yfinance_provider.py) — zero network, a fake yf.Ticker stands in so this
runs everywhere requires_network-gated tests don't.
"""

import time

import pytest

import app.providers.yfinance_provider as yfinance_provider_module
from app.providers.yfinance_provider import YFinanceProvider


class _FakeFastInfo(dict):
    pass


class _FakeTicker:
    call_count = 0

    def __init__(self, symbol):
        self.symbol = symbol
        type(self).call_count += 1
        self.fast_info = _FakeFastInfo(lastPrice=100.0 + type(self).call_count)
        self.info = {"trailingPE": 20.0, "marketCap": 1_000_000}


@pytest.fixture(autouse=True)
def _reset_cache_and_fake_ticker(monkeypatch):
    yfinance_provider_module._quote_cache.clear()
    _FakeTicker.call_count = 0
    monkeypatch.setattr(yfinance_provider_module.yf, "Ticker", _FakeTicker)
    yield
    yfinance_provider_module._quote_cache.clear()


def test_second_call_within_ttl_does_not_refetch():
    provider = YFinanceProvider()

    first = provider.get_quote("RELIANCE.NS")
    second = provider.get_quote("RELIANCE.NS")

    assert _FakeTicker.call_count == 1  # only the first call actually hit yfinance
    assert second.price == first.price


def test_call_after_ttl_expiry_refetches(monkeypatch):
    provider = YFinanceProvider()
    provider.get_quote("RELIANCE.NS")
    assert _FakeTicker.call_count == 1

    # Simulate the TTL having elapsed without a real sleep.
    real_monotonic = time.monotonic()
    monkeypatch.setattr(time, "monotonic", lambda: real_monotonic + yfinance_provider_module.QUOTE_CACHE_TTL_SECONDS + 1)

    provider.get_quote("RELIANCE.NS")

    assert _FakeTicker.call_count == 2


def test_different_instruments_are_cached_independently():
    provider = YFinanceProvider()

    provider.get_quote("RELIANCE.NS")
    provider.get_quote("TCS.NS")
    provider.get_quote("RELIANCE.NS")

    assert _FakeTicker.call_count == 2  # RELIANCE.NS's second call was served from cache, TCS.NS's own first call wasn't
