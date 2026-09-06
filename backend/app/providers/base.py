"""MarketDataProvider interface.

Phase 0 deliverable: the interface only. Concrete providers (yfinance, AMFI,
mock) are implemented in Phase 1 and selected via config, so the rest of the
codebase never talks to yfinance/AMFI/Gemini directly — every route handler
and background job depends on this abstraction instead (see
docs/SOURCE_OF_TRUTH.md, "External data access"). A mock implementation
lands first in Phase 1 specifically so judges can run the whole app without
live API credentials.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Quote:
    """A single point-in-time snapshot of an instrument's price and ratios."""

    instrument_id: str
    price: float
    # Ratios are provider-supplied and vary by instrument type (e.g. P/E for
    # equities, expense ratio for ETFs) — kept as a dict rather than fixed
    # fields so Phase 2's diff engine doesn't need a schema migration every
    # time a new ratio is added.
    ratios: dict
    as_of: datetime


@dataclass(frozen=True)
class PricePoint:
    """One OHLCV bar, used by the significance engine for rolling volatility."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class RawNewsItem:
    """A single headline, prior to embedding/clustering (Phase 4 territory)."""

    source: str
    url: str
    title: str
    snippet: str
    published_at: datetime


@dataclass(frozen=True)
class FundNav:
    """A single day's NAV (and subscription status) for a mutual fund, from AMFI."""

    instrument_id: str
    nav: float
    as_of: date
    # The AMFI-published scheme name (e.g. "HDFC Flexi Cap Fund - Growth")
    # — AMFI instruments are keyed by numeric scheme code, which nobody
    # writes news headlines about, so app/subscription_tracker.py needs
    # this to search Google News meaningfully. Optional/defaulted so
    # existing callers that only need nav/as_of don't need updating.
    scheme_name: str | None = None


class MarketDataProvider(ABC):
    """Everything the rest of the app knows about external market data.

    Every external data source (yfinance, Google News RSS, AMFI) is reached
    through an implementation of this interface, never called directly from
    a route handler or scheduled job. Phase 1 adds the yfinance/AMFI/mock
    implementations; this phase only fixes the shape they must all satisfy.
    """

    @abstractmethod
    def get_quote(self, instrument_id: str) -> Quote:
        """Current price and ratios for one instrument."""

    @abstractmethod
    def get_historical(
        self, instrument_id: str, start: date, end: date
    ) -> list[PricePoint]:
        """Daily OHLCV bars for the instrument between `start` and `end`."""

    @abstractmethod
    def get_news(self, instrument_id: str) -> list[RawNewsItem]:
        """Recent headlines for the instrument."""

    @abstractmethod
    def get_fund_nav(self, instrument_id: str) -> FundNav:
        """Latest published NAV for a mutual fund (mutual funds only)."""
