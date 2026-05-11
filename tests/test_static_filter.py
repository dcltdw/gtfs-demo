"""Tests for ``gtfs_dleung.parser.static`` — load + filter_to_scope."""

from __future__ import annotations

from pathlib import Path

from gtfs_dleung.parser.static import filter_to_scope, load_feed_from_dir
from gtfs_dleung.scope import (
    ALL_CORRIDOR_PARENT_STATIONS,
    GREEN_E_CORRIDOR,
    RED_LINE_CORRIDOR,
    SCOPE_ROUTES,
)


def test_load_fixture_into_pydantic_models(mbta_mini_unzipped: Path) -> None:
    """The fixture parses cleanly into typed Pydantic models."""
    feed = load_feed_from_dir(mbta_mini_unzipped)

    assert len(feed.routes) == 3  # Red, Green-E, 39 (out-of-scope bus)
    assert len(feed.trips) == 6  # 2 trips per route
    assert len(feed.stops) > 0
    assert len(feed.stop_times) > 0
    assert all(r.route_id for r in feed.routes)
    assert all(s.stop_id for s in feed.stops)


def test_filter_keeps_only_red_and_green_e(mbta_mini_unzipped: Path) -> None:
    """After scope filter, only Red Line + Green-E entities remain."""
    feed = load_feed_from_dir(mbta_mini_unzipped)
    filtered = filter_to_scope(feed)

    kept_route_ids = {r.route_id for r in filtered.routes}
    assert kept_route_ids == SCOPE_ROUTES

    kept_trip_route_ids = {t.route_id for t in filtered.trips}
    assert kept_trip_route_ids == SCOPE_ROUTES

    # No out-of-scope route slipped through (the 39 bus is in the unfiltered feed).
    assert "39" not in kept_route_ids


def test_scope_corridor_stop_count(mbta_mini_unzipped: Path) -> None:
    """Every kept stop lives inside a corridor parent station."""
    feed = load_feed_from_dir(mbta_mini_unzipped)
    filtered = filter_to_scope(feed)

    for stop in filtered.stops:
        if stop.stop_id in ALL_CORRIDOR_PARENT_STATIONS:
            continue
        assert (
            stop.parent_station in ALL_CORRIDOR_PARENT_STATIONS
        ), f"stop {stop.stop_id} kept but parent={stop.parent_station} is out of scope"

    # Sanity: the kept set contains at least one stop from each corridor.
    kept_parents = {
        stop.stop_id if stop.stop_id in ALL_CORRIDOR_PARENT_STATIONS else stop.parent_station
        for stop in filtered.stops
    }
    assert kept_parents & RED_LINE_CORRIDOR, "no Red Line corridor stops survived the filter"
    assert kept_parents & GREEN_E_CORRIDOR, "no Green-E corridor stops survived the filter"


def test_filter_trims_stop_times_to_in_scope_trips(mbta_mini_unzipped: Path) -> None:
    """stop_times for out-of-scope trips are dropped entirely."""
    feed = load_feed_from_dir(mbta_mini_unzipped)
    filtered = filter_to_scope(feed)

    kept_trip_ids = {t.trip_id for t in filtered.trips}
    for st in filtered.stop_times:
        assert st.trip_id in kept_trip_ids


def test_filter_shapes_match_kept_trips(mbta_mini_unzipped: Path) -> None:
    """Shape rows for out-of-scope routes are dropped."""
    feed = load_feed_from_dir(mbta_mini_unzipped)
    filtered = filter_to_scope(feed)

    kept_shape_ids = {t.shape_id for t in filtered.trips if t.shape_id is not None}
    for sh in filtered.shapes:
        assert sh.shape_id in kept_shape_ids
