"""NSE/BSE price reconciliation (docs/plan.md §2, Feature 5: Data
Integrity & Corporate Action Layer — "NSE/BSE reconciliation").

NSE is the source of truth when the two disagree: NSE carries the large
majority of India's equity trading volume for almost every stock listed on
both exchanges (BSE's volume is a small fraction of NSE's for actively
traded names), so its quote is the more reliable "current" price. This is
a fixed rule of thumb, not a per-instrument liquidity measurement — if a
specific instrument were ever known to trade more on BSE, this constant
would need to become a real lookup instead of a hardcoded default.
"""

from dataclasses import dataclass

SOURCE_OF_TRUTH_EXCHANGE = "NSE"

# Beyond this fractional difference, the two exchanges' prices are treated
# as a genuine disagreement worth surfacing rather than quote-timing noise —
# near-simultaneous quotes from two independent feeds commonly differ by a
# few basis points even when both are healthy.
DISAGREEMENT_TOLERANCE_PCT = 0.005


@dataclass(frozen=True)
class ReconciliationResult:
    chosen_price: float
    chosen_exchange: str
    nse_price: float
    bse_price: float
    discrepancy_pct: float
    disagreement: bool


def reconcile_exchange_prices(nse_price: float, bse_price: float) -> ReconciliationResult:
    """Never silently picks one price and hides the other — the caller
    (app/api.py) surfaces `discrepancy_pct`/`disagreement` in the response
    even when NSE's price is used, so a real disagreement is visible
    rather than quietly swallowed."""
    discrepancy_pct = abs(nse_price - bse_price) / max(nse_price, bse_price)
    return ReconciliationResult(
        chosen_price=nse_price,
        chosen_exchange=SOURCE_OF_TRUTH_EXCHANGE,
        nse_price=nse_price,
        bse_price=bse_price,
        discrepancy_pct=discrepancy_pct,
        disagreement=discrepancy_pct > DISAGREEMENT_TOLERANCE_PCT,
    )
