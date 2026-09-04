"""MarketDataProvider interface.

Phase 0 deliverable: the interface only. Concrete providers (yfinance, AMFI,
mock) are implemented in Phase 1 and selected via config, so the rest of the
codebase never talks to yfinance/AMFI/Gemini directly — every route handler
and background job depends on this abstraction instead (see
docs/SOURCE_OF_TRUTH.md, "External data access").
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class InstrumentType(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    MF = "mf"


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"


@dataclass(frozen=True)
class Quote:
    """A single point-in-time snapshot of an instrument's price and ratios."""

    symbol: str
    exchange: Exchange
    price: float
    # Ratios are provider-supplied and vary by instrument type (e.g. P/E for
    # equities, expense ratio for ETFs) — kept as a dict rather than fixed
    # fields so Phase 2's diff engine doesn't need a schema migration every
    # time a new ratio is added.
    ratios: dict
    as_of: datetime


@dataclass(frozen=True)
class HistoricalBar:
    """One OHLCV bar, used by the significance engine for rolling volatility."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class NewsItem:
    """A single headline, prior to embedding/clustering (Phase 4 territory)."""

    source: str
    url: str
    title: str
    snippet: str
    published_at: datetime


@dataclass(frozen=True)
class CorporateAction:
    """A split/bonus/dividend event, used to exclude false "crash" diffs."""

    action_type: str  # e.g. "split", "bonus", "dividend"
    ex_date: date
    ratio: float | None  # e.g. 2.0 for a 1:2 split; None for cash dividends
    amount: float | None  # cash amount for dividends; None otherwise


@dataclass(frozen=True)
class MFNav:
    """A single day's NAV for a mutual fund scheme, from AMFI NAVAll."""

    scheme_code: str
    nav: float
    as_of: date


@dataclass(frozen=True)
class SubscriptionWindowStatus:
    """RBI LRS-driven overseas-fund subscription pause status for a scheme."""

    scheme_code: str
    is_open: bool
    changed_at: datetime | None


class MarketDataProvider(ABC):
    """Everything the rest of the app knows about external market data.

    Every external data source (yfinance, Google News RSS, AMFI) is reached
    through an implementation of this interface, never called directly from
    a route handler or scheduled job. Phase 1 adds the yfinance/AMFI/mock
    implementations; this phase only fixes the shape they must all satisfy.
    """

    @abstractmethod
    def get_quote(self, symbol: str, exchange: Exchange) -> Quote:
        """Current price and ratios for one instrument."""

    @abstractmethod
    def get_historical(
        self, symbol: str, exchange: Exchange, period_days: int
    ) -> list[HistoricalBar]:
        """Daily OHLCV bars for the trailing `period_days`."""

    @abstractmethod
    def get_news(self, symbol: str, sector: str | None = None) -> list[NewsItem]:
        """Recent headlines for the instrument, and optionally its sector."""

    @abstractmethod
    def get_corporate_actions(
        self, symbol: str, exchange: Exchange
    ) -> list[CorporateAction]:
        """Known splits/bonuses/dividends for the instrument."""

    @abstractmethod
    def get_mf_nav(self, scheme_code: str) -> MFNav:
        """Latest published NAV for a mutual fund scheme."""

    @abstractmethod
    def get_subscription_window(self, scheme_code: str) -> SubscriptionWindowStatus:
        """Current overseas-subscription window status for a scheme."""
