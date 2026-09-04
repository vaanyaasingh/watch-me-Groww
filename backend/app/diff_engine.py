"""Pure diff computation between two Snapshots of the same instrument.

No I/O, no DB access, no side effects — this only builds an (unpersisted)
Diff object; callers decide whether and when to add it to a session. This
is the primitive Feature 1 ("Since You Last Checked") and everything
downstream (significance scoring, the attention feed, adaptive alerts)
consumes.
"""

from app.models import Diff, Snapshot


def compute_diff(before: Snapshot, after: Snapshot) -> Diff:
    if before.instrument_id != after.instrument_id:
        raise ValueError(
            f"cannot diff snapshots of different instruments: "
            f"{before.instrument_id!r} vs {after.instrument_id!r}"
        )

    price_delta_pct = (after.price - before.price) / before.price

    volume_delta_pct = None
    if before.volume is not None and after.volume is not None and before.volume != 0:
        volume_delta_pct = (after.volume - before.volume) / before.volume

    # Only ratios present (by key) on both snapshots and comparable can be
    # diffed — a ratio that appears/disappears between snapshots (e.g. a
    # provider adding a new field) is silently skipped rather than raising.
    ratio_deltas: dict[str, float] = {}
    before_ratios = before.ratios or {}
    after_ratios = after.ratios or {}
    for key in before_ratios.keys() & after_ratios.keys():
        b, a = before_ratios[key], after_ratios[key]
        if isinstance(b, (int, float)) and isinstance(a, (int, float)) and b:
            ratio_deltas[key] = (a - b) / b

    return Diff(
        instrument_id=before.instrument_id,
        snapshot_before_id=before.id,
        snapshot_after_id=after.id,
        before_price=before.price,
        after_price=after.price,
        price_delta_pct=price_delta_pct,
        before_volume=before.volume,
        after_volume=after.volume,
        volume_delta_pct=volume_delta_pct,
        ratio_deltas=ratio_deltas,
    )
