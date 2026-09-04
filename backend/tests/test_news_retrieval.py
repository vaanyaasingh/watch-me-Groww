"""get_relevant_news() against a small, hand-crafted fixture — some
duplicates, some irrelevant items, one correlated with a flagged
significant day, one outside the time window, and one for an unrelated
instrument/sector. Every embedding is a controlled 2D vector (not a real
768-dim Gemini/mock embedding) so each item's exact cosine similarity to
the query, and therefore its exact rank, is known ahead of time — see the
comment above each item below for the math.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Diff, Instrument, NewsItem, SignificanceScore, Snapshot
from app.news_retrieval import get_relevant_news

SINCE = datetime(2026, 9, 1, 0, 0)
UNTIL = datetime(2026, 9, 4, 0, 0)


class _FixedEmbeddingProvider:
    """Always returns the same query vector regardless of input text — this
    test is about the ranking/clustering math, not embedding-text
    construction, so the query embedding is just a fixed reference point
    every NewsItem's fixture embedding is placed at a known angle from."""

    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0]


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _news_item(session, *, id_suffix, instrument_id, sector_id, published_at, embedding):
    item = NewsItem(
        instrument_id=instrument_id,
        sector_id=sector_id,
        source="Test Wire",
        url=f"https://example.com/{id_suffix}",
        title=f"Story {id_suffix}",
        published_at=published_at,
        embedding=embedding,
    )
    session.add(item)
    return item


def _mark_significant(session, instrument_id: str, on_date: datetime):
    """A minimal Diff+SignificanceScore pair so `on_date` counts as one of
    this instrument's significant days — mirrors what
    app/ingestion/run_ingestion.py actually persists, without needing a
    full price/diff computation for a retrieval-only test."""
    snapshot = Snapshot(instrument_id=instrument_id, user_id=1, captured_at=on_date, price=100.0)
    session.add(snapshot)
    session.flush()
    diff = Diff(
        instrument_id=instrument_id,
        snapshot_before_id=snapshot.id,
        snapshot_after_id=snapshot.id,
        before_price=100.0,
        after_price=100.0,
        price_delta_pct=0.0,
        ratio_deltas={},
    )
    session.add(diff)
    session.flush()
    session.add(SignificanceScore(diff_id=diff.id, score=3.0, category="statistical", detail="test fixture"))


def test_returns_top_5_deduplicated_and_ranked(session):
    session.add(Instrument(id="RELIANCE.NS", type="equity", sector="Energy"))
    session.add(Instrument(id="TCS.NS", type="equity", sector="IT"))
    _mark_significant(session, "RELIANCE.NS", datetime(2026, 9, 2, 9, 0))
    session.commit()

    # Each embedding is a unit vector at a given angle from the query
    # vector [1,0] (so cosine-to-query = cos(angle)); consecutive items are
    # spaced >=30 degrees apart so no two of them accidentally cluster with
    # EACH OTHER (only A/B, placed at the same angle on purpose, should
    # cluster) — see the comment above each score for the exact math.

    # A: angle 0 deg, cos=1.0, on the significant day (2026-09-02):
    # score = 0.4*1.0 + 0.6*1 = 1.0
    a = _news_item(
        session, id_suffix="a", instrument_id="RELIANCE.NS", sector_id="Energy",
        published_at=datetime(2026, 9, 2, 10, 0), embedding=[1.0, 0.0],
    )
    # B: same angle as A (cos(A,B) = 1.0 >= 0.92 threshold), published
    # later the same day — must be collapsed into A's cluster, with A (the
    # earlier one) surviving as the representative.
    _news_item(
        session, id_suffix="b-duplicate-of-a", instrument_id="RELIANCE.NS", sector_id="Energy",
        published_at=datetime(2026, 9, 2, 11, 0), embedding=[1.0, 0.0],
    )
    # E: angle 45 deg, cos=0.7071, on the significant day:
    # score = 0.4*0.7071 + 0.6*1 = 0.8828 — ranks ABOVE C below despite a
    # lower raw semantic score, purely from the significance correlation —
    # proving that signal actually moves the ranking, not just adds noise.
    e = _news_item(
        session, id_suffix="e", instrument_id="RELIANCE.NS", sector_id="Energy",
        published_at=datetime(2026, 9, 2, 12, 0), embedding=[0.7071067811865476, 0.7071067811865475],
    )
    # C: angle 75 deg, cos=0.2588, NOT a significant day:
    # score = 0.4*0.2588 + 0 = 0.1035
    c = _news_item(
        session, id_suffix="c", instrument_id=None, sector_id="Energy",  # sector-level story, no single instrument
        published_at=datetime(2026, 9, 3, 9, 0), embedding=[0.25881904510252074, 0.9659258262890683],
    )
    # H: angle 105 deg, cos=-0.2588, NOT significant: score = -0.1035
    h = _news_item(
        session, id_suffix="h", instrument_id="RELIANCE.NS", sector_id="Energy",
        published_at=datetime(2026, 9, 3, 10, 0), embedding=[-0.25881904510252085, 0.9659258262890683],
    )
    # I: angle 135 deg, cos=-0.7071, NOT significant: score = -0.2828
    i = _news_item(
        session, id_suffix="i", instrument_id="RELIANCE.NS", sector_id="Energy",
        published_at=datetime(2026, 9, 1, 9, 0), embedding=[-0.7071067811865475, 0.7071067811865476],
    )
    # D: angle 165 deg, cos=-0.9659, NOT significant: score = -0.3864 — the
    # least relevant candidate, expected to be the one bumped out of the top 5.
    _news_item(
        session, id_suffix="d-irrelevant", instrument_id="RELIANCE.NS", sector_id="Energy",
        published_at=datetime(2026, 9, 1, 8, 0), embedding=[-0.9659258262890682, 0.258819045102521],
    )
    # F: perfectly relevant embedding, but published before `since` — must
    # be excluded by the time-window filter regardless of how relevant it looks.
    _news_item(
        session, id_suffix="f-outside-window", instrument_id="RELIANCE.NS", sector_id="Energy",
        published_at=datetime(2026, 8, 25, 9, 0), embedding=[1.0, 0.0],
    )
    # G: perfectly relevant embedding and inside the window, but for a
    # completely different instrument/sector — must be excluded by the
    # instrument-or-sector match, not just ranked low.
    _news_item(
        session, id_suffix="g-wrong-instrument", instrument_id="TCS.NS", sector_id="IT",
        published_at=datetime(2026, 9, 2, 9, 0), embedding=[1.0, 0.0],
    )
    session.commit()

    result = get_relevant_news(
        session, "RELIANCE.NS", SINCE, UNTIL, embedding_provider=_FixedEmbeddingProvider()
    )

    assert [item.url for item in result] == [
        a.url,  # 1.0
        e.url,  # 0.72
        c.url,  # 0.2
        h.url,  # 0.08
        i.url,  # 0.04
    ]


def test_empty_window_returns_empty_list_not_error(session):
    session.add(Instrument(id="RELIANCE.NS", type="equity", sector="Energy"))
    session.commit()

    result = get_relevant_news(
        session, "RELIANCE.NS", SINCE, UNTIL, embedding_provider=_FixedEmbeddingProvider()
    )

    assert result == []


def test_unknown_instrument_still_returns_empty_list(session):
    # No Instrument row at all for this id — get_relevant_news must degrade
    # to matching by instrument_id only (no sector to fall back on), not raise.
    result = get_relevant_news(
        session, "DOES-NOT-EXIST.NS", SINCE, UNTIL, embedding_provider=_FixedEmbeddingProvider()
    )

    assert result == []
