"""Unit tests for app/narrative.py's generate_digest(). Every test injects
a fake/no provider — none of this hits real Gemini, per NARRATIVE_PROVIDER
defaulting to 'template' and every provider here being an explicit test
double.
"""

from datetime import datetime

import pytest

from app.models import Diff, NewsItem, SignificanceScore
from app.narrative import generate_digest


def _diff(price_delta_pct: float, instrument_id: str = "RELIANCE.NS") -> Diff:
    return Diff(
        instrument_id=instrument_id,
        snapshot_before_id=1,
        snapshot_after_id=2,
        before_price=100.0,
        after_price=100.0 * (1 + price_delta_pct),
        price_delta_pct=price_delta_pct,
        ratio_deltas={},
    )


def _significance(category: str = "statistical", detail: str = "z=3.2") -> SignificanceScore:
    return SignificanceScore(diff_id=1, score=3.2, category=category, detail=detail)


def _news(title: str, source: str = "Reuters") -> NewsItem:
    return NewsItem(
        instrument_id="RELIANCE.NS",
        source=source,
        url=f"https://example.com/{title}",
        title=title,
        published_at=datetime(2026, 9, 2, 9, 0),
    )


class _FakeProvider:
    """Stands in for GeminiNarrativeProvider — success, failure, and
    advice-slip cases are each just a different construction of this."""

    def __init__(self, response: str | None = None, raises: Exception | None = None):
        self._response = response
        self._raises = raises

    def generate(self, diff, significance, news_items):
        if self._raises:
            raise self._raises
        return self._response


# --- Fallback path: Gemini call fails/times out ---


def test_gemini_failure_falls_back_to_template_with_valid_nonempty_string():
    diff = _diff(0.065, instrument_id="HDFCBANK.NS")
    significance = _significance(category="statistical")
    provider = _FakeProvider(raises=TimeoutError("Gemini request timed out"))

    result = generate_digest(diff, significance, [_news("Some headline")], narrative_provider=provider)

    assert isinstance(result, str)
    assert result.strip() != ""
    assert "HDFCBANK.NS" in result
    assert "statistical" in result
    assert "6.5%" in result


def test_gemini_generic_exception_also_falls_back_to_template():
    diff = _diff(-0.043, instrument_id="TCS.NS")
    significance = _significance(category="threshold", detail="new 52-week low")
    provider = _FakeProvider(raises=RuntimeError("503 Service Unavailable"))

    result = generate_digest(diff, significance, [], narrative_provider=provider)

    assert result == "TCS.NS moved down 4.3% since you last checked, driven by crossing a key price threshold."


# --- Success path: Gemini responds normally ---


def test_gemini_success_response_is_returned_as_the_final_digest():
    diff = _diff(0.03, instrument_id="RELIANCE.NS")
    significance = _significance(category="event", detail="corporate action: bonus")
    news = [_news("Reliance announces bonus issue")]
    provider = _FakeProvider(
        response="Reliance shares rose 3% after the company announced a bonus share issue."
    )

    result = generate_digest(diff, significance, news, narrative_provider=provider)

    assert result == "Reliance shares rose 3% after the company announced a bonus share issue."


def test_gemini_success_with_no_news_still_used_verbatim():
    diff = _diff(0.02, instrument_id="INFY.NS")
    significance = _significance(category="statistical")
    provider = _FakeProvider(response="Infosys rose 2% with no notable news; the move was price-driven.")

    result = generate_digest(diff, significance, [], narrative_provider=provider)

    assert result == "Infosys rose 2% with no notable news; the move was price-driven."


# --- Advice-language backstop still applies here ---


def test_advice_like_gemini_output_falls_back_to_template():
    diff = _diff(0.03, instrument_id="TCS.NS")
    significance = _significance(category="statistical")
    provider = _FakeProvider(response="You should buy TCS now before it rallies further.")

    result = generate_digest(diff, significance, [_news("Deal win")], narrative_provider=provider)

    assert "should buy" not in result
    assert "TCS.NS" in result  # fell back to the template summary instead


@pytest.mark.parametrize(
    "phrase",
    [
        "You should buy this stock",
        "Consider selling your position",
        "This is a strong hold",
        "Our recommendation is to invest now",
        "Target price of 3000 expected",
    ],
)
def test_advice_language_detection_covers_common_phrasings(phrase):
    diff = _diff(0.03)
    significance = _significance()
    provider = _FakeProvider(response=phrase)

    result = generate_digest(diff, significance, [_news("Some story")], narrative_provider=provider)

    assert result != phrase  # never surfaced verbatim; template used instead


def test_empty_gemini_response_falls_back_to_template():
    diff = _diff(0.01, instrument_id="TCS.NS")
    significance = _significance(category="event")
    provider = _FakeProvider(response="")

    result = generate_digest(diff, significance, [_news("Some story")], narrative_provider=provider)

    assert "TCS.NS" in result


# --- No provider configured at all (NARRATIVE_PROVIDER unset/'template') ---


def test_no_provider_configured_uses_template_directly():
    diff = _diff(0.065, instrument_id="HDFCBANK.NS")
    significance = _significance(category="statistical")

    result = generate_digest(diff, significance, [_news("Some headline")], narrative_provider=None)

    assert result == "HDFCBANK.NS moved up 6.5% since you last checked, driven by a statistically unusual price move."
