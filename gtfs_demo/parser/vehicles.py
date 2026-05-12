"""Parse a GTFS-RT ``FeedMessage`` carrying VehiclePositions into typed rows.

Note the three id-like fields (see ``gtfs_demo.models.vehicle`` docstring): the
parser is careful to keep them distinct rather than collapsing one into another.

The feed is scope-filtered to the demo corridor's routes (``SCOPE_ROUTES``):
vehicles on out-of-scope routes are dropped. Route ID is read from the RT
message's TripDescriptor directly — no join with the static feed needed for
this PR. (The static feed could in principle resolve `trip_id → route_id` when
RT omits the route, but in practice MBTA's feed always carries it.)
"""

from __future__ import annotations

from datetime import UTC, datetime

from google.transit import gtfs_realtime_pb2

from gtfs_demo.models.vehicle import VehiclePosition, VehicleStatus
from gtfs_demo.scope import SCOPE_ROUTES

# Protobuf enum values for VehiclePosition.VehicleStopStatus.
_STATUS_INCOMING_AT = 0
_STATUS_STOPPED_AT = 1
_STATUS_IN_TRANSIT_TO = 2

_STATUS_MAP: dict[int, VehicleStatus] = {
    _STATUS_INCOMING_AT: VehicleStatus.INCOMING_AT,
    _STATUS_STOPPED_AT: VehicleStatus.STOPPED_AT,
    _STATUS_IN_TRANSIT_TO: VehicleStatus.IN_TRANSIT_TO,
}


def parse(
    feed_message: gtfs_realtime_pb2.FeedMessage,
    *,
    scope_routes: frozenset[str] = SCOPE_ROUTES,
) -> list[VehiclePosition]:
    """Return one :class:`VehiclePosition` per in-scope vehicle entity.

    ``scope_routes`` is injectable for tests. Vehicles with a missing
    ``route_id`` or a route outside the scope are dropped.
    """
    out: list[VehiclePosition] = []
    for entity in feed_message.entity:
        if not entity.HasField("vehicle"):
            continue
        position = entity.vehicle
        trip_id = position.trip.trip_id or None
        route_id = position.trip.route_id or None
        if route_id is None or route_id not in scope_routes:
            continue

        out.append(
            VehiclePosition(
                vehicle_id=position.vehicle.id,
                vehicle_label=position.vehicle.label or None,
                trip_id=trip_id,
                route_id=route_id,
                latitude=position.position.latitude
                if position.HasField("position") and position.position.HasField("latitude")
                else None,
                longitude=position.position.longitude
                if position.HasField("position") and position.position.HasField("longitude")
                else None,
                bearing=position.position.bearing
                if position.HasField("position") and position.position.HasField("bearing")
                else None,
                current_status=_STATUS_MAP.get(position.current_status)
                if position.HasField("current_status")
                else None,
                current_stop_sequence=position.current_stop_sequence
                if position.HasField("current_stop_sequence")
                else None,
                timestamp=datetime.fromtimestamp(position.timestamp, tz=UTC)
                if position.HasField("timestamp")
                else None,
            )
        )
    return out


__all__ = ("parse",)
