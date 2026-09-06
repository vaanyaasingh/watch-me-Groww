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

# docs/plan.md's tech-stack section calls for "a simple Postgres-based
# cache table (or Memorystore/Redis)" to throttle yfinance calls — this is
# a plain in-process dict instead: yfinance is unofficial and rate-limit-
# sensitive (see the module docstring), and the batch ingestion job
# already calls get_quote() once per distinct watched instrument per run
# (never per user, see run_ingestion.py), so what this cache actually
# guards against is a *different* kind of duplication — several requests
# in quick succession (e.g. the sparkline endpoint and an ingestion run
# landing close together) re-fetching the same ticker. A short TTL is
# enough for that without a second moving part (Postgres/Redis) this
# project doesn't otherwise need; yfinance's own data is itself typically
# 15+ minutes delayed, so a 60-second cache never trades away real
# freshness. Process-local by design — acceptable for a single-instance
# deployment (this project's), not a claim it'd scale to many workers.
QUOTE_CACHE_TTL_SECONDS = 60
_quote_cache: dict[str, tuple[float, Quote]] = {}


def _cached_quote(instrument_id: str) -> Quote | None:
    entry = _quote_cache.get(instrument_id)
    if entry is None:
        return None
    fetched_at, quote = entry
    if time.monotonic() - fetched_at > QUOTE_CACHE_TTL_SECONDS:
        return None
    return quote


def _store_quote(instrument_id: str, quote: Quote) -> None:
    _quote_cache[instrument_id] = (time.monotonic(), quote)


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
        cached = _cached_quote(instrument_id)
        if cached is not None:
            return cached

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

        quote = _with_retries(_fetch, what=f"get_quote({instrument_id})")
        _store_quote(instrument_id, quote)
        return quote

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
