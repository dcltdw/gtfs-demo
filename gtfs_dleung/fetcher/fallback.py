"""Hard-snapshot fallback — the bottom tier of the realtime data path.

The data path has three tiers, top to bottom:

1. **Live fetch** (:mod:`gtfs_dleung.fetcher.realtime`) — the happy path. Fresh
   bytes from MBTA's CDN.
2. **Soft cache** (:class:`gtfs_dleung.fetcher.health.HealthTrackedFetcher`) —
   the last successful `FeedMessage` per feed URL, in memory. Survives
   transient network failure during a session; lost on process restart.
3. **Hard snapshot** (this module) — committed `.pb` snapshots under
   ``examples/``. Survives process restart. Stale by design (captured days or
   weeks ago) — kept around so the demo stays usable even on a cold-start
   network outage.

Each tier produces an `is_degraded=True` `FeedHealth` on the way out, with the
``age_seconds`` reflecting the snapshot's `header.timestamp` (not the file's
mtime). That makes the Streamlit health panel honest about how stale the data
the user is currently looking at actually is.

Snapshots are populated by ``scripts/capture_snapshots.py`` (`just snapshot`).
Filename convention: ``<feed_type>_<YYYYMMDDTHHMMSSZ>.pb`` next to a `.json`
twin. The loader picks the most recent timestamp per feed.
"""

from __future__ import annotations

import logging
from pathlib import Path

from google.transit import gtfs_realtime_pb2

from gtfs_dleung.feeds import (
    SERVICE_ALERTS_URL,
    TRIP_UPDATES_URL,
    VEHICLE_POSITIONS_URL,
)
from gtfs_dleung.models.feed_health import FeedType

logger = logging.getLogger(__name__)


_URL_TO_FEED_TYPE: dict[str, FeedType] = {
    TRIP_UPDATES_URL: FeedType.TRIP_UPDATES,
    VEHICLE_POSITIONS_URL: FeedType.VEHICLE_POSITIONS,
    SERVICE_ALERTS_URL: FeedType.SERVICE_ALERTS,
}


def _repo_root() -> Path:
    """Walk up from this file until we hit the repo root (the ``examples/`` directory's parent)."""
    return Path(__file__).resolve().parent.parent.parent


def default_examples_dir() -> Path:
    """The committed snapshot directory at the repo root."""
    return _repo_root() / "examples"


def load_snapshot_fallback(
    feed_url: str,
    *,
    examples_dir: Path | None = None,
) -> gtfs_realtime_pb2.FeedMessage | None:
    """Return the most recent committed snapshot for ``feed_url``, or ``None``.

    ``examples_dir`` is injectable for tests. In production callers leave it as
    the default (``<repo_root>/examples``).
    """
    feed_type = _URL_TO_FEED_TYPE.get(feed_url)
    if feed_type is None:
        logger.warning("snapshot fallback: no known mapping for url=%s", feed_url)
        return None

    base = examples_dir or default_examples_dir()
    if not base.exists():
        logger.info("snapshot fallback: examples dir %s missing", base)
        return None

    candidates = sorted(base.glob(f"{feed_type.value}_*.pb"))
    if not candidates:
        logger.info(
            "snapshot fallback: no committed snapshot for feed_type=%s in %s",
            feed_type.value,
            base,
        )
        return None

    # Sorted lexicographically — our timestamp format (YYYYMMDDTHHMMSSZ) sorts as expected.
    chosen = candidates[-1]
    try:
        msg = gtfs_realtime_pb2.FeedMessage()
        msg.ParseFromString(chosen.read_bytes())
    except Exception as exc:  # corrupt snapshot - log and treat as missing
        logger.error("snapshot fallback: failed to decode %s: %s", chosen, exc)
        return None

    logger.info(
        "snapshot fallback: serving %s (feed_type=%s, header_ts=%s)",
        chosen.name,
        feed_type.value,
        msg.header.timestamp if msg.header.HasField("timestamp") else "n/a",
    )
    return msg


__all__ = (
    "default_examples_dir",
    "load_snapshot_fallback",
)
