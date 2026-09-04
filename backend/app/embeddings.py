"""Embedding generation — the only other allowed use of an LLM call besides
narrative generation (docs/SOURCE_OF_TRUTH.md, "AI/LLM usage"). Never used
to decide significance; only to embed news text for retrieval ranking.

Two implementations, selected the same way MarketDataProvider is
(EMBEDDING_PROVIDER=gemini|mock, default mock): GeminiEmbeddingProvider
calls the real API; MockEmbeddingProvider derives a deterministic vector
from a text hash, so news ingestion — like everything else — still runs
with zero network calls and zero credentials by default.

docs/plan.md §4 says Gemini is reached "via Vertex AI or direct" — this
project uses Vertex AI, not a bare API key, because every other GCP piece
(Cloud Run, Cloud SQL, Firebase Auth) already runs on GCP-native auth: in
Cloud Run, GeminiEmbeddingProvider picks up the service's own attached
service-account credentials automatically (Application Default
Credentials), so there's no separate GEMINI_API_KEY secret to create,
rotate, or leak. Set GOOGLE_CLOUD_PROJECT (and optionally
GOOGLE_CLOUD_LOCATION) — the same project already backing Cloud Run/Cloud
SQL — and the google-genai SDK resolves credentials/project/location from
the environment on its own. A bare API key (GEMINI_API_KEY, no GCP project
needed) is still supported as a fallback for quick local testing outside
GCP. GeminiEmbeddingProvider is unverified against a live key or a live GCP
project (neither was available while building this phase); MockEmbeddingProvider
is what every test in this project actually runs against.
"""

import hashlib
import os
import struct
import time
from typing import Protocol

# Matches text-embedding-004 / gemini-embedding-001's supported output size,
# so a real embedding and a mock one are interchangeable in the pgvector
# column (see app/vector_type.py).
EMBEDDING_DIM = 768

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 0.5


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


class MockEmbeddingProvider:
    """Deterministic, hash-derived vector — same text always yields the same
    embedding, so cosine-similarity clustering/ranking in tests is
    reproducible without ever calling out to Gemini."""

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # Repeat the 32-byte digest to fill EMBEDDING_DIM floats, each
        # derived from 4 bytes and normalized into roughly [-1, 1].
        values = []
        needed_bytes = EMBEDDING_DIM * 4
        stream = (digest * (needed_bytes // len(digest) + 1))[:needed_bytes]
        for i in range(EMBEDDING_DIM):
            chunk = stream[i * 4 : i * 4 + 4]
            (as_uint,) = struct.unpack(">I", chunk)
            values.append((as_uint / 0xFFFFFFFF) * 2 - 1)
        return values


class GeminiEmbeddingProvider:
    """Calls Gemini's embedding endpoint. Wrapped in the same
    retry-with-backoff pattern as YFinanceProvider (app/providers/
    yfinance_provider.py) since this is also an external network call that
    shouldn't be allowed to crash ingestion for one instrument's news.

    NOTE: built and reviewed against the google-genai SDK's documented
    surface, but never exercised against a live API key — nobody had one
    while this phase was built. Treat the exact model name/config below as
    needing a real run to confirm before relying on it.
    """

    MODEL_NAME = "gemini-embedding-001"

    def __init__(self):
        from google import genai  # imported lazily so MockEmbeddingProvider needs no dependency at all

        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        api_key = os.environ.get("GEMINI_API_KEY")

        if project:
            # Vertex AI path (the production one, see module docstring):
            # project/location/credentials are resolved from the
            # environment and Application Default Credentials — no key here.
            self._client = genai.Client(
                vertexai=True,
                project=project,
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
            )
        elif api_key:
            # Direct API key path — local/non-GCP fallback only.
            self._client = genai.Client(api_key=api_key)
        else:
            raise RuntimeError(
                "Neither GOOGLE_CLOUD_PROJECT (Vertex AI, used in production) "
                "nor GEMINI_API_KEY (direct API, local fallback) is set — set "
                "one, or leave EMBEDDING_PROVIDER unset/'mock' to run without "
                "Gemini access."
            )

    def embed(self, text: str) -> list[float]:
        from google.genai import types

        last_exc: Exception | None = None
        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = self._client.models.embed_content(
                    model=self.MODEL_NAME,
                    contents=text,
                    config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
                )
                return list(response.embeddings[0].values)
            except Exception as exc:  # the SDK's failure modes aren't narrowly typed
                last_exc = exc
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_BASE_DELAY_SECONDS * (2**attempt))
        raise RuntimeError(f"Gemini embedding call failed after {RETRY_ATTEMPTS} attempts") from last_exc


def get_embedding_provider() -> EmbeddingProvider:
    """The one place EMBEDDING_PROVIDER is read — mirrors
    app/providers/config.py's get_market_data_provider() for the same
    reason: nothing else should scatter this env var read around."""
    name = os.environ.get("EMBEDDING_PROVIDER", "mock").lower()
    if name == "mock":
        return MockEmbeddingProvider()
    if name == "gemini":
        return GeminiEmbeddingProvider()
    raise ValueError(f"Unknown EMBEDDING_PROVIDER={name!r}; expected 'mock' or 'gemini'")
