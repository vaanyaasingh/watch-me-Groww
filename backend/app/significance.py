"""Rule-based significance scoring — no ML model, no LLM call, ever (see
docs/SOURCE_OF_TRUTH.md, "Significance scoring"). Each of the four
categories from docs/plan.md §3 is an independent, pure function of numeric
inputs; score_significance() runs all four and returns one SignificanceScore
per category that actually fired.
"""

import statistics
from datetime import date

from app.models import Diff, Instrument, SignificanceScore, Snapshot
from app.providers.base import PricePoint

# --- Tunable thresholds, named and documented so a reviewer can see exactly
# what "meaningful" means without reading the formulas. ---

# |z| >= 2 is the conventional cutoff for "outside ~95% of normal days"
# under a roughly-normal daily-return distribution.
STATISTICAL_Z_THRESHOLD = 2.0
MIN_DAILY_RETURNS_FOR_STATISTICAL = 20

SMA_SHORT_WINDOW = 20
SMA_LONG_WINDOW = 50
FIFTY_TWO_WEEK_TRADING_DAYS = 252

# A same-day divergence from the sector's move of 1.5 percentage points or
# more is treated as "actually outperforming/underperforming", per the
# down-2%-vs-sector-down-3.5% example in docs/plan.md §3.
RELATIVE_DIVERGENCE_THRESHOLD = 0.015


def _corporate_action_between(
    instrument: Instrument, start: date, end: date
) -> dict | None:
    """A recorded split/bonus/dividend whose ex_date falls in (start, end]."""
    for action in instrument.corporate_action_history or []:
        ex_date = action["ex_date"]
        if isinstance(ex_date, str):
            ex_date = date.fromisoformat(ex_date)
        if start < ex_date <= end:
            return action
    return None


def _corporate_action_adjusted_return(
    diff: Diff, action: dict | None
) -> float:
    """The diff's return with any recorded corporate action's mechanical
    price jump undone, so a bonus/split is compared like-for-like instead of
    registering as a crash or spike (docs/plan.md §3: "Corporate-action price
    discontinuities are detected and excluded by design").

    `ratio` is defined as pre-action-price / post-action-price (e.g. 2.0 for
    a 1:1 bonus, which halves the price): multiplying the post-action price
    back up by `ratio` undoes the mechanical jump before computing a return.
    """
    if action is None or not action.get("ratio"):
        return diff.price_delta_pct
    adjusted_after_price = diff.after_price * action["ratio"]
    return (adjusted_after_price - diff.before_price) / diff.before_price


def _check_statistical_deviation(
    diff: Diff, historical: list[PricePoint], adjusted_return: float
) -> SignificanceScore | None:
    """z = (r_today - mean(r)) / stdev(r), where r is the trailing daily-
    return series computed from at least 20 days of historical closes.
    `r_today` is the corporate-action-adjusted return, not the raw diff, so
    a recorded split/bonus never shows up here (it's Category 4's job)."""
    closes = [bar.close for bar in historical]
    if len(closes) < MIN_DAILY_RETURNS_FOR_STATISTICAL + 1:
        return None
    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
    if len(returns) < MIN_DAILY_RETURNS_FOR_STATISTICAL:
        return None

    mean = statistics.mean(returns)
    stdev = statistics.stdev(returns)
    if stdev == 0:
        return None

    z = (adjusted_return - mean) / stdev
    if abs(z) < STATISTICAL_Z_THRESHOLD:
        return None
    return SignificanceScore(
        diff_id=diff.id,
        category="statistical",
        score=z,
        detail=f"z={z:.2f} vs trailing {len(returns)}-day daily-return distribution",
    )


