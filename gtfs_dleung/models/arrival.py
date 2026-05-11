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
    stop_name: str | None
    route_id: str
    trip_id: str
    direction_id: int | None = None

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
