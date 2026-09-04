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
network/credentials, or the real Gemini embeddings endpoint. The Gemini
path uses Vertex AI in production — set `GOOGLE_CLOUD_PROJECT` (the same
GCP project already backing Cloud Run/Cloud SQL) and it authenticates via
that service's own credentials, no separate key to manage; `GEMINI_API_KEY`
is also supported as a local/non-GCP fallback. Every test in this project
runs against the mock provider — the Gemini path hasn't been exercised
against a live key or a live GCP project.

Narrative generation is the same shape again: `NARRATIVE_PROVIDER=template|gemini`
(default `template`). The template summary is a deterministic, no-network
sentence built from the diff + significance category alone (no news
dependency) — not a lesser fallback, it's exactly what a Gemini failure,
timeout, or an advice-like slip past the prompt should fall back to "so a
live demo never breaks." Every test runs against it (`watch-me-groww`'s GCP
billing account is currently closed pending a bank issue, so the live
Gemini path is implemented but still unverified — same status as
embeddings). If Gemini output ever contains buy/sell/hold/invest-style
language, it's discarded in favor of the template — a hard backstop on top
of the prompt, not the only line of defense (see `app/narrative.py`).

**Frontend** (Next.js App Router, TypeScript, Tailwind):

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000`. Start the backend first (above) — the
frontend talks to it at `http://localhost:8000` by default
(`NEXT_PUBLIC_API_BASE_URL` to override). On backend startup, `app/seed.py`
seeds the instrument catalog, a single demo user, and two placeholder
subscription-window rows, so the UI has something to show immediately —
add an instrument to the watchlist, then run
`python -m app.ingestion.run_ingestion` (more than once, so there's a prior
snapshot to diff against) to see the attention feed and digest populate.

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
  with `python -m app.ingestion.run_ingestion`. `app/narrative.py`'s
  `generate_digest(diff, significance, news_items)` turns an already-scored
  Diff plus its retrieved news into the 2-3 sentence summary Feature 1
  shows, at view-time rather than ingestion-time (nothing calls it yet —
  that's what Phase 6's route handlers actually call now); and
  `app/api.py` — the REST layer the frontend talks to (watchlist, the
  significance-ranked attention feed, per-instrument digest, alerts,
  subscription windows), plus `app/seed.py` seeding the instrument catalog
  and a single demo user on startup (no auth system exists yet).
- `frontend/` — Next.js App Router UI for all five screens (attention
  feed, per-instrument digest, watchlist management, alert setup,
  subscription tracker), styled from a Groww design system exported via
  Claude Design (`components/ds/` — Avatar, Badge, Button, Chip, Switch —
  ported from that export's component source; `app/design-tokens.css`
  copied from its color/spacing/typography token files). The export's
  `InstrumentDigest` screen included literal "Buy"/"Sell" action buttons
  (`--accent-buy`/`--accent-sell` tokens) — dropped per
  `docs/SOURCE_OF_TRUTH.md`'s ban on order-execution/buy-sell language,
  replaced with "Add/remove watchlist" and "Set alert" in the same button
  slots, styled with the same `Button` component minus those two variants.
- `docs/` — `plan.md` (product/technical plan) and `SOURCE_OF_TRUTH.md`
  (hard constraints).

## Status

Through Phase 6: the full stack is wired end-to-end — data model, diff
engine, rule-based significance scoring, batch ingestion (price + news),
news retrieval, narrative generation, a REST API, and a styled frontend for
all five screens, responsive down to mobile. Backend logic remains
unit-tested (corporate-action exclusion, an end-to-end ingestion run
against MockProvider with zero real API calls, retrieval dedup/ranking,
narrative advice-language backstop); the frontend has been verified by
running both dev servers and checking each screen in the browser at both
desktop and mobile widths, not by an automated test suite. No auth system
yet (a single seeded demo user stands in for it) — see `docs/plan.md` §7
for the phase sequence.
