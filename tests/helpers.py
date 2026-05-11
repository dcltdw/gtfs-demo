"""Test helpers: programmatic builders for GTFS-RT messages and tiny static feeds.

The protobuf API is verbose; these helpers let tests express scenarios in
dict-like form. Not used in production code — keep it in ``tests/``.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from google.transit import gtfs_realtime_pb2

from gtfs_dleung.models.static import Route, StaticFeed, Stop, StopTime, Trip

# Trip-level ScheduleRelationship enum values (gtfs-realtime.proto).
TripSR = Literal["SCHEDULED", "ADDED", "UNSCHEDULED", "CANCELED"]
_TRIP_SR_VALUES: dict[TripSR, int] = {
    "SCHEDULED": 0,
    "ADDED": 1,
    "UNSCHEDULED": 2,
    "CANCELED": 3,
}

# Stop-level ScheduleRelationship enum values.
StopSR = Literal["SCHEDULED", "SKIPPED", "NO_DATA", "UNSCHEDULED"]
_STOP_SR_VALUES: dict[StopSR, int] = {
    "SCHEDULED": 0,
    "SKIPPED": 1,
    "NO_DATA": 2,
    "UNSCHEDULED": 3,
}


def make_tripupdate_feed(
    *,
    trips: list[dict[str, Any]],
    feed_timestamp: int = 0,
) -> gtfs_realtime_pb2.FeedMessage:
    """Build a ``FeedMessage`` with one ``trip_update`` entity per trip.

    Each ``trips`` entry is a dict with keys:

    - ``trip_id`` (required)
    - ``route_id`` (default empty string)
    - ``start_date`` (``YYYYMMDD``, optional)
    - ``schedule_relationship`` (one of ``TripSR`` strings; default SCHEDULED)
    - ``stop_time_updates``: list of dicts with keys
      ``stop_id`` and/or ``stop_sequence``, ``delay`` (seconds, optional),
      ``time`` (unix seconds, optional), ``schedule_relationship``
      (``StopSR``, optional).
    """
    msg = gtfs_realtime_pb2.FeedMessage()
    msg.header.gtfs_realtime_version = "2.0"
    msg.header.incrementality = 0  # FULL_DATASET
    if feed_timestamp:
        msg.header.timestamp = feed_timestamp

    for i, trip in enumerate(trips):
        entity = msg.entity.add()
        entity.id = f"entity-{i}"
        tu = entity.trip_update
        tu.trip.trip_id = trip["trip_id"]
        tu.trip.route_id = trip.get("route_id", "")
        if "start_date" in trip:
            tu.trip.start_date = trip["start_date"]
        sr = trip.get("schedule_relationship", "SCHEDULED")
        tu.trip.schedule_relationship = _TRIP_SR_VALUES[sr]

        for stu_spec in trip.get("stop_time_updates", []):
            stu = tu.stop_time_update.add()
            if "stop_id" in stu_spec:
                stu.stop_id = stu_spec["stop_id"]
            if "stop_sequence" in stu_spec:
                stu.stop_sequence = stu_spec["stop_sequence"]
            if "schedule_relationship" in stu_spec:
                stu.schedule_relationship = _STOP_SR_VALUES[stu_spec["schedule_relationship"]]
            if "delay" in stu_spec:
                stu.arrival.delay = stu_spec["delay"]
            if "time" in stu_spec:
                stu.arrival.time = stu_spec["time"]
    return msg


# Vehicle stop status enum values.
VehicleStopStatus = Literal["INCOMING_AT", "STOPPED_AT", "IN_TRANSIT_TO"]
_VEHICLE_STATUS_VALUES: dict[VehicleStopStatus, int] = {
    "INCOMING_AT": 0,
    "STOPPED_AT": 1,
    "IN_TRANSIT_TO": 2,
}


def make_vehiclepositions_feed(
    *,
    vehicles: list[dict[str, Any]],
    feed_timestamp: int = 0,
) -> gtfs_realtime_pb2.FeedMessage:
    """Build a ``FeedMessage`` with one ``vehicle`` entity per dict.

    Each ``vehicles`` entry is a dict with keys:

    - ``vehicle_id`` (required) — sets ``VehicleDescriptor.id``.
    - ``vehicle_label`` (optional) — sets ``VehicleDescriptor.label``.
    - ``trip_id`` (optional) — sets ``TripDescriptor.trip_id``.
    - ``route_id`` (optional) — sets ``TripDescriptor.route_id``.
    - ``lat`` / ``lon`` (optional) — set ``Position.latitude`` / ``.longitude``.
    - ``bearing`` (optional).
    - ``current_status`` (``VehicleStopStatus`` literal, optional).
    - ``current_stop_sequence`` (optional).
    - ``timestamp`` (unix-seconds int, optional).
    """
    msg = gtfs_realtime_pb2.FeedMessage()
    msg.header.gtfs_realtime_version = "2.0"
    msg.header.incrementality = 0
    if feed_timestamp:
        msg.header.timestamp = feed_timestamp

    for i, v in enumerate(vehicles):
        entity = msg.entity.add()
        entity.id = f"vehicle-{i}"
        vp = entity.vehicle
        vp.vehicle.id = v["vehicle_id"]
        if "vehicle_label" in v:
            vp.vehicle.label = v["vehicle_label"]
        if "trip_id" in v:
            vp.trip.trip_id = v["trip_id"]
        if "route_id" in v:
            vp.trip.route_id = v["route_id"]
        if "lat" in v:
            vp.position.latitude = v["lat"]
        if "lon" in v:
            vp.position.longitude = v["lon"]
        if "bearing" in v:
            vp.position.bearing = v["bearing"]
        if "current_status" in v:
            vp.current_status = _VEHICLE_STATUS_VALUES[v["current_status"]]
        if "current_stop_sequence" in v:
            vp.current_stop_sequence = v["current_stop_sequence"]
        if "timestamp" in v:
            vp.timestamp = v["timestamp"]
    return msg


def make_static_feed(
    *,
    routes: list[dict[str, Any]] | None = None,
    stops: list[dict[str, Any]] | None = None,
    trips: list[dict[str, Any]] | None = None,
    stop_times: list[dict[str, Any]] | None = None,
) -> StaticFeed:
    """Build a minimal :class:`StaticFeed` from Python dicts.

    Each list item is a dict matching the corresponding Pydantic model's fields.
    """
    return StaticFeed(
        routes=[Route(**r) for r in (routes or [])],
        stops=[Stop(**s) for s in (stops or [])],
        trips=[Trip(**t) for t in (trips or [])],
        stop_times=[StopTime(**st) for st in (stop_times or [])],
        shapes=[],
    )


def yyyymmdd(d: date) -> str:
    """Format a ``date`` as the GTFS service-date string."""
    return d.strftime("%Y%m%d")
