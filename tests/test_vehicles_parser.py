"""Tests for ``gtfs_dleung.parser.vehicles.parse``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from google.transit import gtfs_realtime_pb2

from gtfs_dleung.models.vehicle import VehicleStatus
from gtfs_dleung.parser.vehicles import parse
from tests.helpers import make_vehiclepositions_feed


def test_basic_parse() -> None:
    """A single in-scope vehicle round-trips through the parser with all fields populated."""
    feed = make_vehiclepositions_feed(
        vehicles=[
            {
                "vehicle_id": "y1234",
                "vehicle_label": "1701",
                "trip_id": "T-abc",
                "route_id": "Red",
                "lat": 42.3563946,
                "lon": -71.0624242,
                "bearing": 270.0,
                "current_status": "IN_TRANSIT_TO",
                "current_stop_sequence": 5,
                "timestamp": 1_750_000_000,
            }
        ]
    )

    rows = parse(feed)

    assert len(rows) == 1
    vp = rows[0]
    assert vp.vehicle_id == "y1234"
    assert vp.vehicle_label == "1701"
    assert vp.trip_id == "T-abc"
    assert vp.route_id == "Red"
    assert vp.latitude == pytest.approx(42.3563946, rel=1e-6)
    assert vp.longitude == pytest.approx(-71.0624242, rel=1e-6)
    assert vp.bearing == pytest.approx(270.0)
    assert vp.current_status == VehicleStatus.IN_TRANSIT_TO
    assert vp.current_stop_sequence == 5
    assert vp.timestamp == datetime.fromtimestamp(1_750_000_000, tz=UTC)


def test_filters_to_scope_routes() -> None:
    """Vehicles on out-of-scope routes are dropped; in-scope are kept."""
    feed = make_vehiclepositions_feed(
        vehicles=[
            {"vehicle_id": "v1", "route_id": "Red", "trip_id": "T-red"},
            {"vehicle_id": "v2", "route_id": "Green-E", "trip_id": "T-ge"},
            {"vehicle_id": "v3", "route_id": "Green-B", "trip_id": "T-gb"},
            {"vehicle_id": "v4", "route_id": "39", "trip_id": "T-bus"},
            {"vehicle_id": "v5", "route_id": "CR-Worcester", "trip_id": "T-cr"},
            {"vehicle_id": "v6"},  # no trip → no route_id → dropped
        ]
    )

    rows = parse(feed)
    ids = {r.vehicle_id for r in rows}

    assert ids == {"v1", "v2"}


def test_current_status_enum_mapping() -> None:
    """The three protobuf status values map to the right enum members."""
    feed = make_vehiclepositions_feed(
        vehicles=[
            {"vehicle_id": "v1", "route_id": "Red", "current_status": "INCOMING_AT"},
            {"vehicle_id": "v2", "route_id": "Red", "current_status": "STOPPED_AT"},
            {"vehicle_id": "v3", "route_id": "Red", "current_status": "IN_TRANSIT_TO"},
        ]
    )

    statuses = {r.vehicle_id: r.current_status for r in parse(feed)}

    assert statuses == {
        "v1": VehicleStatus.INCOMING_AT,
        "v2": VehicleStatus.STOPPED_AT,
        "v3": VehicleStatus.IN_TRANSIT_TO,
    }


def test_id_label_trip_id_are_distinct() -> None:
    """Conflating ``vehicle.id`` / ``vehicle.label`` / ``trip_id`` is a beginner bug; assert it doesn't happen."""
    feed = make_vehiclepositions_feed(
        vehicles=[
            {
                "vehicle_id": "system-internal-12345",
                "vehicle_label": "1701",
                "trip_id": "trip-678",
                "route_id": "Red",
            }
        ]
    )

    vp = parse(feed)[0]

    assert vp.vehicle_id == "system-internal-12345"
    assert vp.vehicle_label == "1701"
    assert vp.trip_id == "trip-678"
    assert vp.vehicle_id != vp.vehicle_label
    assert vp.vehicle_id != vp.trip_id
    assert vp.vehicle_label != vp.trip_id


def test_parses_real_fixture() -> None:
    """The committed real-feed fixture decodes + scope-filters to Red + Green-E only."""
    fixture = Path(__file__).parent / "fixtures" / "vehiclepositions_sample.pb"
    msg = gtfs_realtime_pb2.FeedMessage()
    msg.ParseFromString(fixture.read_bytes())

    rows = parse(msg)
    kept_routes = {r.route_id for r in rows}

    assert kept_routes <= {"Red", "Green-E"}
    assert len(rows) > 0
