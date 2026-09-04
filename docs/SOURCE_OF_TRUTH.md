# Source of Truth — Hard Rules

These rules apply to every phase of this build, no exceptions. They override anything
in a later prompt that conflicts with them. `docs/plan.md` is the product/technical
plan; this file is the non-negotiable constraint list on top of it.

## Product boundaries

- **Never** write investment advice, "buy/sell" language, or return recommendations —
  anywhere: code, comments, UI copy, or generated text. This product informs, it
  never advises.
- **Never** implement order execution or trading logic of any kind.

## Significance scoring

- Significance scoring (what counts as a "meaningful change", see `plan.md` §3) must
  be rule-based and auditable — z-scores, ATR bands, threshold crossings, explicit
  event rules.
- Never replace significance scoring with a trained model or an LLM call. If a task
  seems to require ML for this, stop and ask instead of implementing it.

## AI/LLM usage

AI/LLM calls (Gemini) are allowed for exactly two jobs, and nothing else:

1. Generating embeddings for news retrieval.
2. Generating short natural-language summaries from data that has already been
   computed and retrieved.

An LLM must never decide what is "significant" — it only describes what the
rule-based engine already decided.

## External data access

Every external data call (yfinance, Google News RSS, AMFI, Gemini) must go through
the provider abstraction defined in Phase 0 (`MarketDataProvider` and friends).
Never call an external API directly from a route handler or a frontend component.

## Scope discipline

- Every feature must trace back to one of the six features in `plan.md` §2. If
  something extra seems needed, stop and ask before adding it.
- Prefer the simplest implementation that satisfies the requirement. Do not add
  caching layers, message queues, microservices, or abstraction layers beyond what a
  phase explicitly asks for.
- If a prompt is ambiguous about a technical choice not already decided in
  `plan.md`, stop and ask rather than picking silently.

## Process

- Write a short comment above any non-obvious decision explaining why, in plain
  language, as if answering "why did you do it this way" to a reviewer.
- After finishing a phase, list what was built, what was deliberately left out, and
  any open question, before moving to the next phase.
