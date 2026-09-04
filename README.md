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

1. **Swappable sources.** Four implementations share the interface:
   `MockProvider` (reads `backend/fixtures/sample_market_data.json`, zero
   network/credentials), `YFinanceProvider` (equities/ETFs), `AMFIProvider`
   (mutual fund NAV), and `LiveMarketDataProvider` (composes the previous
   two, routed by instrument_id shape — a numeric id is an AMFI scheme code,
   everything else is a yfinance ticker). Pick one with a single env var:
   `MARKET_DATA_PROVIDER=mock|live|yfinance|amfi` (default `mock`), read in
   exactly one place (`app/providers/config.py`). The mock provider is the
   default specifically so anyone running or judging this project sees
   every feature working end-to-end without live API keys or network
   access.
2. **A single seam for external I/O.** If a data source changes or breaks,
   only its provider implementation changes; the diff engine, significance
   scoring, and UI never know the difference.

## Running locally

**Backend** (Python 3.11+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/health`. Run the test suite with
`python -m pytest tests/` — provider tests that need real network access
(live yfinance/AMFI calls) skip themselves automatically when none is
available; every other test, including the full significance-scoring and
news-retrieval suites, runs offline.

News embeddings work the same way: `EMBEDDING_PROVIDER=mock|gemini`
(default `mock`) picks a deterministic, hash-derived embedding with zero
network/credentials, or the real Gemini embeddings endpoint (needs
`GEMINI_API_KEY`). Every test in this project runs against the mock one —
the Gemini path hasn't been exercised against a live key.

**Frontend** (Next.js App Router, TypeScript, Tailwind):

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` for a placeholder page.

## Layout

- `backend/` — FastAPI service (`app/main.py`); the `MarketDataProvider`
  interface and its four implementations (`app/providers/`); SQLAlchemy
  models for every entity in `docs/plan.md` §5 (`app/models.py`) with
  Alembic migrations (`alembic/`); the pure diff engine
  (`app/diff_engine.py`); and rule-based significance scoring
  (`app/significance.py`) — z-scores, threshold crossings, and discrete
  events, with no ML model and no LLM call anywhere in the decision of
  what's "significant"; and the batch
  ingestion job (`app/ingestion/run_ingestion.py`) — one MarketDataProvider
  call per distinct watched instrument per run (not per user), a per-user
  Diff against each user's own last snapshot, and NSE trading-hours/holiday
  awareness (`app/market_calendar.py` + `app/market_calendar_data/`) so a
  closed market gets marked, not fetched, and never mistaken for a stuck
  feed. The same job also ingests news (`app/embeddings.py`,
  `app/providers/google_news_rss.py`) — yfinance `.news` plus company- and
  sector-bounded Google News RSS queries, deduplicated by URL and embedded
  into `NewsItem` (`embedding` stored as a native pgvector column on
  Postgres, a JSON float list on SQLite — see `app/vector_type.py`).
  `app/news_retrieval.py`'s `get_relevant_news()` reads that table back:
  filters by time window and instrument/sector, clusters near-duplicates by
  cosine similarity, and ranks by semantic relevance plus correlation with
  a day the significance engine already flagged — reusing that table
  rather than inventing a second importance signal. Run ingestion locally
  with `python -m app.ingestion.run_ingestion`.
- `frontend/` — Next.js app (watchlist UI, digest views, alerts).
- `docs/` — `plan.md` (product/technical plan) and `SOURCE_OF_TRUTH.md`
  (hard constraints).

## Status

Through Phase 4: data model, diff engine, rule-based significance scoring,
batch ingestion (price + news), and news retrieval are in place and
unit-tested (including a corporate-action exclusion case, an end-to-end
ingestion run against MockProvider with zero real API calls, and a
retrieval test with a hand-crafted fixture proving dedup, significance-
correlated ranking, and the time-window/instrument filters all work
together). No route handlers, narrative generation, or UI logic yet — see
`docs/plan.md` §7 for the phase sequence.
