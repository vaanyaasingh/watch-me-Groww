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

`YFinanceProvider.get_quote()` also throttles: yfinance is unofficial and
rate-limit-sensitive, so repeated calls for the same ticker within 60
seconds are served from a small in-process cache rather than re-fetched
(`app/providers/yfinance_provider.py`) — a plain dict rather than the
Postgres-table/Redis this project's own tech-stack notes once considered,
since yfinance's own data is itself typically 15+ minutes delayed and a
second moving part wasn't worth it for what this actually needed to guard
against (several near-simultaneous requests for the same instrument, not
long-term freshness).

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
is also supported as a local/non-GCP fallback. Automated tests run against
the mock provider; the live Vertex AI path has been verified manually
end-to-end (`GOOGLE_CLOUD_PROJECT=watch-me-groww EMBEDDING_PROVIDER=gemini`)
through the real `/api/instruments/{id}/digest` endpoint, not just an
isolated call.

Narrative generation is the same shape again: `NARRATIVE_PROVIDER=template|gemini`
(default `template`). The template summary is a deterministic, no-network
sentence built from the diff + significance category alone (no news
dependency) — not a lesser fallback, it's exactly what a Gemini failure,
timeout, or an advice-like slip past the prompt should fall back to "so a
live demo never breaks." Automated tests run against it; the live Gemini
path has also been verified manually end-to-end and correctly produces
factual, advice-free narratives, including the no-news case. If Gemini
output ever contains buy/sell/hold/invest-style language, it's discarded
in favor of the template — a hard backstop on top
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
subscription-window rows, so the UI has something to show immediately.

