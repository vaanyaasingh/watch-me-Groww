"""LiveMarketDataProvider — routes each call to YFinanceProvider or
AMFIProvider based on instrument_id's own shape, so a single
MARKET_DATA_PROVIDER=live setting can serve both equities/ETFs and mutual
funds without the caller needing to know which underlying source handles
which instrument (the gap flagged as an open question after Phase 1/2).

Routing is by shape, not a DB lookup, on purpose: a provider must stay
usable with zero setup (see docs/README.md) and must not depend on the data
model (see docs/SOURCE_OF_TRUTH.md, "External data access") — importing
Instrument here to check `.type` would create exactly that dependency.
AMFI scheme codes are purely numeric (e.g. "120503"); every yfinance-style
ticker used in this project carries a non-numeric exchange suffix
(".NS"/".BO"), so the two id spaces never collide.
"""

from datetime import date

from .amfi_provider import AMFIProvider
from .base import FundNav, MarketDataProvider, PricePoint, Quote, RawNewsItem
from .yfinance_provider import YFinanceProvider


class LiveMarketDataProvider(MarketDataProvider):
    def __init__(
        self,
        yfinance_provider: MarketDataProvider | None = None,
        amfi_provider: MarketDataProvider | None = None,
    ):
        # Accept injected providers (used by tests to verify routing without
        # a network call) but default to the real ones.
        self._yfinance = yfinance_provider or YFinanceProvider()
        self._amfi = amfi_provider or AMFIProvider()

    @staticmethod
    def _is_mf_scheme_code(instrument_id: str) -> bool:
        return instrument_id.isdigit()

    def get_quote(self, instrument_id: str) -> Quote:
        if self._is_mf_scheme_code(instrument_id):
            raise NotImplementedError(
                f"{instrument_id!r} looks like an AMFI scheme code — mutual funds have "
                "no live quote, use get_fund_nav instead"
            )
        return self._yfinance.get_quote(instrument_id)

    def get_historical(self, instrument_id: str, start: date, end: date) -> list[PricePoint]:
        if self._is_mf_scheme_code(instrument_id):
            raise NotImplementedError(
                f"{instrument_id!r} looks like an AMFI scheme code — no historical OHLCV for mutual funds"
            )
        return self._yfinance.get_historical(instrument_id, start, end)

    def get_news(self, instrument_id: str) -> list[RawNewsItem]:
        if self._is_mf_scheme_code(instrument_id):
            raise NotImplementedError(
                f"{instrument_id!r} looks like an AMFI scheme code — no news lookup for mutual funds"
            )
        return self._yfinance.get_news(instrument_id)

    def get_fund_nav(self, instrument_id: str) -> FundNav:
        if not self._is_mf_scheme_code(instrument_id):
            raise NotImplementedError(
                f"{instrument_id!r} looks like an equity/ETF ticker — use get_quote instead"
            )
        return self._amfi.get_fund_nav(instrument_id)
