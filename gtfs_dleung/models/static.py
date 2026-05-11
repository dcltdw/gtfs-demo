"""Pydantic models for the static GTFS feed.

These mirror the columns the application actually consumes — not the full GTFS
spec. Optional columns are typed as ``str | None`` / ``float | None`` so that a
missing CSV value (empty string) parses to ``None``.

Reference: https://gtfs.org/schedule/reference/
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _empty_to_none(v: object) -> object:
    """Coerce empty strings to ``None`` so Pydantic ``| None`` fields parse cleanly."""
    if isinstance(v, str) and v == "":
        return None
    return v


class Stop(BaseModel):
    """One row of ``stops.txt``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    stop_id: str
    stop_name: str | None = None
    stop_lat: float | None = None
    stop_lon: float | None = None
    parent_station: str | None = None
    location_type: int | None = None  # 0 = platform, 1 = station, 2 = entrance, ...
    wheelchair_boarding: int | None = None
    platform_code: str | None = None

    _coerce_blank = field_validator(
        "stop_name",
        "stop_lat",
        "stop_lon",
        "parent_station",
        "location_type",
        "wheelchair_boarding",
        "platform_code",
        mode="before",
    )(classmethod(lambda cls, v: _empty_to_none(v)))


class Route(BaseModel):
    """One row of ``routes.txt``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    route_id: str
    route_short_name: str | None = None
    route_long_name: str | None = None
    route_type: int  # 0 = tram/streetcar, 1 = subway, 2 = rail, 3 = bus, ...
    route_color: str | None = None
    route_text_color: str | None = None

    _coerce_blank = field_validator(
        "route_short_name",
        "route_long_name",
        "route_color",
        "route_text_color",
        mode="before",
    )(classmethod(lambda cls, v: _empty_to_none(v)))


class Trip(BaseModel):
    """One row of ``trips.txt``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    route_id: str
    service_id: str
    trip_id: str
    trip_headsign: str | None = None
    direction_id: int | None = None  # 0 = outbound, 1 = inbound (convention varies)
    shape_id: str | None = None

    _coerce_blank = field_validator("trip_headsign", "direction_id", "shape_id", mode="before")(
        classmethod(lambda cls, v: _empty_to_none(v))
    )


class StopTime(BaseModel):
    """One row of ``stop_times.txt``.

    ``arrival_time`` / ``departure_time`` are kept as strings because GTFS times
    can exceed 24h (e.g. ``27:30:00`` for an overnight trip referencing the prior
    service day). Conversion to a real timestamp happens at the consumer.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    trip_id: str
    arrival_time: str | None = None
    departure_time: str | None = None
    stop_id: str
    stop_sequence: int
    pickup_type: int | None = None
    drop_off_type: int | None = None

    _coerce_blank = field_validator(
        "arrival_time",
        "departure_time",
        "pickup_type",
        "drop_off_type",
        mode="before",
    )(classmethod(lambda cls, v: _empty_to_none(v)))


class Shape(BaseModel):
    """One row of ``shapes.txt`` (a single point on a route's geometry)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    shape_id: str
    shape_pt_lat: float
    shape_pt_lon: float
    shape_pt_sequence: int


class StaticFeed(BaseModel):
    """The full set of typed rows from a parsed GTFS bundle.

    Lists rather than indexed dicts: this is the boundary type, not the working
    representation. Consumers can index by ``stop_id`` / ``trip_id`` themselves.
    """

    stops: list[Stop] = Field(default_factory=list)
    routes: list[Route] = Field(default_factory=list)
    trips: list[Trip] = Field(default_factory=list)
    stop_times: list[StopTime] = Field(default_factory=list)
    shapes: list[Shape] = Field(default_factory=list)
