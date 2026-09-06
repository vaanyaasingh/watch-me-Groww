"""News retrieval (docs/plan.md §6, "Retrieval") — runs when a user opens a
stock or the digest is generated, on NewsItem rows the ingestion job
(app/ingestion/run_ingestion.py) already wrote.

get_relevant_news() is a pure read: it doesn't write anything back (in
particular, it does NOT persist NewsItem.dedupe_cluster_id — clustering is
recomputed per call against whatever's in the requested window, since the
window itself changes call to call; there's no stable cluster to cache).
The `dedupe_cluster_id` set on returned NewsItem objects only exists on
those in-memory objects, so a caller can group "N sources on one story"
without a second query.
"""

import math
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Diff, Instrument, NewsItem, SignificanceScore, Snapshot
from app.embeddings import EmbeddingProvider, get_embedding_provider

# Empirically, paraphrased wire-service copies of the same story land above
# 0.95 cosine similarity on Gemini's embedding model; 0.92 gives a little
# headroom for minor rewording between outlets while still being far above
# where two merely-related-but-distinct stories about the same company
# tend to sit (well under 0.9 in practice).
DEDUPE_SIMILARITY_THRESHOLD = 0.92

# Weighted per docs/plan.md §6 ranking step: semantic relevance to the
# instrument, and correlation with a day the SignificanceScore engine
# already flagged. Weighted towards the significance signal since that's
# the one this project can actually stand behind (rule-based, auditable);
# semantic similarity from an embedding is a softer signal.
SEMANTIC_WEIGHT = 0.4
SIGNIFICANCE_WEIGHT = 0.6

TOP_N = 5


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _cluster_near_duplicates(items: list[NewsItem]) -> list[NewsItem]:
    """Greedy single-linkage clustering: an item joins the first existing
    cluster its embedding is similar enough to, otherwise it starts a new
    one. One representative — the earliest-published item, since that's
    closest to the original wire story — survives per cluster."""
    clusters: list[dict] = []  # each: {"representative": NewsItem, "embedding": list[float]}

    for item in sorted(items, key=lambda i: i.published_at):
        if item.embedding is None:
            clusters.append({"representative": item, "embedding": None})
            continue
        joined = False
        for cluster_id, cluster in enumerate(clusters):
            if cluster["embedding"] is None:
                continue
            if _cosine_similarity(item.embedding, cluster["embedding"]) >= DEDUPE_SIMILARITY_THRESHOLD:
                item.dedupe_cluster_id = cluster_id
                joined = True
                break
        if not joined:
            new_id = len(clusters)
            item.dedupe_cluster_id = new_id
            clusters.append({"representative": item, "embedding": item.embedding})

    return [cluster["representative"] for cluster in clusters]


def _significant_dates(session: Session, instrument_id: str) -> set[date]:
    """Every date this instrument had at least one SignificanceScore fire.
    A SignificanceScore row only exists when a check already crossed its
    threshold (app/significance.py never persists a non-firing check), so
    mere presence in this table already means "significant" — there's no
    separate "how high" cutoff to apply on top of that."""
    stmt = (
        select(Snapshot.captured_at)
        .join(Diff, Diff.snapshot_after_id == Snapshot.id)
        .join(SignificanceScore, SignificanceScore.diff_id == Diff.id)
        .where(Diff.instrument_id == instrument_id)
        .distinct()
    )
    return {captured_at.date() for captured_at in session.scalars(stmt)}


def get_relevant_news(
    session: Session,
    instrument_id: str,
    since: datetime,
    until: datetime,
    embedding_provider: EmbeddingProvider | None = None,
) -> list[NewsItem]:
    """The top 5 news items for `instrument_id` published in [since, until],
    matching the instrument itself or its sector, deduplicated and ranked.
    Returns [] if nothing is in the window — never raises, never fabricates
    a placeholder (docs/plan.md §6, "Handle the empty case explicitly").
    """
    instrument = session.get(Instrument, instrument_id)
    sector = instrument.sector if instrument else None

    match_stmt = select(NewsItem).where(NewsItem.published_at >= since, NewsItem.published_at <= until)
    if sector:
        match_stmt = match_stmt.where(
            (NewsItem.instrument_id == instrument_id) | (NewsItem.sector_id == sector)
        )
    else:
        match_stmt = match_stmt.where(NewsItem.instrument_id == instrument_id)

    candidates = list(session.scalars(match_stmt))
    if not candidates:
        return []

    representatives = _cluster_near_duplicates(candidates)

    # This function's own contract is "never raises" (see docstring) — a
    # Gemini embedding failure (rate limit, network blip, a bad key) must
    # degrade the ranking, not take down the whole digest request. Falling
    # back to significance-correlation alone (semantic=0 below) rather than
    # aborting is the same "one source failing doesn't sink the rest"
    # principle app/ingestion/run_ingestion.py already applies at batch time
    # — this is the same idea at request time.
    query_embedding: list[float] | None
    try:
        embedder = embedding_provider or get_embedding_provider()
        # Instrument.name isn't in this project's data model (docs/plan.md
        # §5) — the id (ticker) plus sector is the closest thing to a
        # "what is this instrument" query string available to embed.
        query_text = f"{instrument_id} {sector or ''}".strip()
        query_embedding = embedder.embed(query_text)
    except Exception:
        query_embedding = None

    significant_dates = _significant_dates(session, instrument_id)

    def _score(item: NewsItem) -> float:
        semantic = (
            _cosine_similarity(item.embedding, query_embedding) if item.embedding and query_embedding else 0.0
        )
        on_significant_day = 1.0 if item.published_at.date() in significant_dates else 0.0
        return SEMANTIC_WEIGHT * semantic + SIGNIFICANCE_WEIGHT * on_significant_day

    ranked = sorted(representatives, key=lambda item: (_score(item), item.published_at), reverse=True)
    return ranked[:TOP_N]
