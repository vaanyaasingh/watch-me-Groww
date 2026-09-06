"""MockProvider — reads canned data from a local fixture file.

Zero network calls, zero credentials. This is the default provider (see
config.py) precisely so the app is runnable out of the box, including for
judges without API keys or network access.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from .base import FundNav, MarketDataProvider, PricePoint, Quote, RawNewsItem
from .exceptions import InstrumentNotFoundError

DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "fixtures" / "sample_market_data.json"
)


class MockProvider(MarketDataProvider):
    def __init__(self, fixture_path: str | Path | None = None, today: date | None = None):
        path = Path(fixture_path) if fixture_path else DEFAULT_FIXTURE_PATH
        with open(path) as f:
            self._data = json.load(f)
        self._date_shift = self._compute_date_shift(today or date.today())

    def _compute_date_shift(self, today: date) -> timedelta:
        """The fixture's dates are fixed (Jan 2024) so the file stays
        reviewable and deterministic — but a provider that always answers
        "as of Jan 2024" is useless to anything asking "what happened in
        the last N days" (e.g. the Phase 3 ingestion job's historical
        lookback), no matter which real day this process happens to run
        on. Shift every date by a whole number of weeks so the series
        always ends within the last few days of `today`, while every bar
        stays on the same day of the week it was authored on (Fridays stay
        Fridays) — a plain day-count shift would drift weekdays instead.
        """
        last_date = max(
            date.fromisoformat(bar["date"])
            for instrument in self._data["instruments"].values()
            for bar in instrument["historical"]
        )
        yesterday = today - timedelta(days=1)
        weeks = (yesterday - last_date).days // 7
        return timedelta(weeks=weeks)

    def _shift_date(self, d: date) -> date:
        return d + self._date_shift

    def _shift_datetime(self, dt: datetime) -> datetime:
        return dt + self._date_shift

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
            as_of=self._shift_datetime(datetime.fromisoformat(q["as_of"])),
        )

    def get_historical(self, instrument_id: str, start: date, end: date) -> list[PricePoint]:
        bars = self._instrument(instrument_id)["historical"]
        points = []
        for bar in bars:
            bar_date = self._shift_date(date.fromisoformat(bar["date"]))
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
                published_at=self._shift_datetime(datetime.fromisoformat(n["published_at"])),
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
            as_of=self._shift_date(date.fromisoformat(record["as_of"])),
            scheme_name=record.get("scheme_name"),
        )
