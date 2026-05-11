"""Parser for the unzipped static GTFS feed.

Turns the CSVs under the feed directory into typed Pydantic models, and offers a
``filter_to_scope`` helper that trims a parsed feed down to the demo corridor.
"""

from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel

from gtfs_dleung.models.static import (
    Route,
    Shape,
    StaticFeed,
    Stop,
    StopTime,
    Trip,
)
from gtfs_dleung.scope import (
    ALL_CORRIDOR_PARENT_STATIONS,
    SCOPE_ROUTES,
)


class StaticParseError(Exception):
    """Raised when a required CSV is missing or unreadable."""


def load_feed_from_dir(feed_dir: Path) -> StaticFeed:
    """Parse the unzipped feed at ``feed_dir`` into a :class:`StaticFeed`."""
    return StaticFeed(
        stops=_load_csv(feed_dir / "stops.txt", Stop),
        routes=_load_csv(feed_dir / "routes.txt", Route),
        trips=_load_csv(feed_dir / "trips.txt", Trip),
        stop_times=_load_csv(feed_dir / "stop_times.txt", StopTime),
        shapes=_load_csv(feed_dir / "shapes.txt", Shape),
    )


def filter_to_scope(feed: StaticFeed) -> StaticFeed:
    """Return a new feed scoped to the Red Line + Green Line E demo corridors.

    Filtering is route-aware: Green Line B/C/D share platforms with Green-E at
    Park Street and other downtown stops, but only Green-E is in scope here.
    Without the route filter, those branches' trips would slip through purely
    by stop ID.
    """
    in_scope_stops = [
        s
        for s in feed.stops
        if s.stop_id in ALL_CORRIDOR_PARENT_STATIONS
        or (s.parent_station is not None and s.parent_station in ALL_CORRIDOR_PARENT_STATIONS)
    ]
    in_scope_stop_ids = {s.stop_id for s in in_scope_stops}

    in_scope_routes = [r for r in feed.routes if r.route_id in SCOPE_ROUTES]
    in_scope_trips = [t for t in feed.trips if t.route_id in SCOPE_ROUTES]
    in_scope_trip_ids = {t.trip_id for t in in_scope_trips}

    in_scope_stop_times = [
        st
        for st in feed.stop_times
        if st.trip_id in in_scope_trip_ids and st.stop_id in in_scope_stop_ids
    ]

    in_scope_shape_ids = {t.shape_id for t in in_scope_trips if t.shape_id is not None}
    in_scope_shapes = [sh for sh in feed.shapes if sh.shape_id in in_scope_shape_ids]

    return StaticFeed(
        stops=in_scope_stops,
        routes=in_scope_routes,
        trips=in_scope_trips,
        stop_times=in_scope_stop_times,
        shapes=in_scope_shapes,
    )


def _load_csv[T: BaseModel](path: Path, model: type[T]) -> list[T]:
    if not path.exists():
        raise StaticParseError(f"Required GTFS file missing: {path}")
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            return [model.model_validate(row) for row in reader]
    except OSError as exc:
        raise StaticParseError(f"Failed to read {path}: {exc}") from exc
