"""The one place MARKET_DATA_PROVIDER is read.

Nothing else in the codebase should read this env var directly (see
docs/SOURCE_OF_TRUTH.md, "External data access") — everything should call
get_market_data_provider() instead, so swapping providers never means
hunting through the codebase for scattered os.environ reads.
"""

import os

from .amfi_provider import AMFIProvider
from .base import MarketDataProvider
from .mock_provider import MockProvider
from .yfinance_provider import YFinanceProvider

_PROVIDERS: dict[str, type[MarketDataProvider]] = {
    "mock": MockProvider,
    "yfinance": YFinanceProvider,
    "amfi": AMFIProvider,
}


def get_market_data_provider() -> MarketDataProvider:
    # Defaults to mock so the app runs out of the box with no setup, no
    # credentials, and no network — required so judges can run this cold.
    name = os.environ.get("MARKET_DATA_PROVIDER", "mock").lower()
    try:
        provider_cls = _PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown MARKET_DATA_PROVIDER={name!r}; expected one of {sorted(_PROVIDERS)}"
        ) from None
    return provider_cls()
