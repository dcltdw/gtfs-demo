"""Per-URL outbound rate limiter (token-bucket style).

A single refilling-bucket-per-URL is enough for the spike's needs: refill rate
is one token every ``interval`` seconds; each ``acquire`` consumes one token and
sleeps until the next refill if the bucket is empty.

Thread-safety is intentionally out of scope — Streamlit fetches happen on a
single session thread.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class OutboundRateLimiter:
    """Per-URL minimum-interval rate limiter.

    Calling :meth:`acquire` for the same URL twice in quick succession blocks the
    second call until ``interval`` seconds have elapsed since the first.
    """

    def __init__(self, interval_seconds: float = 10.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")
        self.interval_seconds = interval_seconds
        self._last_acquired: dict[str, float] = {}

    def acquire(self, url: str, *, now: float | None = None) -> float:
        """Block (sleep) if the URL was acquired within the past ``interval``.

        Returns the number of seconds the caller waited (0.0 on a fresh URL).
        ``now`` is injectable for tests; defaults to ``time.monotonic()``.
        """
        current = time.monotonic() if now is None else now
        last = self._last_acquired.get(url)

        if last is None:
            self._last_acquired[url] = current
            return 0.0

        elapsed = current - last
        if elapsed >= self.interval_seconds:
            self._last_acquired[url] = current
            return 0.0

        wait = self.interval_seconds - elapsed
        logger.info(
            "outbound rate-limit wait %.2fs for %s (interval=%.1fs)",
            wait,
            url,
            self.interval_seconds,
        )
        time.sleep(wait)
        self._last_acquired[url] = (current if now is not None else time.monotonic()) + wait
        return wait
