"""Domain model for feed-health bookkeeping.

A ``FeedHealth`` row captures *both* the freshness of the most recently received
``FeedMessage`` (``age_seconds`` + ``is_stale``) and the success of the most
recent fetch attempt (``last_success_at`` + ``is_degraded``). The two are
related but distinct:

- ``is_stale``: the **data** is old. MBTA publishes every ~5s, so >30s
  indicates the publisher (not us) has a problem.
- ``is_degraded``: **our** fetch is failing. The data we're serving is
  whatever we last got — possibly fresh data over a now-broken connection.

The Streamlit UI uses both to drive the feed-health panel: stale data shows
yellow; degraded fetch shows orange; both true shows red.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class FeedType(StrEnum):
    """The three GTFS-RT feeds the spike consumes."""

    TRIP_UPDATES = "trip_updates"
    VEHICLE_POSITIONS = "vehicle_positions"
    SERVICE_ALERTS = "service_alerts"


class FeedHealth(BaseModel):
    """Snapshot of one feed's health at a moment in time."""

    model_config = ConfigDict(frozen=True)

    feed_type: FeedType
    feed_url: str
    age_seconds: float | None
    """Seconds between ``now`` and the most recently received message's
    ``header.timestamp``. ``None`` if no message has been received yet, or if
    the feed omits a header timestamp."""

    is_stale: bool
    """``True`` iff ``age_seconds`` exceeds the configured threshold."""

    last_success_at: datetime | None
    """Wall-clock UTC of our last successful fetch. ``None`` until the first
    success."""

    is_degraded: bool
    """``True`` iff the most recent fetch attempt **failed** and the caller is
    being served stale-cached data. Independent of ``is_stale``: a fresh feed
    can be degraded if the network broke after the last good fetch."""
