# Smart Market Watchlist

Groww CODE 2026 submission — a change-detection and attention-ranking layer on
top of a watchlist, not another price ticker.

See [`docs/plan.md`](docs/plan.md) for the full product/technical plan and
[`docs/SOURCE_OF_TRUTH.md`](docs/SOURCE_OF_TRUTH.md) for the non-negotiable
constraints every phase of this build follows.

## Layout

- `backend/` — FastAPI service. External data access goes through the
  `MarketDataProvider` interface (`backend/app/providers/base.py`); no route
  handler talks to yfinance/AMFI/Gemini directly.
- `frontend/` — Next.js app (watchlist UI, digest views, alerts).

## Status

Phase 0: monorepo scaffold + `MarketDataProvider` interface. No concrete
providers, data model, or UI logic yet — see `docs/plan.md` §7 for the phase
sequence.
