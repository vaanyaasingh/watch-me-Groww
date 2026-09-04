"""AMFIProvider — mutual fund NAV via AMFI's public NAVAll feed.

AMFI has no equity/ETF data, so those interface methods just raise
NotImplementedError — a deployment that needs both equity and MF data picks
per-instrument-type routing at the call site (open question, see phase
summary), not inside this class.
"""

from datetime import date, datetime

import requests

from .base import FundNav, MarketDataProvider, PricePoint, Quote, RawNewsItem
from .exceptions import InstrumentNotFoundError

NAVALL_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
REQUEST_TIMEOUT_SECONDS = 10


class AMFIProvider(MarketDataProvider):
    def get_quote(self, instrument_id: str) -> Quote:
        raise NotImplementedError("AMFIProvider only serves mutual fund NAV data")

    def get_historical(self, instrument_id: str, start: date, end: date) -> list[PricePoint]:
        raise NotImplementedError("AMFIProvider only serves mutual fund NAV data")

    def get_news(self, instrument_id: str) -> list[RawNewsItem]:
        raise NotImplementedError("AMFIProvider only serves mutual fund NAV data")

    def get_fund_nav(self, instrument_id: str) -> FundNav:
        response = requests.get(NAVALL_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        # NAVAll.txt is a semicolon-delimited dump: Scheme Code;ISIN Div
        # Payout;ISIN Div Reinvestment;Scheme Name;Plan;Option;NAV;Date —
        # plus AMC name header lines and blank separators mixed in. Skip
        # anything that doesn't parse as a full 8-field NAV row rather than
        # trying to detect header lines by content.
        for line in response.text.splitlines():
            fields = line.split(";")
            if len(fields) < 8:
                continue
            scheme_code = fields[0].strip()
            if scheme_code != instrument_id:
                continue
            try:
                nav = float(fields[6].strip())
                as_of = datetime.strptime(fields[7].strip(), "%d-%b-%Y").date()
            except ValueError:
                continue  # malformed row (e.g. NAV shown as "N.A.") — keep scanning
            return FundNav(instrument_id=instrument_id, nav=nav, as_of=as_of)
        raise InstrumentNotFoundError(instrument_id)
