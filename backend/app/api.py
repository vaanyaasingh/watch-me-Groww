"""REST API for the frontend (Phase 6). No prior phase built any HTTP
routes — everything through Phase 5 is an internal module the ingestion
job and future callers use directly. This is that first caller: a thin
HTTP layer over app/significance.py, app/news_retrieval.py, and
app/narrative.py, adding no business logic of its own.

No auth system exists yet (Firebase Auth is a later docs/plan.md §4 item)
— every route operates on app/seed.py's single DEMO_USER_ID rather than a
real per-session identity. Swapping in real auth later only touches this
file's user-resolution, not the frontend's shape or any other module.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Alert,
    Diff,
    Instrument,
    NewsItem,
    SignificanceScore,
    Snapshot,
    SubscriptionWindow,
    WatchlistItem,
)
from app.narrative import generate_digest
from app.news_retrieval import get_relevant_news
from app.reconciliation import reconcile_exchange_prices
from app.seed import DEMO_USER_ID
from app.staleness import compute_display_status

router = APIRouter(prefix="/api")

# Feature 3 ("Significance-Ranked Attention Feed"): how many diffs surface
# prominently before the rest collapse — a named constant, not a number
# buried in the ranking logic below, per the Phase 6 brief.
ATTENTION_FEED_TOP_N = 5

IST = ZoneInfo("Asia/Kolkata")


def _now_ist() -> datetime:
    # Naive IST, same convention as app/ingestion/run_ingestion.py and
    # app/market_calendar.py — see those modules for why.
    return datetime.now(IST).replace(tzinfo=None)


def _exchange_counterpart(instrument_id: str) -> str | None:
    """"RELIANCE.NS" <-> "RELIANCE.BO" — the other exchange listing of the
    same company, if this project's Instrument catalog has both. Used by
    the digest endpoint to surface NSE/BSE disagreement (Phase 7
    requirement 2); returns None for anything that isn't a dual-suffix
    equity ticker (ETFs/MFs/scheme codes have no such counterpart)."""
    if instrument_id.endswith(".NS"):
        return instrument_id[: -len(".NS")] + ".BO"
    if instrument_id.endswith(".BO"):
        return instrument_id[: -len(".BO")] + ".NS"
    return None


def _latest_snapshot(session, instrument_id: str, user_id: int) -> Snapshot | None:
    stmt = (
        select(Snapshot)
        .where(Snapshot.instrument_id == instrument_id, Snapshot.user_id == user_id)
        .order_by(Snapshot.captured_at.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def _latest_diff(session, instrument_id: str, user_id: int) -> Diff | None:
    stmt = (
        select(Diff)
        .join(Snapshot, Diff.snapshot_after_id == Snapshot.id)
        .where(Diff.instrument_id == instrument_id, Snapshot.user_id == user_id)
        .order_by(Diff.created_at.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def _significance_for_diff(session, diff_id: int) -> list[SignificanceScore]:
    stmt = select(SignificanceScore).where(SignificanceScore.diff_id == diff_id)
    return list(session.scalars(stmt))


def _rank_score(scores: list[SignificanceScore]) -> float:
    """A diff's overall attention-feed rank: the largest-magnitude
    significance score it triggered, or 0 if it triggered none ("no
    meaningful change")."""
    if not scores:
        return 0.0
    return max(abs(s.score) for s in scores)


# --- Instruments (catalog, for the "add to watchlist" search) ---


@router.get("/instruments")
def list_instruments():
    session = SessionLocal()
    try:
        instruments = session.scalars(select(Instrument)).all()
        return [
            {"id": i.id, "type": i.type, "exchange": i.exchange, "sector": i.sector}
            for i in instruments
        ]
    finally:
        session.close()


# --- Watchlist management (Feature: watchlist itself, underlies everything) ---


class AddWatchlistItem(BaseModel):
    instrument_id: str


@router.get("/watchlist")
def get_watchlist():
    session = SessionLocal()
    try:
        now = _now_ist()
        stmt = select(WatchlistItem).where(WatchlistItem.user_id == DEMO_USER_ID)
        items = session.scalars(stmt).all()
        result = []
        for item in items:
            instrument = session.get(Instrument, item.instrument_id)
            snapshot = _latest_snapshot(session, item.instrument_id, DEMO_USER_ID)
            diff = _latest_diff(session, item.instrument_id, DEMO_USER_ID)
            result.append(
                {
                    "instrument_id": item.instrument_id,
                    "type": instrument.type if instrument else None,
                    "sector": instrument.sector if instrument else None,
                    "price": snapshot.price if snapshot else None,
                    # Recomputed at request time (Phase 7 requirement 3:
                    # stale-vs-closed) rather than returning the raw
                    # ingestion-time Snapshot.status — a snapshot that was
                    # "live" when captured can still go stale just from
                    # time passing, with no new ingestion event.
                    "status": compute_display_status(snapshot.captured_at, now) if snapshot else None,
                    "last_checked_at": snapshot.captured_at.isoformat() if snapshot else None,
                    "price_delta_pct": diff.price_delta_pct if diff else None,
                }
            )
        return result
    finally:
        session.close()


@router.post("/watchlist", status_code=201)
def add_to_watchlist(payload: AddWatchlistItem):
    session = SessionLocal()
    try:
        if session.get(Instrument, payload.instrument_id) is None:
            raise HTTPException(status_code=404, detail=f"Unknown instrument {payload.instrument_id!r}")
        existing = session.scalar(
            select(WatchlistItem).where(
                WatchlistItem.user_id == DEMO_USER_ID,
                WatchlistItem.instrument_id == payload.instrument_id,
            )
        )
        if existing is None:
            session.add(WatchlistItem(user_id=DEMO_USER_ID, instrument_id=payload.instrument_id))
            session.commit()
        return {"instrument_id": payload.instrument_id}
    finally:
        session.close()


@router.delete("/watchlist/{instrument_id}", status_code=204)
def remove_from_watchlist(instrument_id: str):
    session = SessionLocal()
    try:
        stmt = select(WatchlistItem).where(
            WatchlistItem.user_id == DEMO_USER_ID, WatchlistItem.instrument_id == instrument_id
        )
        for item in session.scalars(stmt):
            session.delete(item)
        session.commit()
        return None
    finally:
        session.close()


# --- Significance-ranked attention feed (Feature 3) ---


@router.get("/attention-feed")
def get_attention_feed():
    session = SessionLocal()
    try:
        now = _now_ist()
        watched = session.scalars(
            select(WatchlistItem).where(WatchlistItem.user_id == DEMO_USER_ID)
        ).all()

        ranked = []
        for item in watched:
            instrument = session.get(Instrument, item.instrument_id)
            diff = _latest_diff(session, item.instrument_id, DEMO_USER_ID)
            if diff is None:
                continue  # nothing to rank yet — no diff has ever been computed for this instrument
            scores = _significance_for_diff(session, diff.id)
            snapshot = session.get(Snapshot, diff.snapshot_after_id)
            ranked.append(
                {
                    "instrument_id": item.instrument_id,
                    "sector": instrument.sector if instrument else None,
                    "price_delta_pct": diff.price_delta_pct,
                    "after_price": diff.after_price,
                    "rank_score": _rank_score(scores),
                    "significance": [
                        {"category": s.category, "detail": s.detail, "score": s.score} for s in scores
                    ],
                    "status": compute_display_status(snapshot.captured_at, now) if snapshot else None,
                    "last_checked_at": snapshot.captured_at.isoformat() if snapshot else None,
                }
            )

        ranked.sort(key=lambda entry: entry["rank_score"], reverse=True)
        return {
            "top": ranked[:ATTENTION_FEED_TOP_N],
            "collapsed": ranked[ATTENTION_FEED_TOP_N:],
        }
    finally:
        session.close()


# --- Per-instrument digest view (Features 1, 2, 5's generation step) ---


@router.get("/instruments/{instrument_id}/digest")
def get_digest(instrument_id: str):
    session = SessionLocal()
    try:
        now = _now_ist()
        instrument = session.get(Instrument, instrument_id)
        if instrument is None:
            raise HTTPException(status_code=404, detail=f"Unknown instrument {instrument_id!r}")

        snapshot = _latest_snapshot(session, instrument_id, DEMO_USER_ID)
        diff = _latest_diff(session, instrument_id, DEMO_USER_ID)

        # Phase 7 requirement 2: NSE/BSE disagreement. Only equities/ETFs
        # have a dual-exchange counterpart at all; only surfaced when both
        # sides actually have a snapshot for this user to compare.
        exchange_reconciliation = None
        counterpart_id = _exchange_counterpart(instrument_id)
        if counterpart_id is not None:
            counterpart_snapshot = _latest_snapshot(session, counterpart_id, DEMO_USER_ID)
            if snapshot is not None and counterpart_snapshot is not None:
                nse_price, bse_price = (
                    (snapshot.price, counterpart_snapshot.price)
                    if instrument_id.endswith(".NS")
                    else (counterpart_snapshot.price, snapshot.price)
                )
                result = reconcile_exchange_prices(nse_price, bse_price)
                exchange_reconciliation = {
                    "chosen_exchange": result.chosen_exchange,
                    "chosen_price": result.chosen_price,
                    "nse_price": result.nse_price,
                    "bse_price": result.bse_price,
                    "discrepancy_pct": result.discrepancy_pct,
                    "disagreement": result.disagreement,
                }

        if diff is None:
            return {
                "instrument_id": instrument_id,
                "narrative": "No prior snapshot to compare against yet — check back after this "
                "instrument has been tracked for at least one more ingestion cycle.",
                "price": snapshot.price if snapshot else None,
                "price_delta_pct": None,
                "volume_delta_pct": None,
                "ratio_deltas": {},
                "significance": [],
                "news": [],
                "status": compute_display_status(snapshot.captured_at, now) if snapshot else None,
                "last_checked_at": snapshot.captured_at.isoformat() if snapshot else None,
                "exchange_reconciliation": exchange_reconciliation,
            }

        scores = _significance_for_diff(session, diff.id)
        top_score = max(scores, key=lambda s: abs(s.score)) if scores else SignificanceScore(
            diff_id=diff.id, score=0.0, category="none", detail="no significance category fired"
        )

        before_snapshot = session.get(Snapshot, diff.snapshot_before_id)
        since = before_snapshot.captured_at if before_snapshot else datetime.utcnow() - timedelta(days=7)
        until = snapshot.captured_at if snapshot else datetime.utcnow()
        news_items = get_relevant_news(session, instrument_id, since, until)

        narrative = generate_digest(diff, top_score, news_items)

        return {
            "instrument_id": instrument_id,
            "narrative": narrative,
            "price": diff.after_price,
            "price_delta_pct": diff.price_delta_pct,
            "volume_delta_pct": diff.volume_delta_pct,
            "ratio_deltas": diff.ratio_deltas,
            "significance": [{"category": s.category, "detail": s.detail, "score": s.score} for s in scores],
            # title + source + link + our own paraphrased narrative only —
            # never full article text/snippets, for copyright reasons
            # (docs/plan.md §6 generation step; NewsItem doesn't even
            # persist a snippet, see app/models.py).
            "news": [
                {"title": n.title, "source": n.source, "url": n.url, "published_at": n.published_at.isoformat()}
                for n in news_items
            ],
            "status": compute_display_status(snapshot.captured_at, now) if snapshot else None,
            "last_checked_at": snapshot.captured_at.isoformat() if snapshot else None,
            "exchange_reconciliation": exchange_reconciliation,
        }
    finally:
        session.close()


# --- Adaptive alerts (Feature 4) ---


class CreateAlert(BaseModel):
    instrument_id: str
    target_price: float | None = None
    notify_on_significant_change: bool = False


@router.get("/alerts")
def list_alerts():
    session = SessionLocal()
    try:
        stmt = select(Alert).where(Alert.user_id == DEMO_USER_ID)
        return [
            {
                "id": a.id,
                "instrument_id": a.instrument_id,
                "condition": a.condition,
                "status": a.status,
            }
            for a in session.scalars(stmt)
        ]
    finally:
        session.close()


@router.post("/alerts", status_code=201)
def create_alert(payload: CreateAlert):
    if payload.target_price is None and not payload.notify_on_significant_change:
        raise HTTPException(
            status_code=400,
            detail="Set a target_price, enable notify_on_significant_change, or both.",
        )
    session = SessionLocal()
    try:
        if session.get(Instrument, payload.instrument_id) is None:
            raise HTTPException(status_code=404, detail=f"Unknown instrument {payload.instrument_id!r}")
        # "notify on significant change" reuses app/significance.py's own
        # flags directly (docs/plan.md §2, Feature 4: "reusing the
        # significance score rather than a separate alerting system") —
        # there's no separate numeric threshold to store for it.
        condition = {
            "target_price": payload.target_price,
            "notify_on_significant_change": payload.notify_on_significant_change,
        }
        alert = Alert(user_id=DEMO_USER_ID, instrument_id=payload.instrument_id, condition=condition)
        session.add(alert)
        session.commit()
        return {"id": alert.id, "instrument_id": alert.instrument_id, "condition": alert.condition}
    finally:
        session.close()


@router.delete("/alerts/{alert_id}", status_code=204)
def delete_alert(alert_id: int):
    session = SessionLocal()
    try:
        alert = session.get(Alert, alert_id)
        if alert is not None and alert.user_id == DEMO_USER_ID:
            session.delete(alert)
            session.commit()
        return None
    finally:
        session.close()


# --- Subscription-window tracker (Feature 6) ---


@router.get("/subscription-windows")
def list_subscription_windows():
    session = SessionLocal()
    try:
        stmt = select(SubscriptionWindow)
        result = []
        for window in session.scalars(stmt):
            instrument = session.get(Instrument, window.instrument_id)
            result.append(
                {
                    "instrument_id": window.instrument_id,
                    "type": instrument.type if instrument else None,
                    "status": window.status,
                    "last_changed_at": window.last_changed_at.isoformat(),
                }
            )
        return result
    finally:
        session.close()
