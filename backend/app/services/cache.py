"""Short-TTL in-memory cache for the dashboard read endpoints
(routers/dashboard.py). director_dashboard in particular recomputes
aggregates over every call plus a per-team top_tag_types query in a loop, on
every single request -- expensive for data that doesn't need to be
second-fresh. Same in-memory-is-fine reasoning as services/events.py: this
app runs as one process on Render's free tier, so there's no cross-instance
cache to keep in sync.

Explicitly invalidated (not just left to expire) wherever a score actually
changes underneath a dashboard -- see services/rescoring.py's
recalculate_score, the one place a team leader's action should be visible
immediately rather than up to TTL_SECONDS stale.
"""
import time
from typing import Any

TTL_SECONDS = 30.0

_cache: dict[str, tuple[float, Any]] = {}  # key -> (expires_at, value)


def get(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if time.time() >= expires_at:
        del _cache[key]
        return None
    return value


def set(key: str, value: Any, ttl_seconds: float = TTL_SECONDS) -> None:
    _cache[key] = (time.time() + ttl_seconds, value)


def invalidate_all() -> None:
    """Drops every cached dashboard -- a score change can affect the
    director view, the affected advisor's team view, and the advisor's own
    view all at once; precise per-scope invalidation isn't worth the
    complexity for an event this infrequent (a human reviewing one tag)."""
    _cache.clear()
