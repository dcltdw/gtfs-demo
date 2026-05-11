"""Inbound rate limiter — sliding-window, per Streamlit session.

The Streamlit page (#11) calls :meth:`SessionRateLimiter.acquire` before every
data-fetching handler. ``True`` means the request is allowed; ``False`` means
the session has used up its budget — the page shows a banner and serves
cached data.

Design choices, all intentional for a 4-6h spike:

- **In-memory.** A `dict[str, deque[float]]` keyed by session ID. Process-local;
  resets on restart. **Out of scope** (all post-demo): Redis-backed shared
  state (so multiple Streamlit replicas share a quota), persistence across
  restarts (post-demo #26 may revisit), distributed rate limiting.
- **Sliding window, not token bucket.** Cheaper to reason about for the spike
  (no refill-rate parameter); a token-bucket comparison ADR is tracked as
  post-demo #41.
- **Per session, not per IP.** A future per-IP layer is post-demo #40 —
  particularly important for an unauthenticated public surface, less critical
  here because the app sits behind a single seeded auth.
- **No HTTP 429 semantics.** Streamlit isn't a request/response server; the
  limiter returns a bool and the page renders accordingly. A real HTTP API
  with proper 429 + `Retry-After` is post-demo.
- **Lazy idle eviction.** Sweeps stale sessions on every `acquire` call. Cheap
  at the spike's scale (≤100 concurrent sessions); a background sweeper is
  post-demo if needed.

Thread-safe: a single ``threading.Lock`` guards the bucket dict. Streamlit's
session threads can call into the same limiter without races.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque

logger = logging.getLogger(__name__)


class SessionRateLimiter:
    """Per-session sliding-window rate limiter."""

    def __init__(
        self,
        limit: int = 30,
        window_s: float = 60.0,
        *,
        idle_evict_s: float = 3600.0,
    ) -> None:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if window_s <= 0:
            raise ValueError("window_s must be > 0")
        if idle_evict_s <= window_s:
            raise ValueError("idle_evict_s must exceed window_s")
        self._limit = limit
        self._window_s = window_s
        self._idle_evict_s = idle_evict_s
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def acquire(self, session_id: str, *, now: float | None = None) -> bool:
        """Return ``True`` if the request is allowed; ``False`` if rate-limited.

        ``now`` is injectable for tests (monotonic seconds); defaults to
        :func:`time.monotonic` so behavioural tests don't have to mock the clock.
        """
        current = time.monotonic() if now is None else now
        with self._lock:
            self._evict_idle_locked(current)
            bucket = self._buckets.setdefault(session_id, deque())
            cutoff = current - self._window_s
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self._limit:
                logger.info(
                    "inbound rate-limit throttle session_id=%s used=%d limit=%d window_s=%.1f",
                    session_id,
                    len(bucket),
                    self._limit,
                    self._window_s,
                )
                return False
            bucket.append(current)
            return True

    def remaining(self, session_id: str, *, now: float | None = None) -> int:
        """Return budget remaining for ``session_id`` in the current window.

        Useful for UI affordances (showing "x requests left this minute"). Does
        not consume budget.
        """
        current = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._buckets.get(session_id)
            if bucket is None:
                return self._limit
            cutoff = current - self._window_s
            used = sum(1 for ts in bucket if ts >= cutoff)
            return max(0, self._limit - used)

    def session_count(self) -> int:
        """Number of sessions currently tracked. Useful for ops + tests."""
        with self._lock:
            return len(self._buckets)

    def _evict_idle_locked(self, now: float) -> None:
        """Drop sessions whose most recent event is older than ``idle_evict_s``.

        Called with the lock held. Iterates the bucket dict once per
        :meth:`acquire`; at the spike's scale (~100 concurrent sessions) this
        is unmeasurably cheap.
        """
        cutoff = now - self._idle_evict_s
        stale: list[str] = []
        for sid, bucket in self._buckets.items():
            # An empty bucket counts as fresh (just-allocated).
            if bucket and bucket[-1] < cutoff:
                stale.append(sid)
        for sid in stale:
            del self._buckets[sid]
            logger.debug("inbound rate-limit evicted idle session_id=%s", sid)


__all__ = ("SessionRateLimiter",)
