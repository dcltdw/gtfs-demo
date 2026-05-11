"""Domain model for vehicle positions — output of the VehiclePositions parser.

Three id-like fields appear on each row and are easy to confuse — they mean
different things:

- ``vehicle_id``: the **transport-system-internal** vehicle identifier
  (``VehicleDescriptor.id``). Stable across trips; a serial-number-like value.
  Used internally by ops; not rider-facing.
- ``vehicle_label``: the **rider-facing** label
  (``VehicleDescriptor.label``) — e.g. ``"1701"`` painted on the side of an
  MBTA car. Typically what a rider would report ("the train numbered 1701").
- ``trip_id``: the **trip** the vehicle is currently running
  (``TripDescriptor.trip_id``). One trip is run by different vehicles on
  different days; conflating ``trip_id`` with vehicle identity is a beginner
  mistake.

The ``VehicleStatus`` enum maps the three values
``VehiclePosition.VehicleStopStatus`` defines:

- ``INCOMING_AT``: vehicle is about to arrive at the stop indicated by
  ``current_stop_sequence``.
- ``STOPPED_AT``: vehicle is currently stopped at that stop.
- ``IN_TRANSIT_TO``: vehicle is en route to that stop.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class VehicleStatus(StrEnum):
    """Per-vehicle stop status. See module docstring."""

    INCOMING_AT = "INCOMING_AT"
    STOPPED_AT = "STOPPED_AT"
    IN_TRANSIT_TO = "IN_TRANSIT_TO"


class VehiclePosition(BaseModel):
    """One vehicle's position + status snapshot from the GTFS-RT feed."""

    model_config = ConfigDict(frozen=True)

    vehicle_id: str
    """Transport-system-internal ID (``VehicleDescriptor.id``)."""

    vehicle_label: str | None
    """Rider-facing label (``VehicleDescriptor.label``), e.g. ``"1701"``."""

    trip_id: str | None
    """Trip the vehicle is currently running. ``None`` for vehicles between trips."""

    route_id: str | None
    """Route currently being served. Used for the scope filter."""

    latitude: float | None
    longitude: float | None
    bearing: float | None
    """Compass heading in degrees, 0 = north. ``None`` when the feed omits it."""

    current_status: VehicleStatus | None
    current_stop_sequence: int | None
    """The trip's stop-sequence index this status refers to."""

    timestamp: datetime | None
    """Feed-side observation time, in UTC. ``None`` if the feed omits it."""
