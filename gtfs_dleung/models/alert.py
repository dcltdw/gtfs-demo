"""Domain model for service alerts — output of the ServiceAlerts parser.

``Cause`` and ``Effect`` are user-facing StrEnums mirroring the GTFS-RT
``Alert.Cause`` and ``Alert.Effect`` protobuf enums. ``InformedEntity`` is the
GTFS-RT selector format: an alert can target any combination of agency / route /
trip / stop. The parser narrows alerts to the demo scope by checking these
selectors against the corridor routes and parent stations.

An alert may have multiple ``active_period`` ranges (e.g. weekend closures over
two weekends). A missing ``start`` or ``end`` means "open-ended in that direction."
The presenter filters to alerts whose ``active_period`` overlaps the wall clock.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Cause(StrEnum):
    """``Alert.Cause`` enum from gtfs-realtime.proto."""

    UNKNOWN_CAUSE = "UNKNOWN_CAUSE"
    OTHER_CAUSE = "OTHER_CAUSE"
    TECHNICAL_PROBLEM = "TECHNICAL_PROBLEM"
    STRIKE = "STRIKE"
    DEMONSTRATION = "DEMONSTRATION"
    ACCIDENT = "ACCIDENT"
    HOLIDAY = "HOLIDAY"
    WEATHER = "WEATHER"
    MAINTENANCE = "MAINTENANCE"
    CONSTRUCTION = "CONSTRUCTION"
    POLICE_ACTIVITY = "POLICE_ACTIVITY"
    MEDICAL_EMERGENCY = "MEDICAL_EMERGENCY"


class Effect(StrEnum):
    """``Alert.Effect`` enum from gtfs-realtime.proto."""

    NO_SERVICE = "NO_SERVICE"
    REDUCED_SERVICE = "REDUCED_SERVICE"
    SIGNIFICANT_DELAYS = "SIGNIFICANT_DELAYS"
    DETOUR = "DETOUR"
    ADDITIONAL_SERVICE = "ADDITIONAL_SERVICE"
    MODIFIED_SERVICE = "MODIFIED_SERVICE"
    OTHER_EFFECT = "OTHER_EFFECT"
    UNKNOWN_EFFECT = "UNKNOWN_EFFECT"
    STOP_MOVED = "STOP_MOVED"
    NO_EFFECT = "NO_EFFECT"
    ACCESSIBILITY_ISSUE = "ACCESSIBILITY_ISSUE"


class ActivePeriod(BaseModel):
    """One ``[start, end)`` half-open interval during which an alert is active.

    Either side may be ``None`` (open-ended)."""

    model_config = ConfigDict(frozen=True)

    start: datetime | None = None
    end: datetime | None = None


class InformedEntity(BaseModel):
    """One ``EntitySelector`` from an alert's ``informed_entity`` list.

    All fields are optional; an alert with selector ``{route_id: "Red"}`` applies
    to every trip + stop on the Red Line.
    """

    model_config = ConfigDict(frozen=True)

    agency_id: str | None = None
    route_id: str | None = None
    trip_id: str | None = None
    stop_id: str | None = None


class ServiceAlert(BaseModel):
    """One service alert from the RT ``Alert`` feed."""

    model_config = ConfigDict(frozen=True)

    header_text: str | None
    """Short title (e.g. ``"Red Line: Shuttle buses replace trains, weekend of 5/18"``)."""

    description_text: str | None
    """Longer body. May be ``None``."""

    cause: Cause = Cause.UNKNOWN_CAUSE
    effect: Effect = Effect.UNKNOWN_EFFECT
    active_period: list[ActivePeriod] = []
    informed_entity: list[InformedEntity] = []
