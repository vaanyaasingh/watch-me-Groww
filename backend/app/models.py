"""SQLAlchemy models — entity names match docs/plan.md §5 exactly.

Diff and SignificanceScore are persisted (not computed-on-read): the
attention feed (Feature 3) needs to show what fired in past sessions, not
just the current one, and a persisted row is trivial to stop reading later
if it turns out to be unnecessary — reconstructing lost history is not.
"""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.vector_type import EmbeddingType


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Firebase Authentication is the identity provider (docs/plan.md §4) —
    # this table just links a Firebase identity to app-owned rows.
    firebase_uid: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Instrument(Base):
    __tablename__ = "instrument"

    # The instrument_id is the natural key MarketDataProvider already uses
    # (a yfinance-style ticker like "RELIANCE.NS", or an AMFI scheme code
    # like "120503") — reusing it as the primary key avoids a second id
    # that every provider call would otherwise need translating to/from.
    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String)  # "equity" | "etf" | "mf"
    exchange: Mapped[str | None] = mapped_column(String, nullable=True)  # "NSE" | "BSE" | None for MF
    sector: Mapped[str | None] = mapped_column(String, nullable=True)
    # List of {"action_type", "ex_date", "ratio", "amount"} dicts (see
    # backend/fixtures/sample_market_data.json for the shape) — read by
    # app/significance.py to exclude corporate-action discontinuities.
    corporate_action_history: Mapped[list | None] = mapped_column(JSON, nullable=True)


class WatchlistItem(Base):
    __tablename__ = "watchlist_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instrument.id"), index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Snapshot(Base):
    __tablename__ = "snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instrument.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    price: Mapped[float] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ratios: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    top_headlines: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Discrete-event fields (docs/plan.md §3, category 4): wired now so the
    # significance engine has somewhere to read them from, even though no
    # provider populates real earnings dates or rating changes yet.
    corporate_action: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    earnings_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    rating_change: Mapped[str | None] = mapped_column(String, nullable=True)
    # "live" | "market_closed" — set by the Phase 3 ingestion job so a
    # snapshot that's simply old because NSE is shut isn't later confused
    # with a broken/stuck feed (that distinction is Feature 5's staleness
    # indicator, Phase 7; this column is the data it will read).
    status: Mapped[str] = mapped_column(String, default="live")


class Diff(Base):
    __tablename__ = "diff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instrument.id"), index=True)
    snapshot_before_id: Mapped[int] = mapped_column(ForeignKey("snapshot.id"))
    snapshot_after_id: Mapped[int] = mapped_column(ForeignKey("snapshot.id"))
    before_price: Mapped[float] = mapped_column(Float)
    after_price: Mapped[float] = mapped_column(Float)
    price_delta_pct: Mapped[float] = mapped_column(Float)
    before_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    after_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume_delta_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ratio_deltas: Mapped[dict] = mapped_column(JSON, default=dict)
    # Top-5 post-ranking news items (docs/plan.md §6) — Phase 4 builds
    # get_relevant_news() (app/news_retrieval.py) but doesn't write its
    # result here yet; that wiring happens in Phase 5 alongside narrative
    # generation, which is what actually consumes this field.
    news_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NewsItem(Base):
    __tablename__ = "news_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Nullable: a sector-level story (from the sector RSS query) isn't about
    # any one instrument — it's tagged by sector_id only. A company-level
    # story gets both, so it's still found by a sector-wide query.
    instrument_id: Mapped[str | None] = mapped_column(ForeignKey("instrument.id"), nullable=True, index=True)
    sector_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    source: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String, unique=True, index=True)
    title: Mapped[str] = mapped_column(String)
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingType, nullable=True)
    # Assigned by app/news_retrieval.py's clustering step at query time, not
    # at ingestion — see that module's docstring for why it's left null here.
    dedupe_cluster_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SignificanceScore(Base):
    __tablename__ = "significance_score"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    diff_id: Mapped[int] = mapped_column(ForeignKey("diff.id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String)  # "statistical" | "threshold" | "event"
    # Not in docs/plan.md §5's field list — added because "auditable" (see
    # docs/SOURCE_OF_TRUTH.md) needs a human-readable reason a category
    # fired, not just a bare number; flagged as a deliberate addition in the
    # Phase 2 summary rather than left silent.
    detail: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alert"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instrument.id"), index=True)
    condition: Mapped[dict] = mapped_column(JSON)
    adaptive_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active")


class SubscriptionWindow(Base):
    __tablename__ = "subscription_window"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instrument.id"), index=True, unique=True)
    status: Mapped[str] = mapped_column(String)
    last_changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
