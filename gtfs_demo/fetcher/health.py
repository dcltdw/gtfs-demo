"""Health-aware wrapper around ``fetch_feed`` — staleness + degradation + metrics.

The bare :func:`gtfs_demo.fetcher.realtime.fetch_feed` is stateless: it returns
a ``FeedMessage`` or raises. The Streamlit page needs more: when a fetch fails,
keep serving the last good message; when the feed's header timestamp drifts
behind, flag the data as stale.

This module adds three pieces of state to the fetcher path:

1. **Last-success cache**: per-feed ``FeedMessage`` + the wall-clock at which we
   received it. Survives subsequent failures.
2. **Staleness state**: previous fresh/stale flag per feed, so we can emit a
   single structured log line on each transition rather than every fetch.
3. **Metrics**: per-feed counters (``fetches_total``, ``fetch_errors_total``)
   and gauge (``feed_age_seconds``). The Streamlit feed-health panel reads
   this dict directly; a Prometheus exporter (post-demo #33) will translate.

The module exposes a class (:class:`HealthTrackedFetcher`) for tests to
instantiate directly, plus a module-level singleton + thin wrapper functions
that match the public API the issue specifies.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Any

from google.transit import gtfs_realtime_pb2

from gtfs_demo.config import Settings, get_settings
from gtfs_demo.feeds import (
    SERVICE_ALERTS_URL,
    TRIP_UPDATES_URL,
    VEHICLE_POSITIONS_URL,
)
from gtfs_demo.fetcher.fallback import load_snapshot_fallback
from gtfs_demo.fetcher.realtime import FeedFetchError, fetch_feed
from gtfs_demo.models.feed_health import FeedHealth, FeedType

logger = logging.getLogger(__name__)


_URL_TO_FEED_TYPE: dict[str, FeedType] = {
    TRIP_UPDATES_URL: FeedType.TRIP_UPDATES,
    VEHICLE_POSITIONS_URL: FeedType.VEHICLE_POSITIONS,
    SERVICE_ALERTS_URL: FeedType.SERVICE_ALERTS,
}


class HealthTrackedFetcher:
    """Wraps :func:`fetch_feed` with last-success caching + staleness tracking + metrics."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        fetch_fn: Any = None,
        now_fn: Any = None,
        snapshot_loader: Any = None,
    ) -> None:
        """Constructor.

        ``fetch_fn`` overrides the default :func:`fetch_feed` (useful in tests).
        ``now_fn`` overrides ``datetime.now(tz=UTC)`` (useful in tests).
        ``snapshot_loader`` overrides the default
        :func:`gtfs_demo.fetcher.fallback.load_snapshot_fallback`. Pass
        ``lambda _url: None`` to disable hard-snapshot fallback entirely.
        """
        self._settings = settings or get_settings()
        self._fetch_fn = fetch_fn or fetch_feed
        self._now_fn = now_fn or (lambda: datetime.now(tz=UTC))
        self._snapshot_loader = snapshot_loader or load_snapshot_fallback

        self._cache: dict[str, gtfs_realtime_pb2.FeedMessage] = {}
        self._last_success_at: dict[str, datetime] = {}
        self._last_message_timestamp: dict[str, datetime | None] = {}
        self._stale_state: dict[str, bool] = {}
        self._is_degraded: dict[str, bool] = {}
        self._serving_from_snapshot: dict[str, bool] = {}
        self._metrics: dict[str, dict[str, int | float]] = {}
        self._lock = threading.Lock()

    # ---- core ----------------------------------------------------------------

    def fetch(self, feed_url: str) -> tuple[gtfs_realtime_pb2.FeedMessage, FeedHealth]:
        """Fetch a feed; on failure, return the cached last-good message + degraded health.

        Raises ``FeedFetchError`` only if the fetch fails **and** there is no cache
        to fall back to (i.e. the very first attempt failed).
        """
        with self._lock:
            self._metrics.setdefault(feed_url, self._zero_metrics())
            self._metrics[feed_url]["fetches_total"] += 1
        try:
            msg = self._fetch_fn(feed_url, settings=self._settings)
        except FeedFetchError:
            with self._lock:
                self._metrics[feed_url]["fetch_errors_total"] += 1
            if feed_url in self._cache:
                with self._lock:
                    self._is_degraded[feed_url] = True
                health = self._compute_health(feed_url)
                logger.warning(
                    "feed fetch failed, serving cached message url=%s age_seconds=%s",
                    feed_url,
                    health.age_seconds,
                )
                return self._cache[feed_url], health
            # No in-memory cache. Try the hard-snapshot fallback (#13).
            snapshot = self._snapshot_loader(feed_url)
            if snapshot is not None:
                with self._lock:
                    self._cache[feed_url] = snapshot
                    self._is_degraded[feed_url] = True
                    self._serving_from_snapshot[feed_url] = True
                    if snapshot.header.HasField("timestamp"):
                        self._last_message_timestamp[feed_url] = datetime.fromtimestamp(
                            snapshot.header.timestamp, tz=UTC
                        )
                    else:
                        self._last_message_timestamp[feed_url] = None
                health = self._compute_health(feed_url)
                logger.warning(
                    "feed fetch failed AND no in-memory cache; serving snapshot "
                    "url=%s age_seconds=%s",
                    feed_url,
                    health.age_seconds,
                )
                return snapshot, health
            raise

        # Success path.
        with self._lock:
            self._cache[feed_url] = msg
            self._last_success_at[feed_url] = self._now_fn()
            self._is_degraded[feed_url] = False
            self._serving_from_snapshot[feed_url] = False
            if msg.header.HasField("timestamp"):
                self._last_message_timestamp[feed_url] = datetime.fromtimestamp(
                    msg.header.timestamp, tz=UTC
                )
            else:
                self._last_message_timestamp[feed_url] = None

        health = self._compute_health(feed_url)
        self._log_staleness_transition(feed_url, health.is_stale)
        with self._lock:
            self._metrics[feed_url]["feed_age_seconds"] = health.age_seconds or 0.0
        return msg, health

    # ---- API ----------------------------------------------------------------

    def get_health(self) -> dict[FeedType, FeedHealth]:
        """Return current health for every known feed URL keyed by ``FeedType``."""
        out: dict[FeedType, FeedHealth] = {}
        for url in self._cache:
            ft = _URL_TO_FEED_TYPE.get(url)
            if ft is None:
                continue
            out[ft] = self._compute_health(url)
        return out

    def get_metrics(self) -> dict[str, dict[str, int | float]]:
        """Return a snapshot of the metrics dict keyed by feed URL.

        Future: a Prometheus exporter (post-demo #33) translates these dicts to
        the Prometheus text-format. For now, the Streamlit feed-health panel
        consumes them directly.
        """
        # Shallow-copy so callers can't mutate our state.
        with self._lock:
            return {url: dict(m) for url, m in self._metrics.items()}

    # ---- internals ----------------------------------------------------------

    @staticmethod
    def _zero_metrics() -> dict[str, int | float]:
        return {"fetches_total": 0, "fetch_errors_total": 0, "feed_age_seconds": 0.0}

    def _compute_health(self, feed_url: str) -> FeedHealth:
        feed_type = _URL_TO_FEED_TYPE.get(feed_url, FeedType.TRIP_UPDATES)
        ts = self._last_message_timestamp.get(feed_url)
        if ts is None:
            age_seconds: float | None = None
            is_stale = False
        else:
            age_seconds = (self._now_fn() - ts).total_seconds()
            is_stale = age_seconds > self._threshold_for(feed_type)
        return FeedHealth(
            feed_type=feed_type,
            feed_url=feed_url,
            age_seconds=age_seconds,
            is_stale=is_stale,
            last_success_at=self._last_success_at.get(feed_url),
            is_degraded=self._is_degraded.get(feed_url, False),
            is_snapshot=self._serving_from_snapshot.get(feed_url, False),
        )

    def _threshold_for(self, feed_type: FeedType) -> int:
        """Pick the per-feed staleness threshold. See ``Settings`` for the rationale."""
        if feed_type is FeedType.SERVICE_ALERTS:
            return self._settings.gtfs_service_alerts_stale_s
        if feed_type is FeedType.VEHICLE_POSITIONS:
            return self._settings.gtfs_vehicle_positions_stale_s
        return self._settings.gtfs_trip_updates_stale_s

    def _log_staleness_transition(self, feed_url: str, is_stale_now: bool) -> None:
        was_stale = self._stale_state.get(feed_url, False)
        if was_stale != is_stale_now:
            logger.info(
                "feed staleness transition url=%s direction=%s",
                feed_url,
                "stale" if is_stale_now else "fresh",
            )
            self._stale_state[feed_url] = is_stale_now


