"""Tests for ``gtfs_demo.parser.tripupdates.parse``."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from gtfs_demo.models.arrival import ScheduleRelationship
from gtfs_demo.models.static import StaticFeed
from gtfs_demo.parser.tripupdates import parse
from tests.helpers import make_static_feed, make_tripupdate_feed, yyyymmdd

SERVICE_DATE = date(2026, 5, 11)
TZ = ZoneInfo("America/New_York")


def _three_stop_trip_feed() -> StaticFeed:
    """A trivial static feed: route Red, trip T1, stops P/D/B at 08:00 / 08:10 / 08:20."""
    return make_static_feed(
        routes=[{"route_id": "Red", "route_type": 1}],
        stops=[
            {"stop_id": "P", "stop_name": "Park Street"},
            {"stop_id": "D", "stop_name": "Davis"},
            {"stop_id": "B", "stop_name": "Ball Square"},
        ],
        trips=[{"route_id": "Red", "service_id": "S1", "trip_id": "T1", "direction_id": 1}],
        stop_times=[
            {"trip_id": "T1", "arrival_time": "08:00:00", "stop_id": "P", "stop_sequence": 1},
            {"trip_id": "T1", "arrival_time": "08:10:00", "stop_id": "D", "stop_sequence": 2},
            {"trip_id": "T1", "arrival_time": "08:20:00", "stop_id": "B", "stop_sequence": 3},
        ],
    )


def test_parses_basic_arrival() -> None:
    static = _three_stop_trip_feed()
    rt = make_tripupdate_feed(
        trips=[
            {
                "trip_id": "T1",
                "route_id": "Red",
                "start_date": yyyymmdd(SERVICE_DATE),
                "stop_time_updates": [{"stop_id": "P", "delay": 60}],
            }
        ]
    )

    arrivals = parse(rt, static)

    assert len(arrivals) == 3
    park = arrivals[0]
    assert park.stop_id == "P"
    assert park.stop_name == "Park Street"
    assert park.route_id == "Red"
    assert park.trip_id == "T1"
    assert park.direction_id == 1
    assert park.scheduled_at == datetime(2026, 5, 11, 8, 0, tzinfo=TZ)
    assert park.predicted_at == datetime(2026, 5, 11, 8, 1, tzinfo=TZ)
    assert park.delay_seconds == 60
    assert park.schedule_relationship == ScheduleRelationship.SCHEDULED
    assert park.is_added is False


def test_handles_canceled_trip() -> None:
    static = _three_stop_trip_feed()
    rt = make_tripupdate_feed(
        trips=[
            {
                "trip_id": "T1",
                "route_id": "Red",
                "start_date": yyyymmdd(SERVICE_DATE),
                "schedule_relationship": "CANCELED",
            }
        ]
    )

    arrivals = parse(rt, static)

    assert len(arrivals) == 3, "CANCELED trips are returned (flagged), not dropped"
    for a in arrivals:
        assert a.schedule_relationship == ScheduleRelationship.CANCELED


def test_partial_stop_time_update_propagates() -> None:
    """An explicit delay on stop D propagates to stop B (downstream, no explicit update)."""
    static = _three_stop_trip_feed()
    rt = make_tripupdate_feed(
        trips=[
            {
                "trip_id": "T1",
                "route_id": "Red",
                "start_date": yyyymmdd(SERVICE_DATE),
                "stop_time_updates": [{"stop_id": "D", "delay": 120}],
            }
        ]
    )

    arrivals = parse(rt, static)
    by_stop = {a.stop_id: a for a in arrivals}

    # P is upstream of the explicit update — no propagation backward.
    assert by_stop["P"].delay_seconds is None
    assert by_stop["P"].predicted_at == by_stop["P"].scheduled_at

    # D has the explicit delay.
    assert by_stop["D"].delay_seconds == 120
    assert by_stop["D"].predicted_at == datetime(2026, 5, 11, 8, 12, tzinfo=TZ)

    # B is downstream — inherits D's delay.
    assert by_stop["B"].delay_seconds == 120
    assert by_stop["B"].predicted_at == datetime(2026, 5, 11, 8, 22, tzinfo=TZ)


def test_added_trip_surfaces_with_flag() -> None:
    """A trip whose ``trip_id`` is absent from the static feed is flagged ``is_added``."""
    static = make_static_feed(
        routes=[{"route_id": "Green-E", "route_type": 0}],
        stops=[{"stop_id": "X", "stop_name": "Phantom Stop"}],
    )
    rt = make_tripupdate_feed(
        trips=[
            {
                "trip_id": "T-PHANTOM",
                "route_id": "Green-E",
                "schedule_relationship": "ADDED",
                "stop_time_updates": [{"stop_id": "X", "time": 1_750_000_000}],
            }
        ]
    )

    arrivals = parse(rt, static)

    assert len(arrivals) == 1
    a = arrivals[0]
    assert a.is_added is True
    assert a.trip_id == "T-PHANTOM"
    assert a.stop_id == "X"
    assert a.stop_name == "Phantom Stop"
    assert a.schedule_relationship == ScheduleRelationship.ADDED
    assert a.scheduled_at is None
    assert a.predicted_at == datetime.fromtimestamp(1_750_000_000, tz=TZ)


def test_skipped_stop_is_flagged_individually() -> None:
    """SKIPPED is a stop-level signal — other stops on the same trip stay SCHEDULED."""
    static = _three_stop_trip_feed()
    rt = make_tripupdate_feed(
        trips=[
            {
                "trip_id": "T1",
                "route_id": "Red",
                "start_date": yyyymmdd(SERVICE_DATE),
                "stop_time_updates": [
                    {"stop_id": "D", "schedule_relationship": "SKIPPED"},
                ],
            }
        ]
    )

    arrivals = parse(rt, static)
    by_stop = {a.stop_id: a for a in arrivals}
    assert by_stop["P"].schedule_relationship == ScheduleRelationship.SCHEDULED
    assert by_stop["D"].schedule_relationship == ScheduleRelationship.SKIPPED
    assert by_stop["B"].schedule_relationship == ScheduleRelationship.SCHEDULED


def test_parent_station_name_preferred_over_platform_name() -> None:
    """When a stop has a parent_station with a name, that's the user-facing label."""
    static = make_static_feed(
        routes=[{"route_id": "Red", "route_type": 1}],
        stops=[
            {"stop_id": "place-pktrm", "stop_name": "Park Street"},
            {
                "stop_id": "70075",
                "stop_name": "Park Street - Red Line",
                "parent_station": "place-pktrm",
            },
        ],
        trips=[{"route_id": "Red", "service_id": "S1", "trip_id": "T1"}],
        stop_times=[
            {"trip_id": "T1", "arrival_time": "08:00:00", "stop_id": "70075", "stop_sequence": 1},
        ],
    )
    rt = make_tripupdate_feed(
        trips=[{"trip_id": "T1", "route_id": "Red", "start_date": yyyymmdd(SERVICE_DATE)}]
    )

    arrivals = parse(rt, static)
    assert arrivals[0].stop_name == "Park Street"


