"""Parse a GTFS-RT ``FeedMessage`` carrying ``Alert`` entities into typed rows.

Two layered filters:

1. **Scope** (stop-aware route check): when an ``informed_entity`` carries a
   ``stop_id``, at least one of those ``stop_id``s must be in
   ``ALL_CORRIDOR_PARENT_STATIONS``. Only when *no* informed_entity has a
   ``stop_id`` does a route-only match against ``SCOPE_ROUTES`` keep the alert
   — that's the "systemwide / no stops named" case. The asymmetry is required
   because MBTA tags every Red Line alert with ``route_id="Red"`` in addition
   to specific stop selectors; a flat "any route OR any stop" check kept
   alerts whose stops were entirely outside our corridor (e.g. Andrew, south
   of Park St). See :func:`_touches_scope`.
2. **Active-period**: an alert survives only if at least one of its
   ``active_period`` ranges overlaps the supplied ``now``. An alert with no
   ``active_period`` entries is considered always-on (per the GTFS-RT spec) and
   survives.

``now`` is a parameter (no module-level wall-clock read), so tests can pin time
without monkey-patching.
"""

from __future__ import annotations

from datetime import UTC, datetime

from google.transit import gtfs_realtime_pb2

from gtfs_demo.models.alert import (
    ActivePeriod,
    Cause,
    Effect,
    InformedEntity,
    ServiceAlert,
)
from gtfs_demo.scope import ALL_CORRIDOR_PARENT_STATIONS, SCOPE_ROUTES

_PREFERRED_LANGUAGE = "en"


def parse(
    feed_message: gtfs_realtime_pb2.FeedMessage,
    *,
    now: datetime,
    scope_routes: frozenset[str] = SCOPE_ROUTES,
    scope_stops: frozenset[str] = ALL_CORRIDOR_PARENT_STATIONS,
) -> list[ServiceAlert]:
    """Return alerts touching the scope and active at ``now``.

    ``now`` is required (no ambient wall clock). Callers in the live demo pass
    ``datetime.now(tz=UTC)``; tests pass a pinned datetime.
    """
    out: list[ServiceAlert] = []
    for entity in feed_message.entity:
        if not entity.HasField("alert"):
            continue
        alert = entity.alert
        informed = _map_informed(alert)
        if not _touches_scope(informed, scope_routes, scope_stops):
            continue
        active = _map_active_periods(alert)
        if not _is_active(active, now):
            continue
        out.append(
            ServiceAlert(
                header_text=_pick_translation(alert.header_text),
                description_text=_pick_translation(alert.description_text),
                cause=_map_cause(alert.cause),
                effect=_map_effect(alert.effect),
                active_period=active,
                informed_entity=informed,
            )
        )
    return out


def _map_informed(alert: gtfs_realtime_pb2.Alert) -> list[InformedEntity]:
    return [
        InformedEntity(
            agency_id=ie.agency_id or None,
            route_id=ie.route_id or None,
            trip_id=ie.trip.trip_id if ie.HasField("trip") and ie.trip.trip_id else None,
            stop_id=ie.stop_id or None,
        )
        for ie in alert.informed_entity
    ]


def _map_active_periods(alert: gtfs_realtime_pb2.Alert) -> list[ActivePeriod]:
    out: list[ActivePeriod] = []
    for ap in alert.active_period:
        start = datetime.fromtimestamp(ap.start, tz=UTC) if ap.HasField("start") else None
        end = datetime.fromtimestamp(ap.end, tz=UTC) if ap.HasField("end") else None
        out.append(ActivePeriod(start=start, end=end))
    return out


def _touches_scope(
    informed: list[InformedEntity],
    scope_routes: frozenset[str],
    scope_stops: frozenset[str],
) -> bool:
    """Decide whether an alert geographically touches the demo's scope.

    MBTA typically tags every Red Line alert with ``route_id="Red"`` in addition
    to the specific ``stop_id`` selectors. A naive "any route OR any stop in
    scope" check kept alerts whose stops were entirely south of Park St
    (Andrew, JFK, Quincy, etc.) just because the route tag matched — leaking
    out-of-corridor noise onto the board.

    Semantics:

    - If any informed entity carries a ``stop_id``, at least one of those
      ``stop_id``s must be in ``scope_stops``. Otherwise the alert is
      geographically out of corridor regardless of route tagging.
    - If no informed entity has a ``stop_id`` at all (the "Red Line systemwide"
      / "no stops named" case), a route-only match against ``scope_routes`` is
      sufficient.
    """
    stop_ids = [ie.stop_id for ie in informed if ie.stop_id]
    if stop_ids:
        return any(sid in scope_stops for sid in stop_ids)
    return any(ie.route_id in scope_routes for ie in informed if ie.route_id)


def _is_active(active_period: list[ActivePeriod], now: datetime) -> bool:
    """Empty list → always active. Otherwise: at least one range covers ``now``."""
    if not active_period:
        return True
    for ap in active_period:
        if ap.start is not None and now < ap.start:
            continue
        if ap.end is not None and now >= ap.end:
            continue
        return True
    return False


def _pick_translation(translated: gtfs_realtime_pb2.TranslatedString) -> str | None:
    """Return the English translation if available; otherwise the first translation."""
    if not translated.translation:
        return None
    for t in translated.translation:
        if t.language == _PREFERRED_LANGUAGE:
            return t.text or None
    return translated.translation[0].text or None


def _map_cause(pb_value: int) -> Cause:
    """Translate ``Alert.Cause`` protobuf int → user-facing enum.

    Unknown values map to ``UNKNOWN_CAUSE`` rather than raising, so future spec
    additions don't break the parser.
    """
    name = gtfs_realtime_pb2.Alert.Cause.Name(pb_value) if pb_value else "UNKNOWN_CAUSE"
    try:
        return Cause(name)
    except ValueError:
        return Cause.UNKNOWN_CAUSE


def _map_effect(pb_value: int) -> Effect:
    """Translate ``Alert.Effect`` protobuf int → user-facing enum.

    Unknown values map to ``UNKNOWN_EFFECT``.
    """
    name = gtfs_realtime_pb2.Alert.Effect.Name(pb_value) if pb_value else "UNKNOWN_EFFECT"
    try:
        return Effect(name)
    except ValueError:
        return Effect.UNKNOWN_EFFECT


__all__ = ("parse",)