# ---- module-level singleton + thin wrappers (the public API per the issue) ---

_DEFAULT_TRACKER: HealthTrackedFetcher | None = None
_DEFAULT_TRACKER_LOCK = threading.Lock()


def _get_default_tracker() -> HealthTrackedFetcher:
    global _DEFAULT_TRACKER
    with _DEFAULT_TRACKER_LOCK:
        if _DEFAULT_TRACKER is None:
            _DEFAULT_TRACKER = HealthTrackedFetcher()
        return _DEFAULT_TRACKER


def fetch_with_health(feed_url: str) -> tuple[gtfs_realtime_pb2.FeedMessage, FeedHealth]:
    """Convenience wrapper around the singleton's :meth:`HealthTrackedFetcher.fetch`."""
    return _get_default_tracker().fetch(feed_url)


def get_feed_health() -> dict[FeedType, FeedHealth]:
    """Return the singleton tracker's per-feed health snapshot."""
    return _get_default_tracker().get_health()


def get_metrics() -> dict[str, dict[str, int | float]]:
    """Return the singleton tracker's metrics dict.

    TODO: a Prometheus ``/metrics`` endpoint that translates this to the
    Prometheus text-format is tracked as post-demo issue #33.
    """
    return _get_default_tracker().get_metrics()


def reset_tracker_for_tests() -> None:
    """Clear the singleton so tests start from a known state.

    Intended for ``conftest.py`` or per-test setup; do not call from production code.
    """
    global _DEFAULT_TRACKER
    with _DEFAULT_TRACKER_LOCK:
        _DEFAULT_TRACKER = None


__all__ = (
    "HealthTrackedFetcher",
    "fetch_with_health",
    "get_feed_health",
    "get_metrics",
    "reset_tracker_for_tests",
)
