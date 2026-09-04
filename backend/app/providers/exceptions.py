"""Exceptions shared by every MarketDataProvider implementation.

Kept separate from base.py (rather than one file per provider) so callers
can catch these without importing a specific provider — the whole point of
the interface is that callers shouldn't need to know which one is active.
"""


class InstrumentNotFoundError(KeyError):
    """The provider has no data for the requested instrument_id."""


class ProviderUnavailableError(RuntimeError):
    """An external provider failed (network, rate limit, schema change) even
    after retries. Callers are expected to catch this and surface a
    "data temporarily unavailable" state (Feature 5, staleness handling in
    Phase 7) rather than letting it crash the request.
    """
