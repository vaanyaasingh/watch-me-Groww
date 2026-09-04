# Smart Market Watchlist — Build Plan

Groww CODE 2026 Submission

---

## 1. Core Thesis

Groww's existing watchlist shows every instrument with equal weight and no diffing or ranking. The gap isn't more data, it's triage. This product is a change-detection and attention-ranking layer on top of a watchlist, not another price ticker.

**Non-goals (explicit):** no investment advice or allocation suggestions, no order execution, no social/copy-trading features, no black-box ML for core decisions.

---

## 2. Core Features

1. **"Since You Last Checked" Digest** — snapshot on every view (price, ratios, headlines, timestamp). On return, diff against the last snapshot and produce a one-line narrative plus underlying deltas. This is the core primitive; everything else consumes it.
2. **News-Augmented Digest (RAG)** — retrieve news published between last-checked and now for the instrument and its sector, deduplicate and cluster near-identical stories, rank by semantic relevance and by correlation with flagged price-significant days, take the top 5, and feed only those into the summary generation step. Retrieval-then-generation, never free generation.
3. **Significance-Ranked Attention Feed** — score every diff (statistical/threshold/relative/event), surface only the top few per session, collapse the rest. Bigger watchlist means smarter triage, not a longer scroll.
4. **Adaptive Alerts** — volatility-normalized triggers (not flat percentages), reusing the significance score rather than a separate alerting system.
5. **Data Integrity & Corporate Action Layer** — staleness indicators (market-closed vs feed-stuck), NSE/BSE reconciliation, corporate-action adjustment so splits/bonuses/dividends never register as false "crashes."
6. **MF/ETF Subscription-Window Tracker** — tracks RBI LRS-driven overseas fund subscription pauses via AMFI data, notifies before/as a window closes.

**Stretch:** circuit-limit proximity and volume-spike detection folded into the significance score (source: NSE bhavcopy price-band columns).

---

## 3. What Counts as "Meaningfully Changed"

No flat percentage thresholds. A change is meaningful if it is:

| Category | Example |
|---|---|
| Statistical price deviation | Move large relative to the instrument's own rolling volatility (z-score / ATR-normalized) |
| Threshold / structural crossing | 52-week high/low, moving average crossover, circuit-limit proximity |
| Relative / peer context | Down 2% while sector index is down 3.5% (actually outperforming) |
| Discrete event | Earnings, corporate action, rating change, MF subscription window change |

Corporate-action price discontinuities are detected and excluded by design, never reported as meaningful change.

---

## 4. Tech Stack

**Frontend**
- Next.js (React), Tailwind CSS, Recharts
- React Query (server state) + Zustand (UI state)
- Mobile-responsive by default
- Hosted on Cloud Run or Firebase Hosting

