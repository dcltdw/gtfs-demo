"""Domain model for arrivals — the output of the TripUpdates parser.

The ``ScheduleRelationship`` enum is a *user-facing* synthesis of two GTFS-RT
enums (trip-level and stop-level). Both are flattened into one label so the
arrivals board can show a single status per row.

- ``SCHEDULED``: trip is on its static schedule (possibly with delay).
- ``ADDED``: trip is added at runtime; not in the static feed (`is_added=True`).
- ``UNSCHEDULED``: trip running, but not normally part of the schedule
  (e.g. shuttle bus, rescue trip).
- ``CANCELED``: the trip is canceled — every stop on it is flagged.
- ``SKIPPED``: this specific stop on the trip is skipped, even though the trip
  itself is running.

The presenter filters CANCELED + SKIPPED out of the default "next N" view by
convention, but the parser returns them so the alerts panel (#7) can surface them.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ScheduleRelationship(StrEnum):
    """Synthesised trip+stop relationship label. See module docstring."""

    SCHEDULED = "SCHEDULED"
    ADDED = "ADDED"
    UNSCHEDULED = "UNSCHEDULED"
    CANCELED = "CANCELED"
    SKIPPED = "SKIPPED"


class Arrival(BaseModel):
    """One predicted (or scheduled, if no RT update) stop-time on a trip."""

    model_config = ConfigDict(frozen=True)

    stop_id: str
    """Platform-level ``stop_id`` straight from the static feed (e.g. ``70063`` for
    Davis-southbound). The Streamlit page typically filters by ``parent_station``
    instead — see :attr:`parent_station`."""

    parent_station: str | None = None
    """The parent station ID (e.g. ``place-davis``) when ``stop_id`` is a
    platform-level stop. ``None`` when the stop has no parent (the stop itself is
    a top-level station). Populated by the parser via a static-feed lookup; lets
    the presenter filter by station name without having to enumerate platform IDs."""

    stop_name: str | None
    route_id: str
    trip_id: str
    direction_id: int | None = None
    """Per the GTFS spec, ``0`` and ``1`` identify the two directions of a route;
    the *meaning* (north/south/inbound/outbound) is per-route and lives in MBTA's
    ``directions.txt`` extension. For the demo's two stations (Davis and Ball Sq,
    both north of Park St), ``0`` is inbound (toward downtown) and ``1`` is
    outbound — see :func:`gtfs_dleung.presenter.formatters.direction_label`."""

    trip_headsign: str | None = None
    """The rider-facing destination label from the static feed
    (e.g. ``"Alewife"`` for Red Line northbound). ``None`` for ADDED trips that
    don't appear in the static feed."""

    scheduled_at: datetime | None
    """Static schedule time for this stop, in America/New_York. ``None`` for ADDED
    trips that the static feed doesn't know about."""

    predicted_at: datetime | None
    """RT-adjusted time for this stop, in America/New_York. May equal
    ``scheduled_at`` if no delay info is available."""

    delay_seconds: int | None
    """Positive = late; negative = early; ``None`` if no RT update covers this stop
    and no explicit zero was given."""

    schedule_relationship: ScheduleRelationship = ScheduleRelationship.SCHEDULED
    is_added: bool = False
    """``True`` for trips referenced by RT but absent from the static feed."""