def _check_threshold_crossing(
    diff: Diff, historical: list[PricePoint], action: dict | None
) -> SignificanceScore | None:
    """52-week high/low, and a 20-day/50-day SMA crossover.

    `historical` must cover strictly the days *before* this diff's after-
    snapshot (it must not include today's close) — today's only data point
    is diff.after_price. That contract is what lets the high/low check
    compare today against a baseline that doesn't already contain today.

    If a corporate action fired on this diff, the historical series mixes
    pre- and post-action price levels, which makes a high/low or SMA
    comparison meaningless without back-adjusting the whole series (that's
    Feature 5's job, Phase 7) — skip cleanly rather than emit a misleading
    flag.
    """
    if action is not None:
        return None
    closes = [bar.close for bar in historical]
    if not closes:
        return None

    window = closes[-FIFTY_TWO_WEEK_TRADING_DAYS:]
    prior_high, prior_low = max(window), min(window)
    if diff.after_price > prior_high:
        return SignificanceScore(
            diff_id=diff.id,
            category="threshold",
            score=(diff.after_price - prior_high) / prior_high,
            detail=f"new {len(window)}-day high ({diff.after_price} > {prior_high})",
        )
    if diff.after_price < prior_low:
        return SignificanceScore(
            diff_id=diff.id,
            category="threshold",
            score=(prior_low - diff.after_price) / prior_low,
            detail=f"new {len(window)}-day low ({diff.after_price} < {prior_low})",
        )

    if len(closes) >= SMA_LONG_WINDOW:
        def sma(values: list[float], window_size: int) -> float:
            return sum(values[-window_size:]) / window_size

        combined = closes + [diff.after_price]
        prev_short, prev_long = sma(closes, SMA_SHORT_WINDOW), sma(closes, SMA_LONG_WINDOW)
        curr_short, curr_long = sma(combined, SMA_SHORT_WINDOW), sma(combined, SMA_LONG_WINDOW)
        crossed_up = prev_short <= prev_long and curr_short > curr_long
        crossed_down = prev_short >= prev_long and curr_short < curr_long
        if crossed_up or crossed_down:
            return SignificanceScore(
                diff_id=diff.id,
                category="threshold",
                score=(curr_short - curr_long) / curr_long,
                detail=(
                    f"{SMA_SHORT_WINDOW}/{SMA_LONG_WINDOW}-day SMA "
                    f"{'bullish' if crossed_up else 'bearish'} crossover"
                ),
            )
    return None


def _check_relative_context(
    diff: Diff, adjusted_return: float, sector_historical: list[PricePoint] | None
) -> SignificanceScore | None:
    """Compares the instrument's (adjusted) same-day return to its sector's.

    Unlike instrument_historical, sector_historical must include today as
    its last close — there's no separate "sector diff" object to carry
    today's sector price the way diff.after_price carries the instrument's,
    so today's sector return is computed from the last two closes here.

    Resolving *which* sector index to pass in is not this module's job —
    that's a caller-side lookup from Instrument.sector, wired up wherever
    this is actually invoked (see Phase 2 summary, open question)."""
    if not sector_historical or len(sector_historical) < 2:
        return None
    sector_closes = [bar.close for bar in sector_historical]
    sector_return = (sector_closes[-1] - sector_closes[-2]) / sector_closes[-2]
    divergence = adjusted_return - sector_return
    if abs(divergence) < RELATIVE_DIVERGENCE_THRESHOLD:
        return None
    return SignificanceScore(
        diff_id=diff.id,
        category="relative",
        score=divergence,
        detail=f"instrument {adjusted_return:+.2%} vs sector {sector_return:+.2%}",
    )


def _check_discrete_event(
    diff: Diff, snapshot_after: Snapshot, action: dict | None
) -> SignificanceScore | None:
    """Corporate action, earnings date, or rating change on the snapshot.
    Earnings/rating fields are wired now so a later provider can populate
    them without another migration — today they're almost always None."""
    reasons = []
    if action is not None:
        reasons.append(f"corporate action: {action['action_type']} (ex-date {action['ex_date']})")
    if snapshot_after.earnings_date is not None:
        reasons.append(f"earnings date: {snapshot_after.earnings_date}")
    if snapshot_after.rating_change:
        reasons.append(f"rating change: {snapshot_after.rating_change}")
    if not reasons:
        return None
    return SignificanceScore(
        diff_id=diff.id, category="event", score=1.0, detail="; ".join(reasons)
    )


def score_significance(
    diff: Diff,
    instrument: Instrument,
    instrument_historical: list[PricePoint],
    snapshot_before: Snapshot,
    snapshot_after: Snapshot,
    sector_historical: list[PricePoint] | None = None,
) -> list[SignificanceScore]:
    """Run all four significance categories from docs/plan.md §3 against one
    Diff. Returns a SignificanceScore per category that fired — an empty
    list means nothing about this diff crossed any threshold.

    `instrument_historical` and `sector_historical` must both cover strictly
    the days *before* snapshot_after (they must not include the day this
    diff represents) — the diff itself (diff.after_price / adjusted_return)
    is the only "today" data point.
    """
    action = _corporate_action_between(
        instrument, snapshot_before.captured_at.date(), snapshot_after.captured_at.date()
    )
    adjusted_return = _corporate_action_adjusted_return(diff, action)

    candidates = [
        _check_statistical_deviation(diff, instrument_historical, adjusted_return),
        _check_threshold_crossing(diff, instrument_historical, action),
        _check_relative_context(diff, adjusted_return, sector_historical),
        _check_discrete_event(diff, snapshot_after, action),
    ]
    return [score for score in candidates if score is not None]