**Backend**
- Python + FastAPI (matches yfinance's native language, no cross-language hop)
- Cloud Run (serverless containers)
- Cloud Scheduler → Cloud Run batch job for all ingestion (price + news), on one shared cadence
- Cloud SQL (Postgres) with the **pgvector** extension for embeddings — one database for relational + vector data, no separate vector store
- Firebase Authentication — also the mechanism for state persisting across sessions/devices
- Simple Postgres-based cache table (or Memorystore/Redis) to throttle yfinance calls
- Notifications: Firebase Cloud Messaging (web push), email as fallback

**AI Layer**
- Gemini API (via Vertex AI or direct, on GCP credits) for two jobs only:
  1. Embeddings for news items and semantic ranking
  2. Generating the short narrative digest from an already-retrieved, already-scored set of inputs
- Significance scoring itself stays rule-based (z-scores, ATR, threshold crossings, corporate-action detection) — AI generates language, never decides what's significant.

**Data Ingestion**
- yfinance — equity/ETF quotes, historical data, and `.news` for headlines (`.NS` / `.BO` tickers)
- Google News RSS — date-bounded queries (`after:` / `before:`) for company and sector-level news, using `sector`/`industry` fields from yfinance's ticker info
- AMFI NAVAll — official, free, daily MF NAV and subscription status

---

## 5. Data Model

- `User`
- `WatchlistItem` (user_id, instrument_id, added_at)
- `Instrument` (id, type: equity/etf/mf, exchange, sector, corporate_action_history)
- `Snapshot` (instrument_id, user_id, captured_at, price, ratios, top_headlines)
- `Diff` (derived between two snapshots; includes `news_items` field, top 5 post-ranking)
- `SignificanceScore` (diff_id, score, category)
- `NewsItem` (id, instrument_id, sector_id, source, url, title, published_at, embedding, dedupe_cluster_id, ingested_at)
- `Alert` (user_id, instrument_id, condition, adaptive_threshold, status)
- `SubscriptionWindow` (instrument_id, status, last_changed_at)

Flat and relational by design — no premature sharding or event-sourcing.

---

## 6. News RAG Pipeline (Feature 2 detail)

**Ingestion** (runs inside the shared scheduled job):
1. For each actively watched instrument: pull yfinance `.news`, pull Google News RSS for company name and separately for sector.
2. Dedupe by URL, embed title + snippet via Gemini embeddings, insert into `NewsItem`.

**Retrieval** (runs when a user opens a stock or the digest is generated):
1. Filter `NewsItem` where `published_at` is between `last_checked_at` and `now`, matching instrument or sector.
2. Cluster near-duplicates by embedding similarity (collapse repeated wire stories into one).
3. Rank remaining candidates by: semantic relevance to the instrument, **and** correlation with days already flagged by the SignificanceScore engine (reuses existing infra rather than inventing a new importance heuristic).
4. Take top 5.

**Generation:**
- Pass only the top 5 retrieved items to Gemini with a tight prompt: summarize into 2–3 lines, paraphrased, no fabricated detail beyond what's retrieved.
- If no news in the window: return "no notable news, movement was price-driven" rather than an empty/awkward output.
- If the API call fails: fall back to a template-based summary so a live demo never breaks.

---

## 7. Build Stages (Claude Code phases)

Point Claude Code at this file and the Source of Truth doc before each phase. Each phase = its own session/commit boundary, so every piece can be explained independently.

| Phase | Deliverable |
|---|---|
| 0 | Scaffold monorepo (`/backend` FastAPI, `/frontend` Next.js). `MarketDataProvider` interface only (yfinance / AMFI / mock planned). |
| 1 | Implement yfinance, AMFI, and mock providers behind the interface. Unit tests swapping providers via config. |
| 2 | Data model via SQLAlchemy/Postgres. Diff engine. Rule-based significance scoring (four categories). Corporate-action exclusion as a testable case. |
| 3 | Scheduled batch ingestion job (price + news together) for Cloud Scheduler + Cloud Run. |
| 4 | News RAG pipeline: embeddings, pgvector storage, retrieval + clustering + ranking logic. |
| 5 | AI narrative layer: Gemini summary generation from Diff + top-5 news, with template fallback. |
| 6 | Frontend: watchlist management, ranked attention feed, per-instrument digest view (with news), adaptive alerts, subscription-window tracker. |
| 7 | Edge cases pass: market hours/holiday calendar, NSE/BSE disagreement, stale-vs-closed detection, corporate-action tests. |
| 8 | Polish: README (judge-runnable with mock provider as default), locked 100-word pitch, final scope check against this plan. |

**Cutting order if time runs short:** News RAG ranking sophistication (fall back to recency-only ranking) → AI narrative layer (fall back to template-based digest) → circuit-limit stretch feature. The core digest engine (Phase 1–3) and edge case handling (Phase 7) are not cut candidates — they're what the judging criteria weight most heavily.

---

## 8. Judging Criteria Map

| Dimension | Where addressed |
|---|---|
| Engineering Depth | Diff engine, provider abstraction, RAG pipeline, data model |
| Product & Problem Interpretation | Meaningful-change definition, news-augmented digest |
| Edge Cases & Resilience | Data integrity layer, corporate actions, staleness, dedup |
| Code Quality & Simplicity | Non-goals list, single Postgres+pgvector store, rule-based scoring |
| Originality | Subscription-window tracker, significance-correlated news ranking |

---

## 9. Open Decisions

1. Sector-level news: pre-computed for every instrument every cycle, or only on-demand when a user opens that stock?
2. Notification channel: web push only, or push + email?
3. How much of the significance score is shown raw (z-score) vs. simplified to a label (high/medium/low)?
