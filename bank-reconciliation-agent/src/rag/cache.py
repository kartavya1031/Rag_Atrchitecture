"""Semantic query cache — caches KB search results with TTL for frequent queries."""

import hashlib
import threading
from typing import Any

from cachetools import TTLCache


_CACHE_MAX_SIZE = 256
_CACHE_TTL_SECONDS = 600  # 10 minutes

_cache = TTLCache(maxsize=_CACHE_MAX_SIZE, ttl=_CACHE_TTL_SECONDS)
_lock = threading.Lock()


def _make_key(query: str, n_results: int, filename_filter: str | None, rerank: bool) -> str:
    """Create a deterministic cache key from query parameters."""
    raw = f"{query.strip().lower()}|{n_results}|{filename_filter or ''}|{rerank}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def cache_get(
    query: str,
    n_results: int,
    filename_filter: str | None = None,
    rerank: bool = False,
) -> dict[str, Any] | None:
    """Look up a cached result. Returns None on miss."""
    key = _make_key(query, n_results, filename_filter, rerank)
    with _lock:
        return _cache.get(key)


def cache_put(
    query: str,
    n_results: int,
    result: dict[str, Any],
    filename_filter: str | None = None,
    rerank: bool = False,
) -> None:
    """Store a result in the cache."""
    key = _make_key(query, n_results, filename_filter, rerank)
    with _lock:
        _cache[key] = result


def cache_clear() -> int:
    """Clear the entire cache. Returns number of evicted entries."""
    with _lock:
        count = len(_cache)
        _cache.clear()
        return count


def cache_stats() -> dict[str, Any]:
    """Return cache statistics."""
    with _lock:
        return {
            "size": len(_cache),
            "max_size": _cache.maxsize,
            "ttl_seconds": int(_cache.ttl),
        }
