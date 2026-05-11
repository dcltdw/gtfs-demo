"""Tests for ``gtfs_dleung.presenter.arrivals.next_n_arrivals``."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from gtfs_dleung.models.arrival import Arrival, ScheduleRelationship
from gtfs_dleung.presenter.arrivals import next_n_arrivals

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