def test_arrival_carries_parent_station() -> None:
    """For a platform-level stop with a parent in static, ``Arrival.parent_station`` is populated.

    Pins the fix for #60 — without ``parent_station``, ``next_n_arrivals(..., "place-davis")``
    can't match Arrival rows whose ``stop_id`` is a platform-level ID like ``70064``.
    """
    static = make_static_feed(
        routes=[{"route_id": "Red", "route_type": 1}],
        stops=[
            {"stop_id": "place-davis", "stop_name": "Davis"},
            {
                "stop_id": "70064",
                "stop_name": "Davis - Red Line - Alewife",
                "parent_station": "place-davis",
            },
        ],
        trips=[{"route_id": "Red", "service_id": "S1", "trip_id": "T1"}],
        stop_times=[
            {"trip_id": "T1", "arrival_time": "08:00:00", "stop_id": "70064", "stop_sequence": 1},
        ],
    )
    rt = make_tripupdate_feed(
        trips=[{"trip_id": "T1", "route_id": "Red", "start_date": yyyymmdd(SERVICE_DATE)}]
    )

    arrivals = parse(rt, static)
    assert arrivals[0].stop_id == "70064"
    assert arrivals[0].parent_station == "place-davis"


def test_arrival_carries_trip_headsign() -> None:
    """The static trip's ``trip_headsign`` is propagated onto every Arrival row."""
    static = make_static_feed(
        routes=[{"route_id": "Red", "route_type": 1}],
        stops=[
            {"stop_id": "place-davis", "stop_name": "Davis"},
            {
                "stop_id": "70064",
                "stop_name": "Davis - Red Line - Alewife",
                "parent_station": "place-davis",
            },
        ],
        trips=[
            {
                "route_id": "Red",
                "service_id": "S1",
                "trip_id": "T1",
                "direction_id": 1,
                "trip_headsign": "Alewife",
            }
        ],
        stop_times=[
            {"trip_id": "T1", "arrival_time": "08:00:00", "stop_id": "70064", "stop_sequence": 1},
        ],
    )
    rt = make_tripupdate_feed(
        trips=[{"trip_id": "T1", "route_id": "Red", "start_date": yyyymmdd(SERVICE_DATE)}]
    )

    arrivals = parse(rt, static)
    assert arrivals[0].direction_id == 1
    assert arrivals[0].trip_headsign == "Alewife"