To see the attention feed/digest actually populate with a real "since you
last checked" story, add an instrument to the watchlist and call
`POST /api/admin/seed-demo-scenario` (see `app/demo_seed.py`) rather than
running `python -m app.ingestion.run_ingestion` by hand more than once —
`MockProvider.get_quote()` is a fixed fixture value (the same price on
every call, by design, so tests stay deterministic), so two manual
ingestion runs always diff a price against itself and show a flat 0.00%
change, never a populated feed. `seed_demo_scenario()` instead diffs
against a real, different point from the instrument's own historical
series, which is what actually produces a real, scoreable price move.

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
  (13 equities across 8 sectors, 2 ETFs, 2 MFs — `backend/fixtures/sample_market_data.json`)
  and a fixed system-anchor user on startup. `app/auth.py` verifies the
  Firebase ID token every personal route requires (`Depends(get_current_user_id)`)
  using `google-auth`'s `verify_firebase_token` — no service-account key or
  Application Default Credentials needed, just Firebase's public certs, so
  it works identically whether this runs on GCP or (as deployed) Render.
  It resolves the token to this app's own `User` row by `firebase_uid`,
  creating one on a person's first authenticated call — there's no
  separate signup endpoint, Firebase already owns account creation on the
  frontend. Reference instruments (NIFTY/SENSEX/USD-INR) stay anchored to
  one fixed system user regardless of who's logged in, since
  `/api/market-overview` isn't personal to anybody. Edge-case
  hardening lives here too: `app/staleness.py`'s `compute_display_status()`
  recomputes "live"/"stale"/"market_closed" at request time (a snapshot can
  go stale from time passing alone, with no new ingestion event, so this
  can't be a value fixed at ingestion time) and is wired into the
  watchlist, attention-feed, and digest responses (`last_checked_at` +
  `status`); `app/reconciliation.py`'s `reconcile_exchange_prices()`
  resolves NSE/BSE disagreement (NSE wins — it carries the large majority
  of India's equity liquidity — and the discrepancy is always surfaced in
  the digest response's `exchange_reconciliation` field, never silently
  dropped) and is wired in whenever both a `.NS` and `.BO` listing exist
  for the same company. `app/demo_seed.py`'s `seed_demo_scenario()`
  (triggered via `POST /api/admin/seed-demo-scenario`) seeds a realistic
  "last checked N days ago" snapshot for a handful of instruments from
  their own historical prices, then runs the real diff/significance/news
  pipeline against "today" — including real Google News RSS retrieval —
  so the digest/attention-feed views have a genuine story to show without
  a judge needing to run the ingestion job by hand first. Two features
  that used to be UI-only now have a real mechanism behind them, both
  wired into `app/ingestion/run_ingestion.py`'s per-instrument loop:
  `app/alerts.py`'s `evaluate_alerts()` (Feature 4) checks every active
  Alert against the Diff/SignificanceScore just computed for that same
  (user, instrument) pair and flips it to `"triggered"` when its condition
  is met — before this, an alert could be created and nothing would ever
  happen no matter how the price moved. Delivery (push/email) stays out of
  scope deliberately: Firebase Cloud Messaging and SMTP both need real
  infrastructure (a service worker + VAPID keys, or a provider account)
  this project doesn't have, so `status` is a checkable fact
  (`GET /api/alerts`) rather than something pushed at anyone.
  `app/subscription_tracker.py` (Feature 6) replaces guesswork with a real,
  checked constraint: no free structured feed for RBI-LRS-driven MF
  subscription pauses exists (AMFI's NAVAll feed carries no such field,
  and none was found elsewhere), but AMCs announce them as ordinary
  headlines, so it reuses the same `GoogleNewsRSSProvider` the price-side
  news pipeline already depends on — searched by the fund's real AMFI
  scheme name (now returned by `FundNav.scheme_name`, added to both
  `MockProvider` and `AMFIProvider`), classified by a small rule-based
  regex, never an LLM call (the same "rule-based, auditable" bar
  `docs/SOURCE_OF_TRUTH.md` holds significance scoring to). Its honesty
  constraint: no matching headline means the existing status is left
  untouched, never guessed — a domestic fund with no real subscription
  news correctly shows no change, which is why the two seeded schemes
  (both domestic) don't visibly flip in a demo even though the mechanism
  ran; verified instead against real, currently-live headlines about
  actual RBI-LRS-affected funds (PGIM India's international FoFs) during
  development. The matched headline itself is stored (`evidence`) and
  shown in the UI, so "why does it say this" is inspectable, not
  trust-me.
- `frontend/` — Next.js App Router UI for all five core screens (attention
  feed, per-instrument digest, watchlist management, alert setup,
  subscription tracker) plus a real Firebase-backed login/profile flow and a NIFTY 50/
  SENSEX/USD-INR market-overview strip, styled from a Groww design system
  exported via Claude Design (`components/ds/` — Avatar, Badge, Button,
  Chip, Switch — ported from that export's component source;
  `app/design-tokens.css` copied from its color/spacing/typography token
  files). The export's `InstrumentDigest` screen included literal
  "Buy"/"Sell" action buttons (`--accent-buy`/`--accent-sell` tokens) —
  dropped per `docs/SOURCE_OF_TRUTH.md`'s ban on order-execution/buy-sell
  language, replaced with "Add/remove watchlist" and "Set alert" in the
  same button slots, styled with the same `Button` component minus those
  two variants — the same substitution applies to a second design pass
  below. A dark-mode toggle (`components/DarkModeToggle.tsx`, persisted to
  `localStorage`) flips every surface in the app at once by redefining the
  same token names under `:root[data-theme="dark"]` rather than branching
  per component.

  The current visual direction ("Pulsewatch" — a warm cream/amber/
  terracotta/olive editorial palette, Sora throughout) replaced an earlier
  dark frosted-glass theme, implemented from a Claude Design mockup
  (`Smart Market Watchlist.dc.html`, project `3d1e8be7-...`) rather than
  from scratch. That mockup's Instrument Digest screen again had literal
  "Buy"/"Sell" buttons — dropped the same way as the original export's,
  for the same `docs/SOURCE_OF_TRUTH.md` reason. It also has no dark-mode
  variant of its own; the dark-mode tokens in `design-tokens.css` are this
  project's own construction in the same palette, built so the toggle
  already shipped doesn't regress. `components/ds/glass.ts` (name kept
  from the earlier translucent treatment; every consumer already imports
  it) now renders solid white/dark "paper" cards with a soft drop shadow
  instead of blur — the whole point of this direction is an opaque,
  paper-like surface, not translucency.
  `components/ds/Freshness.tsx` surfaces the staleness/last-checked data
  in every screen that shows a price. `/login` and `/profile`
  (`lib/auth.ts`, `lib/firebase.ts`, `components/AuthGate.tsx`) are real
  Firebase Authentication (email/password) — every request `lib/api.ts`
  makes attaches the signed-in user's ID token as `Authorization: Bearer
  <token>`, verified server-side by `backend/app/auth.py`, not just a
  client-side gate. `AuthGate` subscribes to Firebase's auth-state
  listener rather than checking it once at mount, since a signed-in
  session restores asynchronously on page load and a one-off check could
  redirect someone who's actually still logged in.
  `components/ds/Sparkline.tsx` is a small inline SVG trend line (no
  charting library — a ~30-point polyline doesn't need one) reading real
  daily closes from a new `GET /api/instruments/{id}/sparkline` endpoint,
  which calls the same `MarketDataProvider.get_historical()` the
  significance engine already uses — a visual, not a second data source.
  It appears on the market-overview cards, attention-feed rows, and the
  digest page's price header. That pass also fixed a real dark-mode
  contrast bug (`Badge`'s "medium" attention/status colors were a
  hardcoded light-only hex, invisible against a dark card — now a
  `--amber-50` token like every other status color) and gave list rows
  (watchlist/feed), hero metrics (market overview), and news items three
  visually distinct treatments instead of one repeated card style.
- `docs/` — `plan.md` (product/technical plan) and `SOURCE_OF_TRUTH.md`
  (hard constraints).

## Deploying

Frontend on [Vercel](https://vercel.com) (auto-detects Next.js — import the
repo, set its root directory to `frontend`), backend on
[Render](https://render.com) (`render.yaml` at the repo root is a Blueprint
— New -> Blueprint -> pick this repo), database on
[Neon](https://neon.tech) (free Postgres).

1. **Firebase** (console.firebase.google.com): add Firebase to the
   existing `watch-me-groww` GCP project (or create a project), enable
   **Authentication -> Sign-in method -> Email/Password**, then add a Web
   App and copy its config into `frontend/.env.local`
   (see `frontend/.env.example`) and into Vercel's project env vars.
2. **Neon**: create a project, copy the Postgres connection string.
3. **Render**: New -> Blueprint -> this repo (reads `render.yaml`). When
   prompted, set `DATABASE_URL` (from Neon), `GEMINI_API_KEY` (from
   [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — Render
   isn't a GCP host, so this replaces the Vertex AI/ADC path used locally),
   and `FIREBASE_PROJECT_ID` (the Firebase project id from step 1).
4. **Vercel**: import the repo, root directory `frontend`, add the
   `NEXT_PUBLIC_FIREBASE_*` vars from step 1 plus
   `NEXT_PUBLIC_API_BASE_URL` (the Render URL from step 3).
5. Back on Render, set `ALLOWED_ORIGINS` to the Vercel URL from step 4 (CORS,
   see `app/main.py`) and redeploy.

## Status

Through Phase 7 plus a UI/hosting pass: the full stack is wired
end-to-end — data model, diff engine, rule-based significance scoring,
batch ingestion (price + news), news retrieval, narrative generation, a
REST API, a styled frontend for all five screens (responsive down to
mobile), and the edge-case pass Feature 5 (Data Integrity & Corporate
Action Layer) actually asks for: market-hours/holiday awareness, NSE/BSE
reconciliation, stale-vs-closed detection (distinct from "market closed",
computed at request time), corporate-action exclusion generalized across
both bonus issues and stock splits, and per-source news-pipeline failure
isolation (one source failing never discards another source's results for
the same instrument, nor aborts other instruments in the run). Real
Firebase Authentication replaces the earlier mock login, and Features 4
and 6 (Adaptive Alerts, Subscription-Window Tracker) moved from UI-only to
a real evaluated/news-derived mechanism (see the `frontend/` and
`app/api.py` layout entries above). 97 backend tests pass, including an
API-level test (via FastAPI's `TestClient`) proving the NSE/BSE
disagreement actually reaches the HTTP response, not just the pure
reconciliation function; a dedicated auth test suite covering missing/
invalid tokens and first-call user creation; and dedicated suites for
alert evaluation and subscription-window classification, the latter
verified against real, currently-live news headlines during development,
not just synthetic fixtures. The frontend has been verified by running
both dev servers and checking each screen in the browser at desktop and
mobile widths, not by an automated test suite — see `docs/plan.md` §7 for
the phase sequence.
