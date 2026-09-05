"""Narrative generation — job #2 of the two allowed LLM uses
(docs/SOURCE_OF_TRUTH.md, "AI/LLM usage" — this repo has no CLAUDE.md; that
file is this project's equivalent "hard rules" doc). By this point the
significance decision is already made (app/significance.py, Phase 2) —
Gemini only phrases it, never re-derives or second-guesses it.

Like retrieval, this runs at view-time (docs/plan.md §6: "runs when a user
opens a stock or the digest is generated"), not at ingestion — so it isn't
wired into app/ingestion/run_ingestion.py. A future route handler is the
intended caller, once one exists. Nothing here persists a digest anywhere:
Diff/SignificanceScore have no text column for one (docs/plan.md §5's
field lists don't include one), so this stays a pure generate-and-return
function.
"""

import logging
import os
import re
import time
from typing import Protocol

from app.models import Diff, NewsItem, SignificanceScore

logger = logging.getLogger(__name__)

GEMINI_TIMEOUT_MS = 8_000
RETRY_ATTEMPTS = 2
RETRY_BASE_DELAY_SECONDS = 0.5

# Hard backstop, not the only line of defense — the prompt already
# instructs Gemini never to give advice, but a model can still slip. If the
# output matches any of these, it's discarded in favor of the template
# summary rather than ever reaching a user.
_ADVICE_PATTERN = re.compile(
    r"\b(buy\w*|sell\w*|hold\w*|invest\w*|accumulat\w*|book profit|target price|"
    r"should (?:consider|purchase)|recommend\w*)\b",
    re.IGNORECASE,
)


def _looks_like_advice(text: str) -> bool:
    return bool(_ADVICE_PATTERN.search(text))


def _template_summary(diff: Diff, significance: SignificanceScore) -> str:
    """Deterministic, no-network fallback — built from the diff and
    significance fields alone (no news dependency), per the Phase 5 brief's
    own example format. Used whenever Gemini is unavailable/unconfigured,
    times out, errors, or its output fails the advice-language check —
    also what every test in this project runs against.

    Uses diff.instrument_id as a stand-in for "instrument name": Instrument
    has no name field in this project's data model (docs/plan.md §5), only
    the ticker/scheme-code id — same substitution app/news_retrieval.py
    already makes for its query text.
    """
    pct = abs(diff.price_delta_pct) * 100
    direction = "up" if diff.price_delta_pct >= 0 else "down"
    if significance.category == "none":
        # No category fired for this diff — "driven by none" reads as
        # broken English, so this one case gets its own phrasing rather
        # than forcing the general "driven by {category}" template to
        # cover a non-category.
        return f"{diff.instrument_id} moved {direction} {pct:.1f}% since you last checked, with no significant driver flagged."
    return (
        f"{diff.instrument_id} moved {direction} {pct:.1f}% since you last "
        f"checked, driven by {significance.category}."
    )


def _build_prompt(diff: Diff, significance: SignificanceScore, news_items: list[NewsItem]) -> str:
    base_instructions = (
        "You are summarizing a stock/ETF/mutual-fund price change for a "
        "watchlist app. Write 2-3 sentences, plain and factual. Use ONLY "
        "the data given below — never invent a fact, number, or event not "
        "present here. Never suggest buying, selling, holding, or any "
        "other action, and never give a recommendation or predict future "
        "returns of any kind — describe what already happened, not what "
        "to do."
    )
    facts = (
        f"Instrument: {diff.instrument_id}\n"
        f"Price change since last check: {diff.price_delta_pct:+.2%} "
        f"(from {diff.before_price} to {diff.after_price})\n"
        f"Why this was flagged as significant: {significance.category}"
        + (f" — {significance.detail}" if significance.detail else "")
        + "\n"
    )

    if not news_items:
        # Adjusted instruction rather than a bare "no news" statement — the
        # model should say the move was price-driven, not awkwardly report
        # the absence of news as if that were itself a fact worth stating.
        news_section = (
            "No related news was found in the relevant window. State "
            "plainly that the movement was price-driven with no notable "
            "news, in one clause — don't dwell on or repeat this point.\n"
        )
    else:
        lines = []
        for item in news_items[:5]:
            lines.append(
                f"- {item.title} ({item.source}, {item.published_at.date().isoformat()})"
            )
        news_section = "Recent related headlines:\n" + "\n".join(lines) + "\n"

    return f"{base_instructions}\n\n{facts}{news_section}"


