"""MockProvider — reads canned data from a local fixture file.

Zero network calls, zero credentials. This is the default provider (see
config.py) precisely so the app is runnable out of the box, including for
judges without API keys or network access.
"""

import json
from datetime import date, datetime
from pathlib import Path

from .base import FundNav, MarketDataProvider, PricePoint, Quote, RawNewsItem
from .exceptions import InstrumentNotFoundError

DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "fixtures" / "sample_market_data.json"
)


class MockProvider(MarketDataProvider):
    def __init__(self, fixture_path: str | Path | None = None):
        path = Path(fixture_path) if fixture_path else DEFAULT_FIXTURE_PATH
        with open(path) as f:
            self._data = json.load(f)

    def _instrument(self, instrument_id: str) -> dict:
        try:
            return self._data["instruments"][instrument_id]
        except KeyError:
            raise InstrumentNotFoundError(instrument_id) from None

    def get_quote(self, instrument_id: str) -> Quote:
        q = self._instrument(instrument_id)["quote"]
        return Quote(
            instrument_id=instrument_id,
            price=q["price"],
            ratios=q["ratios"],
            as_of=datetime.fromisoformat(q["as_of"]),
        )

    def get_historical(self, instrument_id: str, start: date, end: date) -> list[PricePoint]:
        bars = self._instrument(instrument_id)["historical"]
        points = []
        for bar in bars:
            bar_date = date.fromisoformat(bar["date"])
            if start <= bar_date <= end:
                points.append(
                    PricePoint(
                        date=bar_date,
                        open=bar["open"],
                        high=bar["high"],
                        low=bar["low"],
                        close=bar["close"],
                        volume=bar["volume"],
                    )
                )
        return points

    def get_news(self, instrument_id: str) -> list[RawNewsItem]:
        news = self._instrument(instrument_id).get("news", [])
        return [
            RawNewsItem(
                source=n["source"],
                url=n["url"],
                title=n["title"],
                snippet=n["snippet"],
                published_at=datetime.fromisoformat(n["published_at"]),
            )
            for n in news
        ]

    def get_fund_nav(self, instrument_id: str) -> FundNav:
        try:
            record = self._data["mutual_funds"][instrument_id]
        except KeyError:
            raise InstrumentNotFoundError(instrument_id) from None
        return FundNav(
            instrument_id=instrument_id,
            nav=record["nav"],
            as_of=date.fromisoformat(record["as_of"]),
        )
