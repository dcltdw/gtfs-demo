"""Pure formatting helpers for the Streamlit arrivals / alerts / health panels.

These functions take typed model instances and return strings / dict
representations. They never touch Streamlit, so they're unit-testable without
spinning up the page.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any, Final

from gtfs_dleung.models.alert import Effect, ServiceAlert
from gtfs_dleung.models.arrival import Arrival, ScheduleRelationship
from gtfs_dleung.models.feed_health import FeedHealth

# Color thresholds for the delay badge. Numbers from the AC.
_DELAY_GREEN_S = 30.0
_DELAY_YELLOW_S = 120.0

# (stop_id, direction_id) pairs where the trip headsign tells the rider something
# the column header doesn't. Default-False: if a pair isn't listed here, the
# direction has a single terminus and the headsign is redundant.
#
# - ("place-davis", 0): Red Line southbound from Davis splits Ashmont/Braintree
#   south of JFK; the headsign picks the branch and matters to the rider.
#
# Outbound from Davis (Alewife) and both directions from Ball Sq (single Green-E
# terminus each way) are absent — headsign is non-informative there. If the demo
# ever extends to a southern station with branching, add an entry here.
_HEADSIGN_INFORMATIVE_PAIRS: Final[frozenset[tuple[str, int]]] = frozenset(
    {
        ("place-davis", 0),
    }
)


def delay_color_class(delay_seconds: int | float | None) -> str:
    """Return ``"green" | "yellow" | "red" | "neutral"`` based on the delay magnitude.

    Negative delays (early arrivals) are treated by absolute magnitude — a train
    running 90s early is the same kind of "off-schedule" as a train running 90s
    late, from a rider's planning perspective.
    """
    if delay_seconds is None:
        return "neutral"
    mag = abs(float(delay_seconds))
    if mag <= _DELAY_GREEN_S:
        return "green"
    if mag <= _DELAY_YELLOW_S:
        return "yellow"
    return "red"


def direction_label(direction_id: int | None) -> str:
    """Return a human-readable label for a GTFS ``direction_id``.

    The mapping is **scoped to the demo's two stations** (Davis on the Red Line
    and Ball Square on the Green-E branch), both of which sit north of Park St:

    - ``0`` → ``"Inbound"``  (south toward Park St / downtown)
    - ``1`` → ``"Outbound"``  (north toward Alewife / Medford-Tufts)
    - ``None`` → ``"Unknown direction"``

    A station south of Park St would invert this mapping. If the demo ever
    extends to a southern station (Quincy Center, Heath St, etc.), this helper
    needs a route-+-station-aware variant. Pinned to "north of Park" today.
    """
    if direction_id == 0:
        return "Inbound"
    if direction_id == 1:
        return "Outbound"
    return "Unknown direction"


def show_headsign(stop_id: str, direction_id: int | None) -> bool:
    """Return ``True`` iff the trip headsign is informative at this ``(stop, direction)``.

    Hides redundant ``— toward Foo`` suffixes on rows where every train in that
    direction goes to the same terminus (Davis outbound → Alewife; Ball Sq either
    direction → Green-E single terminus). Returns ``True`` only when the direction
    has multiple possible termini (currently just Davis inbound → Ashmont/Braintree).
    """
    if direction_id is None:
        return False
    return (stop_id, direction_id) in _HEADSIGN_INFORMATIVE_PAIRS


def schedule_relationship_badge(sr: ScheduleRelationship) -> str | None:
    """Return a short, user-facing badge label for unusual ``schedule_relationship`` values.

    Returns ``None`` for ``SCHEDULED`` (the boring case — no badge).
    """
    badge_map: dict[ScheduleRelationship, str] = {
        ScheduleRelationship.ADDED: "ADDED",
        ScheduleRelationship.CANCELED: "CANCELED",
        ScheduleRelationship.SKIPPED: "SKIPPED",
        ScheduleRelationship.UNSCHEDULED: "UNSCHED",
    }
    return badge_map.get(sr)


def format_arrival_row(arrival: Arrival) -> dict[str, str | None]:
    """Render an :class:`Arrival` as a display-ready dict.

    Keys: ``route``, ``stop``, ``scheduled``, ``predicted``, ``delay``, ``color``,
    ``badge``, ``trip_id``. Values are pre-formatted strings; ``None`` is used
    sparingly for missing data so the consumer can render placeholders.
    """
    return {
        "route": arrival.route_id,
        "stop": arrival.stop_name or arrival.stop_id,
        "scheduled": _fmt_clock(arrival.scheduled_at),
        "predicted": _fmt_clock(arrival.predicted_at),
        "delay": _fmt_delay(arrival.delay_seconds),
        "color": delay_color_class(arrival.delay_seconds),
        "badge": schedule_relationship_badge(arrival.schedule_relationship),
        "trip_id": arrival.trip_id,
        "headsign": arrival.trip_headsign,
    }


def format_feed_age(age_seconds: float | None) -> str:
    """Human-readable feed age (``None`` → ``"unknown"``, ``8.2`` → ``"8s"``, etc.)."""
    if age_seconds is None:
        return "unknown"
    seconds = max(0.0, float(age_seconds))
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"


def feed_health_icon(health: FeedHealth) -> str:
    """Return a single emoji that summarises the feed's state at a glance.

    - ``✅`` fresh + connected
    - ``🟡`` stale data but fetches succeeding (publisher delay)
    - ``🟠`` degraded fetches but cached data still fresh (network blip)
    - ``🔴`` stale **and** degraded (both signals red — biggest worry)
    - ``⚪`` no data yet
    """
    if health.age_seconds is None and not health.is_degraded:
        return "⚪"
    if health.is_stale and health.is_degraded:
        return "🔴"
    if health.is_degraded:
        return "🟠"
    if health.is_stale:
        return "🟡"
    return "✅"


def format_alert_row(alert: ServiceAlert) -> dict[str, str | None]:
    """Render a :class:`ServiceAlert` as a display-ready dict.

    Keys: ``header``, ``description``, ``effect``, ``effect_label``, ``cause``,
    ``starts``, ``ends``.
    """
    first_period = alert.active_period[0] if alert.active_period else None
    return {
        "header": alert.header_text or "(no header)",
        "description": alert.description_text,
        "effect": str(alert.effect.value),
        "effect_label": _effect_short_label(alert.effect),
        "cause": str(alert.cause.value),
        "starts": _fmt_clock(first_period.start) if first_period else None,
        "ends": _fmt_clock(first_period.end) if first_period else None,
    }


def should_show_stale_banner(
    healths: Mapping[Any, FeedHealth] | Iterable[FeedHealth],
) -> bool:
    """``True`` iff any feed is currently stale or degraded.

    Accepts either a mapping (as returned by ``HealthTrackedFetcher.get_health``,
    keyed by ``FeedType``) or a flat iterable. ``Mapping[Any, ...]`` rather than
    ``Mapping[object, ...]`` because mypy treats ``Mapping`` key types as
    invariant — a ``dict[FeedType, V]`` is not a ``Mapping[object, V]``.
    """
    iterable: Iterable[FeedHealth] = healths.values() if isinstance(healths, Mapping) else healths
    return any(h.is_stale or h.is_degraded for h in iterable)


# ---- internals ----------------------------------------------------------------


def _fmt_clock(when: datetime | None) -> str | None:
    if when is None:
        return None
    return when.strftime("%I:%M:%S %p").lstrip("0")


def _fmt_delay(seconds: int | float | None) -> str:
    if seconds is None:
        return "—"
    mag = round(abs(float(seconds)))
    sign = "+" if seconds >= 0 else "−"  # noqa: RUF001 — Unicode minus is intentional for visual clarity
    if mag < 60:
        return f"{sign}{mag}s"
    return f"{sign}{mag // 60}m {mag % 60}s"


def _effect_short_label(effect: Effect) -> str:
    """Compress the long enum names for tighter UI labels."""
    short = {
        Effect.NO_SERVICE: "No service",
        Effect.REDUCED_SERVICE: "Reduced",
        Effect.SIGNIFICANT_DELAYS: "Delays",
        Effect.DETOUR: "Detour",
        Effect.ADDITIONAL_SERVICE: "Added",
        Effect.MODIFIED_SERVICE: "Modified",
        Effect.STOP_MOVED: "Stop moved",
        Effect.ACCESSIBILITY_ISSUE: "Accessibility",
        Effect.NO_EFFECT: "Info",
        Effect.OTHER_EFFECT: "Other",
        Effect.UNKNOWN_EFFECT: "?",
    }
    return short.get(effect, str(effect.value))


__all__ = (
    "delay_color_class",
    "direction_label",
    "feed_health_icon",
    "format_alert_row",
    "format_arrival_row",
    "format_feed_age",
    "schedule_relationship_badge",
    "should_show_stale_banner",
    "show_headsign",
)
