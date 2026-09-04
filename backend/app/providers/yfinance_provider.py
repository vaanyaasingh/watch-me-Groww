"""YFinanceProvider — equity/ETF quotes, history, and news via yfinance.

yfinance is an unofficial API that scrapes/wraps Yahoo Finance and can fail
or change response shape without notice, so every call goes through
`_with_retries` and, on exhausted retries, raises a typed
ProviderUnavailableError instead of letting a raw yfinance exception bubble
up and crash the caller (see docs/SOURCE_OF_TRUTH.md and Feature 5's
staleness handling, which is where this ultimately surfaces to a user).
"""

import logging
import time
from datetime import date, datetime, timezone

import yfinance as yf

from .base import FundNav, MarketDataProvider, PricePoint, Quote, RawNewsItem
from .exceptions import ProviderUnavailableError

logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 0.5


def _with_retries(fn, *, what: str):
    last_exc: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return fn()
        except Exception as exc:  # yfinance raises a mix of exception types depending on failure mode
            last_exc = exc
            logger.warning(
                "yfinance call failed (%s), attempt %d/%d: %s",
                what,
                attempt + 1,
                RETRY_ATTEMPTS,
                exc,
            )
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BASE_DELAY_SECONDS * (2**attempt))
    raise ProviderUnavailableError(
        f"{what}: data temporarily unavailable — yfinance failed after {RETRY_ATTEMPTS} attempts"
    ) from last_exc


def _parse_news_item(item: dict) -> RawNewsItem:
    # yfinance's `.news` shape has changed across versions (a flat dict in
    # older releases, a nested "content" dict in newer ones) — parse both
    # defensively rather than pinning to one yfinance version.
    content = item.get("content", item)

    provider = content.get("provider")
    if isinstance(provider, dict):
        source = provider.get("displayName", "unknown")
    else:
        source = str(item.get("publisher", provider or "unknown"))

    url = None
    canonical = content.get("canonicalUrl")
    if isinstance(canonical, dict):
        url = canonical.get("url")
    url = url or item.get("link", "")

    published_raw = content.get("pubDate") or item.get("providerPublishTime")
    if isinstance(published_raw, (int, float)):
        published_at = datetime.fromtimestamp(published_raw, tz=timezone.utc)
    elif isinstance(published_raw, str):
        try:
            published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
        except ValueError:
            published_at = datetime.now(timezone.utc)
    else:
        published_at = datetime.now(timezone.utc)

    return RawNewsItem(
        source=source,
        url=url,
        title=content.get("title", item.get("title", "")),
        snippet=content.get("summary", item.get("summary", "")),
        published_at=published_at,
    )


class YFinanceProvider(MarketDataProvider):
    def get_quote(self, instrument_id: str) -> Quote:
        def _fetch() -> Quote:
            ticker = yf.Ticker(instrument_id)
            price = ticker.fast_info["lastPrice"]
            info = ticker.info
            ratios = {
                "pe_ratio": info.get("trailingPE"),
                "market_cap": info.get("marketCap"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            }
            return Quote(
                instrument_id=instrument_id,
                price=price,
                ratios=ratios,
                as_of=datetime.now(timezone.utc),
            )

        return _with_retries(_fetch, what=f"get_quote({instrument_id})")

    def get_historical(self, instrument_id: str, start: date, end: date) -> list[PricePoint]:
        def _fetch() -> list[PricePoint]:
            ticker = yf.Ticker(instrument_id)
            df = ticker.history(start=start.isoformat(), end=end.isoformat())
            return [
                PricePoint(
                    date=idx.date(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                )
                for idx, row in df.iterrows()
            ]

        return _with_retries(_fetch, what=f"get_historical({instrument_id})")

    def get_news(self, instrument_id: str) -> list[RawNewsItem]:
        def _fetch() -> list[RawNewsItem]:
            ticker = yf.Ticker(instrument_id)
            return [_parse_news_item(item) for item in (ticker.news or [])]

        return _with_retries(_fetch, what=f"get_news({instrument_id})")

    def get_fund_nav(self, instrument_id: str) -> FundNav:
        raise NotImplementedError(
            "YFinanceProvider does not serve mutual fund NAV data — use AMFIProvider"
        )
