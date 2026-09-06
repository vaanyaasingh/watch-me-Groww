"""Feature 6 (MF/ETF Subscription-Window Tracker) — the real half.

docs/plan.md's own tech-stack section names "AMFI data" as the source for
RBI LRS-driven overseas-fund subscription pauses, but AMFI's NAVAll feed
(app/providers/amfi_provider.py) carries only scheme code/name/NAV/date —
no subscription-status field exists there, and no other free, structured,
machine-readable feed for this was found either (checked before writing
this module): AMCs announce a pause/resume via their own press releases,
not a queryable API. What IS real and checkable is that Google News
carries those announcements as ordinary headlines — e.g. "PGIM India
suspends fresh subscriptions in three international FoFs" — so this reuses
the same GoogleNewsRSSProvider search() the price-side news pipeline
already depends on, tagged to a specific scheme rather than a company/
sector, then classifies the retrieved headlines with a small rule-based
regex (never an LLM call — this is a status decision, same "rule-based,
auditable" bar docs/SOURCE_OF_TRUTH.md holds significance scoring to).

Honesty constraint this module is built around: if no matching headline is
found, the existing status is left untouched — never guessed, never
defaulted to "closed" just because a fund is a plausible LRS candidate.
A fund with no real news about it will correctly show no status change.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Instrument, SubscriptionWindow
from app.providers.base import MarketDataProvider, RawNewsItem
from app.providers.google_news_rss import GoogleNewsRSSProvider

logger = logging.getLogger(__name__)

# How far back to search for a status-change headline on each refresh —
# generous relative to NEWS_INGESTION_LOOKBACK_DAYS (app/ingestion/
# run_ingestion.py's 3 days for price-side news) since these
# announcements are comparatively rare per fund and a missed run
# shouldn't lose one.
SUBSCRIPTION_NEWS_LOOKBACK_DAYS = 21

_CLOSE_PATTERN = re.compile(
    r"\b(suspend(?:s|ed|ing)?|suspension|pause[sd]?|halt(?:s|ed|ing)?|stop(?:s|ped|ping)?|clos(?:es|ed|ing))\b"
    r"(?:\s+\w+){0,4}?\s+"
    r"\b(subscriptions?|lumpsum|sips?|stps?|investments?|inflows?)\b",
    re.IGNORECASE,
)
_OPEN_PATTERN = re.compile(
    r"\b(resum(?:es|ed|ing)|reopen(?:s|ed|ing)?|restart(?:s|ed|ing)?)\b"
    r"(?:\s+\w+){0,4}?\s+"
    r"\b(subscriptions?|lumpsum|sips?|stps?|investments?|inflows?)\b",
    re.IGNORECASE,
)


def classify_headline(title: str) -> str | None:
    """Rule-based, not a model call — returns "closed"/"open"/None (no
    signal). Checked in this order because a headline mentioning both a
    past pause and a present resumption ("after suspending X, Y now
    resumes subscriptions") is about the resumption; that's also the more
    recently-true fact a reader cares about."""
    if _OPEN_PATTERN.search(title):
        return "open"
    if _CLOSE_PATTERN.search(title):
        return "closed"
    return None


def _get_or_create(session: Session, instrument_id: str) -> SubscriptionWindow:
    window = session.query(SubscriptionWindow).filter_by(instrument_id=instrument_id).first()
    if window is None:
        window = SubscriptionWindow(instrument_id=instrument_id, status="open")
        session.add(window)
        session.flush()
    return window


def refresh_subscription_window(
    session: Session,
    instrument: Instrument,
    provider: MarketDataProvider,
    google_news_provider: GoogleNewsRSSProvider,
    now: datetime,
) -> SubscriptionWindow | None:
    """One refresh per mutual-fund Instrument per ingestion run (mirrors
    run_ingestion.py's "one provider call per instrument, never per user"
    rule). Returns the SubscriptionWindow row whether or not its status
    actually changed; returns None for non-MF instruments (nothing to do
    — equities/ETFs/indices have no subscription-window concept)."""
    if instrument.type != "mf":
        return None

    try:
        fund_nav = provider.get_fund_nav(instrument.id)
    except Exception as exc:
        logger.warning("subscription-window refresh: couldn't resolve scheme name for %s: %s", instrument.id, exc)
        return _get_or_create(session, instrument.id)

    scheme_name = fund_nav.scheme_name
    if not scheme_name:
        # No searchable name available (e.g. a mock fixture entry missing
        # it) — can't do a meaningful Google News query by scheme code
        # alone, so there's nothing honest to search for.
        return _get_or_create(session, instrument.id)

    window = _get_or_create(session, instrument.id)
    window.scheme_name = scheme_name

    after = (now - timedelta(days=SUBSCRIPTION_NEWS_LOOKBACK_DAYS)).date()
    before = now.date()
    try:
        headlines: list[RawNewsItem] = google_news_provider.search(
            f"{scheme_name} subscription", after=after, before=before
        )
    except Exception as exc:
        logger.warning("subscription-window refresh: news search failed for %s: %s", scheme_name, exc)
        return window

    # Most recent real signal wins — an older "suspended" headline
    # shouldn't override a newer "resumed" one just because of search
    # result ordering.
    for item in sorted(headlines, key=lambda h: h.published_at, reverse=True):
        classification = classify_headline(item.title)
        if classification is None:
            continue
        if classification != window.status:
            window.status = classification
            window.last_changed_at = now
        window.evidence = f"{item.title} ({item.source}, {item.published_at.date().isoformat()})"
        break

    return window
