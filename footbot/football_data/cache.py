"""
Simple in-memory TTL cache for football-data.org API responses.

Keeps slash commands fast and stops the poller from competing with
user requests for the 10 req/min free-tier rate limit.
"""
import logging
import threading
from time import monotonic
from typing import Any, Callable

logger = logging.getLogger(__name__)

_store: dict[str, tuple[Any, float]] = {}
_lock = threading.Lock()

SLACK_MAX_BLOCKS = 50
SLACK_SAFE_BLOCKS = 45  # conservative limit, leaving headroom for appended sections


def get(key: str, ttl: int, fn: Callable) -> Any:
    """Return cached value if still fresh, otherwise call fn(), cache, and return."""
    with _lock:
        entry = _store.get(key)
        if entry is not None:
            value, expires_at = entry
            if monotonic() < expires_at:
                logger.debug("Cache hit: %s", key)
                return value

    logger.debug("Cache miss: %s", key)
    value = fn()

    with _lock:
        _store[key] = (value, monotonic() + ttl)
    return value


def invalidate(key: str) -> None:
    with _lock:
        _store.pop(key, None)


def invalidate_all() -> None:
    with _lock:
        _store.clear()