class NarrativeProvider(Protocol):
    def generate(self, diff: Diff, significance: SignificanceScore, news_items: list[NewsItem]) -> str: ...


class GeminiNarrativeProvider:
    """See app/embeddings.py's GeminiEmbeddingProvider for the identical
    Vertex-AI-first / API-key-fallback auth pattern and its rationale
    (this project is GCP-native end to end, so production uses Vertex AI,
    not a bare key). Unverified against a live project/key — the GCP
    project set up for this (watch-me-groww) has a closed billing account
    pending a bank issue on the user's end; nobody has run this against
    real Gemini yet.
    """

    MODEL_NAME = "gemini-2.5-flash"

    def __init__(self):
        from google import genai  # imported lazily so the template-only path needs no dependency
        from google.genai import types

        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        api_key = os.environ.get("GEMINI_API_KEY")
        http_options = types.HttpOptions(timeout=GEMINI_TIMEOUT_MS)

        if project:
            self._client = genai.Client(
                vertexai=True,
                project=project,
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                http_options=http_options,
            )
        elif api_key:
            self._client = genai.Client(api_key=api_key, http_options=http_options)
        else:
            raise RuntimeError(
                "Neither GOOGLE_CLOUD_PROJECT (Vertex AI) nor GEMINI_API_KEY is set "
                "— set one, or leave NARRATIVE_PROVIDER unset/'template' to run "
                "without Gemini access."
            )

    def generate(self, diff: Diff, significance: SignificanceScore, news_items: list[NewsItem]) -> str:
        prompt = _build_prompt(diff, significance, news_items)
        last_exc: Exception | None = None
        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = self._client.models.generate_content(model=self.MODEL_NAME, contents=prompt)
                return (response.text or "").strip()
            except Exception as exc:  # the SDK's failure modes (timeout included) aren't narrowly typed
                last_exc = exc
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_BASE_DELAY_SECONDS * (2**attempt))
        raise RuntimeError(f"Gemini narrative generation failed after {RETRY_ATTEMPTS} attempts") from last_exc


def _resolve_default_provider() -> NarrativeProvider | None:
    name = os.environ.get("NARRATIVE_PROVIDER", "template").lower()
    if name == "template":
        return None
    if name == "gemini":
        try:
            return GeminiNarrativeProvider()
        except RuntimeError as exc:
            logger.warning("falling back to template narrative: %s", exc)
            return None
    raise ValueError(f"Unknown NARRATIVE_PROVIDER={name!r}; expected 'template' or 'gemini'")


def generate_digest(
    diff: Diff,
    significance: SignificanceScore,
    news_items: list[NewsItem],
    narrative_provider: NarrativeProvider | None = None,
) -> str:
    """The public entry point: a 2-3 sentence digest for one Diff, given
    the significance category app/significance.py already decided (Phase 2)
    and up to 5 news items app/news_retrieval.py's get_relevant_news()
    already retrieved (Phase 4) — this function only phrases them.

    Never raises, and always returns something displayable: a Gemini
    failure, timeout, or an advice-like slip past the prompt all fall back
    to a template summary built from the diff/significance fields alone,
    logged but never surfaced as an error to the caller.
    """
    provider = narrative_provider if narrative_provider is not None else _resolve_default_provider()

    if provider is not None:
        try:
            text = provider.generate(diff, significance, news_items)
            if text and not _looks_like_advice(text):
                return text
            logger.warning("discarding Gemini digest (empty or advice-like), using template instead")
        except Exception as exc:
            logger.warning("Gemini digest generation failed, using template instead: %s", exc)

    return _template_summary(diff, significance)
