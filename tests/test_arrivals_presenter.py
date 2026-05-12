"""Tests for ``gtfs_demo.presenter.arrivals.next_n_arrivals``."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from gtfs_demo.models.arrival import Arrival, ScheduleRelationship
from gtfs_demo.presenter.arrivals import next_n_arrivals

TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 5, 11, 8, 0, tzinfo=TZ)


def _arr(
    stop_id: str,
    minutes_from_now: int,
    *,
    sr: ScheduleRelationship = ScheduleRelationship.SCHEDULED,
    route_id: str = "Red",
    trip_id: str | None = None,
) -> Arrival:
    predicted = NOW + timedelta(minutes=minutes_from_now)
    return Arrival(
        stop_id=stop_id,
        stop_name=stop_id,
        route_id=route_id,
        trip_id=trip_id or f"T-{stop_id}-{minutes_from_now}",
        scheduled_at=predicted,
        predicted_at=predicted,
        delay_seconds=0,
        schedule_relationship=sr,
    )


def test_next_n_at_davis() -> None:
    arrivals = [
        _arr("place-davis", 3),
        _arr("place-davis", 7),
        _arr("place-davis", 12),
        _arr("place-davis", 15),
        _arr("place-davis", 22),
        _arr("place-davis", 30),
        _arr("place-pktrm", 5),  # different stop, filtered out
    ]

    out = next_n_arrivals(arrivals, "place-davis", n=5, now=NOW)

    assert [a.predicted_at for a in out] == [NOW + timedelta(minutes=m) for m in (3, 7, 12, 15, 22)]


def test_next_n_at_ball_sq() -> None:
    arrivals = [
        _arr("place-balsq", 4, route_id="Green-E"),
        _arr("place-balsq", 9, route_id="Green-E"),
        _arr("place-balsq", 14, route_id="Green-E"),
        _arr("place-pktrm", 2, route_id="Green-E"),  # different stop
        _arr("place-balsq", -1, route_id="Green-E"),  # past, filtered out
    ]

    out = next_n_arrivals(arrivals, "place-balsq", n=5, now=NOW)

    assert [a.predicted_at for a in out] == [NOW + timedelta(minutes=m) for m in (4, 9, 14)]


def test_canceled_and_skipped_excluded_from_board() -> None:
    arrivals = [
        _arr("place-davis", 3),
        _arr("place-davis", 5, sr=ScheduleRelationship.CANCELED),
        _arr("place-davis", 7, sr=ScheduleRelationship.SKIPPED),
        _arr("place-davis", 9, sr=ScheduleRelationship.UNSCHEDULED),
        _arr("place-davis", 11, sr=ScheduleRelationship.ADDED),
    ]

    out = next_n_arrivals(arrivals, "place-davis", n=10, now=NOW)
    relationships = [a.schedule_relationship for a in out]

    assert relationships == [ScheduleRelationship.SCHEDULED, ScheduleRelationship.ADDED]


def test_n_caps_result_size() -> None:
    arrivals = [_arr("place-davis", m) for m in range(1, 21)]
    out = next_n_arrivals(arrivals, "place-davis", n=3, now=NOW)
    assert len(out) == 3


def _arr_with_parent(
    stop_id: str,
    parent_station: str | None,
    minutes_from_now: int,
) -> Arrival:
    predicted = NOW + timedelta(minutes=minutes_from_now)
    return Arrival(
        stop_id=stop_id,
        parent_station=parent_station,
        stop_name="Davis",
        route_id="Red",
        trip_id=f"T-{stop_id}-{minutes_from_now}",
        scheduled_at=predicted,
        predicted_at=predicted,
        delay_seconds=0,
        schedule_relationship=ScheduleRelationship.SCHEDULED,
    )


def test_next_n_matches_by_parent_station() -> None:
    """Filtering by parent station ID matches platform-level Arrival rows.

    This is the production case: the parser produces Arrival rows whose
    ``stop_id`` is the platform-level ID (e.g. ``70063``) from static
    ``stop_times.txt``; the Streamlit page passes the parent station ID
    (``place-davis``). Without the parent-station match, the board renders empty.
    """
    arrivals = [
        _arr_with_parent("70063", "place-davis", 3),  # Davis-southbound
        _arr_with_parent("70064", "place-davis", 5),  # Davis-northbound
        _arr_with_parent("70075", "place-pktrm", 4),  # different parent — filtered out
    ]

    out = next_n_arrivals(arrivals, "place-davis", n=5, now=NOW)

    assert [a.stop_id for a in out] == ["70063", "70064"]


def test_next_n_matches_by_direct_stop_id_backward_compat() -> None:
    """Existing test-style fixtures (Arrival.stop_id is the parent ID directly) still match."""
    arrivals = [
        _arr("place-davis", 3),
        _arr("place-davis", 7),
    ]
    out = next_n_arrivals(arrivals, "place-davis", n=5, now=NOW)
    assert len(out) == 2


def test_next_n_filters_by_direction_id() -> None:
    """Passing ``direction_id=0`` returns only inbound (south) arrivals; ``=1`` only outbound."""
    arrivals = [
        Arrival(
            stop_id="70064",
            parent_station="place-davis",
            stop_name="Davis",
            route_id="Red",
            trip_id=f"T-outbound-{m}",
            direction_id=1,
            scheduled_at=NOW + timedelta(minutes=m),
            predicted_at=NOW + timedelta(minutes=m),
            delay_seconds=0,
            schedule_relationship=ScheduleRelationship.SCHEDULED,
        )
        for m in (3, 8)
    ] + [
        Arrival(
            stop_id="70063",
            parent_station="place-davis",
            stop_name="Davis",
            route_id="Red",
            trip_id=f"T-inbound-{m}",
            direction_id=0,
            scheduled_at=NOW + timedelta(minutes=m),
            predicted_at=NOW + timedelta(minutes=m),
            delay_seconds=0,
            schedule_relationship=ScheduleRelationship.SCHEDULED,
        )
        for m in (5, 10)
    ]

    inbound = next_n_arrivals(arrivals, "place-davis", n=5, direction_id=0, now=NOW)
    outbound = next_n_arrivals(arrivals, "place-davis", n=5, direction_id=1, now=NOW)

    assert [a.trip_id for a in inbound] == ["T-inbound-5", "T-inbound-10"]
    assert [a.trip_id for a in outbound] == ["T-outbound-3", "T-outbound-8"]

    # No filter still returns everything, sorted.
    both = next_n_arrivals(arrivals, "place-davis", n=10, now=NOW)
    assert len(both) == 4


def test_next_n_handles_arrival_with_no_parent() -> None:
    """A row whose ``parent_station`` is ``None`` doesn't crash the match logic."""
    arrivals = [
        _arr_with_parent("place-davis", None, 3),  # the parent station itself
        _arr_with_parent("70063", "place-davis", 5),  # a platform under it
    ]
    out = next_n_arrivals(arrivals, "place-davis", n=5, now=NOW)
    assert len(out) == 2
