"""GTFS-RT HTTP fetcher.

Responsibilities:

- Send an identifying ``User-Agent`` (settings.gtfs_user_agent).
- Enforce a per-URL outbound rate limit (≤ 1 fetch / interval seconds).
- Retry transient failures (5xx, timeouts) with exponential backoff.
- Distinguish permanent (4xx) failures with a typed exception — no retries.
- Decode the response body as a GTFS-RT ``FeedMessage`` protobuf.
- Emit a structured log line on every attempt: URL, status, latency, retry count.
"""

from __future__ import annotations

import logging
import time

import requests
from google.transit import gtfs_realtime_pb2
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from gtfs_demo.config import Settings, get_settings
from gtfs_demo.fetcher.rate_limit import OutboundRateLimiter

logger = logging.getLogger(__name__)

_DEFAULT_RATE_LIMITER: OutboundRateLimiter | None = None


class FeedFetchError(Exception):
    """Base class for realtime-feed fetch failures."""


class TransientFeedError(FeedFetchError):
    """Raised on transient failures (timeout, 5xx) after all retries are exhausted."""


class PermanentFeedError(FeedFetchError):
    """Raised on 4xx responses or protobuf-decode failures — do NOT retry."""


def fetch_feed(
    feed_url: str,
    *,
    settings: Settings | None = None,
    rate_limiter: OutboundRateLimiter | None = None,
    session: requests.Session | None = None,
) -> gtfs_realtime_pb2.FeedMessage:
    """Fetch + decode a GTFS-RT feed, respecting rate-limit and retry policy.

    ``rate_limiter`` and ``session`` are injectable for tests; in production the
    module-level limiter and an ad-hoc session are used.
    """
    settings = settings or get_settings()
    limiter = rate_limiter or _get_default_rate_limiter(settings)
    sess = session or requests.Session()

    limiter.acquire(feed_url)

    raw = _fetch_with_retry(feed_url, settings=settings, session=sess)

    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(raw)
    except Exception as exc:  # protobuf raises a plain Exception subclass
        raise PermanentFeedError(
            f"Failed to decode GTFS-RT FeedMessage from {feed_url}: {exc}"
        ) from exc
    return feed


def _fetch_with_retry(
    feed_url: str,
    *,
    settings: Settings,
    session: requests.Session,
) -> bytes:
    """Perform the HTTP fetch with retry + structured log; return raw bytes."""
    attempt_count = {"n": 0}

    @retry(
        retry=retry_if_exception_type(_TransientHTTPError),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _attempt() -> bytes:
        attempt_count["n"] += 1
        return _fetch_once(
            feed_url,
            settings=settings,
            session=session,
            attempt=attempt_count["n"],
        )

    try:
        return _attempt()
    except _TransientHTTPError as exc:
        raise TransientFeedError(
            f"Transient failure fetching {feed_url} after {attempt_count['n']} attempts: {exc}"
        ) from exc
    except RetryError as exc:
        raise TransientFeedError(
            f"Transient failure fetching {feed_url} after {attempt_count['n']} attempts: {exc}"
        ) from exc


def _fetch_once(
    feed_url: str,
    *,
    settings: Settings,
    session: requests.Session,
    attempt: int,
) -> bytes:
    """One HTTP attempt — translates lib errors to our typed exceptions."""
    started = time.monotonic()
    try:
        response = session.get(
            feed_url,
            headers={"User-Agent": settings.gtfs_user_agent},
            timeout=30,
        )
    except requests.Timeout as exc:
        latency_ms = (time.monotonic() - started) * 1000
        logger.warning(
            "gtfs-rt fetch timeout url=%s attempt=%d latency_ms=%.0f",
            feed_url,
            attempt,
            latency_ms,
        )
        raise _TransientHTTPError(f"timeout fetching {feed_url}") from exc
    except requests.ConnectionError as exc:
        latency_ms = (time.monotonic() - started) * 1000
        logger.warning(
            "gtfs-rt fetch connection error url=%s attempt=%d latency_ms=%.0f err=%s",
            feed_url,
            attempt,
            latency_ms,
            exc,
        )
        raise _TransientHTTPError(f"connection error fetching {feed_url}: {exc}") from exc
    except requests.RequestException as exc:
        latency_ms = (time.monotonic() - started) * 1000
        logger.error(
            "gtfs-rt fetch error url=%s attempt=%d latency_ms=%.0f err=%s",
            feed_url,
            attempt,
            latency_ms,
            exc,
        )
        raise PermanentFeedError(f"request failed for {feed_url}: {exc}") from exc

    latency_ms = (time.monotonic() - started) * 1000
    status = response.status_code
    logger.info(
        "gtfs-rt fetch url=%s status=%d attempt=%d latency_ms=%.0f bytes=%d",
        feed_url,
        status,
        attempt,
        latency_ms,
        len(response.content),
    )

    if 500 <= status < 600:
        raise _TransientHTTPError(f"{status} from {feed_url}")
    if 400 <= status < 500:
        raise PermanentFeedError(f"{status} from {feed_url}")
    response.raise_for_status()
    return response.content


class _TransientHTTPError(Exception):
    """Internal marker for tenacity to retry on. Wrapped to TransientFeedError externally."""


def _get_default_rate_limiter(settings: Settings) -> OutboundRateLimiter:
    global _DEFAULT_RATE_LIMITER
    if _DEFAULT_RATE_LIMITER is None:
        _DEFAULT_RATE_LIMITER = OutboundRateLimiter(
            interval_seconds=float(settings.gtfs_rt_fetch_interval_seconds)
        )
    return _DEFAULT_RATE_LIMITER
