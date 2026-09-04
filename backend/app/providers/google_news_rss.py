"""GoogleNewsRSSProvider — date-bounded Google News RSS search
(docs/plan.md §6, "pull Google News RSS for company name and separately
for sector").

Not a MarketDataProvider implementation (its shape doesn't fit: a free-text
query and a date range, not an instrument_id) — but it's still the one seam
this codebase goes through for Google News, never called directly from the
ingestion job's date/query construction elsewhere (docs/SOURCE_OF_TRUTH.md,
"External data access").
"""

import html
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from email.utils import parsedate_to_datetime

import requests

from .base import RawNewsItem

RSS_SEARCH_URL = "https://news.google.com/rss/search"
REQUEST_TIMEOUT_SECONDS = 10

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    # Google's RSS <description> is a raw HTML snippet (an <a> tag plus a
    # trailing <font> byline, with entities like &nbsp;), not plain text —
    # strip tags and unescape entities to get a clean embedding input.
    return html.unescape(_HTML_TAG_RE.sub("", text)).strip()


class GoogleNewsRSSProvider:
    def search(self, query: str, after: date, before: date) -> list[RawNewsItem]:
        params = {
            "q": f"{query} after:{after.isoformat()} before:{before.isoformat()}",
            "hl": "en-IN",
            "gl": "IN",
            "ceid": "IN:en",
        }
        response = requests.get(RSS_SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        root = ET.fromstring(response.content)

        items = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            snippet = _strip_html(item.findtext("description") or "")

            source_el = item.find("source")
            source = source_el.text.strip() if source_el is not None and source_el.text else "Google News"
            # Titles come back as "Headline - Source" — drop the redundant
            # suffix now that `source` is captured separately.
            suffix = f" - {source}"
            if title.endswith(suffix):
                title = title[: -len(suffix)]

            pub_date_raw = item.findtext("pubDate")
            published_at = parsedate_to_datetime(pub_date_raw) if pub_date_raw else datetime.utcnow()

            items.append(
                RawNewsItem(source=source, url=link, title=title, snippet=snippet, published_at=published_at)
            )
        return items
