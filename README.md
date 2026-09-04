# Smart Market Watchlist

Groww CODE 2026 submission. Existing watchlists show every instrument with
equal weight and no diffing or ranking — the gap isn't more data, it's
triage. This project is a change-detection and attention-ranking layer on
top of a watchlist: it snapshots what you're tracking, diffs it against what
you last saw, scores those diffs with rule-based significance rules, and
surfaces only what actually deserves attention. See
[`docs/plan.md`](docs/plan.md) for the full product/technical plan and
[`docs/SOURCE_OF_TRUTH.md`](docs/SOURCE_OF_TRUTH.md) for the non-negotiable
constraints every phase of this build follows (no investment advice, no
order execution, significance scoring stays rule-based, etc.).

## The `MarketDataProvider` abstraction

All external market data (equity/ETF quotes and history, news, mutual fund
NAV) is read through one interface, [`MarketDataProvider`](backend/app/providers/base.py),
instead of route handlers or jobs calling yfinance/AMFI/Google News
directly. Two things fall out of that:

1. **Swappable sources.** Phase 1 adds real providers (yfinance, AMFI) and a
   **mock provider** behind the same interface. The mock provider returns
   deterministic fixture data, so anyone running or judging this project can
   see every feature working end-to-end without live API keys or network
   access — set one config value to switch between mock and real data.
2. **A single seam for external I/O.** If a data source changes or breaks,
   only its provider implementation changes; the diff engine, significance
   scoring, and UI never know the difference.

This phase only defines the interface (`get_quote`, `get_historical`,
`get_news`, `get_fund_nav`) and its return types — no implementations yet.

## Running locally

Both are scaffolds for now — no business logic, database models, or routes
beyond a health check exist yet.

**Backend** (Python 3.11+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/health`. Alembic is wired up for migrations
(`alembic upgrade head`) but there are no models/revisions yet — that lands
in Phase 2.

**Frontend** (Next.js App Router, TypeScript, Tailwind):

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` for a placeholder page.

## Layout

- `backend/` — FastAPI service (`app/main.py`), SQLAlchemy + Alembic
  scaffold (`app/db.py`, `alembic/`), and the `MarketDataProvider` interface
  (`app/providers/base.py`).
- `frontend/` — Next.js app (watchlist UI, digest views, alerts).
- `docs/` — `plan.md` (product/technical plan) and `SOURCE_OF_TRUTH.md`
  (hard constraints).

## Status

Phase 0: monorepo scaffold + `MarketDataProvider` interface. No concrete
providers, data model, or UI logic yet — see `docs/plan.md` §7 for the phase
sequence.