def test_parse_drops_out_of_scope_route_entities() -> None:
    """Bus / CR / other-branch TripUpdates are dropped before any per-trip work.

    Without this filter, the parser would treat them as ADDED trips (since
    the static feed is scope-filtered to Red + Green-E) and surface bus
    arrivals on the Davis board.
    """
    static = make_static_feed(
        routes=[{"route_id": "Red", "route_type": 1}],
        stops=[{"stop_id": "place-davis", "stop_name": "Davis"}],
        trips=[{"route_id": "Red", "service_id": "S1", "trip_id": "T-RED-1"}],
        stop_times=[
            {
                "trip_id": "T-RED-1",
                "arrival_time": "08:00:00",
                "stop_id": "place-davis",
                "stop_sequence": 1,
            },
        ],
    )
    rt = make_tripupdate_feed(
        trips=[
            # In-scope: should produce one Arrival.
            {"trip_id": "T-RED-1", "route_id": "Red", "start_date": yyyymmdd(SERVICE_DATE)},
            # Out-of-scope (the 39 bus): should be dropped entirely, not surfaced as ADDED.
            {
                "trip_id": "T-BUS-39-1",
                "route_id": "39",
                "start_date": yyyymmdd(SERVICE_DATE),
                "stop_time_updates": [{"stop_id": "place-davis", "delay": 60}],
            },
            # Out-of-scope (Green-B): same.
            {
                "trip_id": "T-GREEN-B-1",
                "route_id": "Green-B",
                "start_date": yyyymmdd(SERVICE_DATE),
                "stop_time_updates": [{"stop_id": "place-davis", "delay": 60}],
            },
        ]
    )

    arrivals = parse(rt, static)

    kept_routes = {a.route_id for a in arrivals}
    assert kept_routes == {"Red"}, f"unexpected routes leaked through: {kept_routes}"


def test_arrival_parent_station_none_for_top_level_stop() -> None:
    """A stop with no parent (the parent station itself) reports ``parent_station=None``."""
    static = make_static_feed(
        routes=[{"route_id": "Red", "route_type": 1}],
        stops=[
            # No parent_station field on this stop — it's the top-level station.
            {"stop_id": "place-davis", "stop_name": "Davis"},
        ],
        trips=[{"route_id": "Red", "service_id": "S1", "trip_id": "T1"}],
        stop_times=[
            {
                "trip_id": "T1",
                "arrival_time": "08:00:00",
                "stop_id": "place-davis",
                "stop_sequence": 1,
            },
        ],
    )
    rt = make_tripupdate_feed(
        trips=[{"trip_id": "T1", "route_id": "Red", "start_date": yyyymmdd(SERVICE_DATE)}]
    )

    arrivals = parse(rt, static)
    assert arrivals[0].stop_id == "place-davis"
    assert arrivals[0].parent_station is None
