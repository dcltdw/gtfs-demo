"""Parse a GTFS-RT ``FeedMessage`` carrying TripUpdates into ``Arrival`` rows.

Two non-obvious behaviours, both required by GTFS-RT semantics:

1. **Partial StopTimeUpdate propagation.** A TripUpdate's ``stop_time_update``
   list is sparse: if stop K has an explicit delay, every downstream stop on the
   same trip inherits that delay until the next explicit update appears.
   See https://gtfs.org/realtime/reference/#message-tripupdate.

2. **ADDED trips.** A trip whose ``trip_id`` is not in the static feed is an
   added (one-off) trip — surface it with ``is_added=True`` instead of dropping
   the row. The trip's stop sequence comes from the RT message itself.

Times are tz-aware ``datetime`` values in ``America/New_York``. GTFS static
times can exceed 24h (e.g. ``27:30:00``) for trips that span midnight on the
prior service day; ``_static_time_to_datetime`` handles that by adding the
overflow to the next day.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from google.transit import gtfs_realtime_pb2

from gtfs_dleung.models.arrival import Arrival, ScheduleRelationship
from gtfs_dleung.models.static import StaticFeed, Stop, StopTime, Trip

MBTA_TZ = ZoneInfo("America/New_York")

# Protobuf enum values for TripDescriptor.ScheduleRelationship (trip-level).
_TRIP_SR_SCHEDULED = 0
_TRIP_SR_ADDED = 1
_TRIP_SR_UNSCHEDULED = 2
_TRIP_SR_CANCELED = 3
# 5/6/7 = REPLACEMENT (deprecated) / DUPLICATED (experimental) / DELETED — treated as SCHEDULED.

# Protobuf enum values for StopTimeUpdate.ScheduleRelationship (stop-level).
_STOP_SR_SCHEDULED = 0
_STOP_SR_SKIPPED = 1
_STOP_SR_NO_DATA = 2
_STOP_SR_UNSCHEDULED = 3


def parse(
    feed_message: gtfs_realtime_pb2.FeedMessage,
    static_feed: StaticFeed,
    *,
    now: datetime | None = None,
) -> list[Arrival]:
    """Return one :class:`Arrival` per stop on every trip in ``feed_message``.

    ``now`` is injectable for tests; defaults to the wall clock in ``MBTA_TZ``.
    It only affects the fallback service date when the RT message doesn't carry
    a ``start_date``.
    """
    if now is None:
        now = datetime.now(tz=MBTA_TZ)

    trips_by_id: Mapping[str, Trip] = {t.trip_id: t for t in static_feed.trips}
    stops_by_id: Mapping[str, Stop] = {s.stop_id: s for s in static_feed.stops}
    static_stop_times_by_trip: dict[str, list[StopTime]] = {}
    for st in static_feed.stop_times:
        static_stop_times_by_trip.setdefault(st.trip_id, []).append(st)
    for v in static_stop_times_by_trip.values():
        v.sort(key=lambda st: st.stop_sequence)

    out: list[Arrival] = []
    for entity in feed_message.entity:
        if not entity.HasField("trip_update"):
            continue
        out.extend(
            _parse_trip_update(
                entity.trip_update,
                trips_by_id=trips_by_id,
                stops_by_id=stops_by_id,
                static_stop_times_by_trip=static_stop_times_by_trip,
                now=now,
            )
        )
    return out


def _parse_trip_update(
    tu: gtfs_realtime_pb2.TripUpdate,
    *,
    trips_by_id: Mapping[str, Trip],
    stops_by_id: Mapping[str, Stop],
    static_stop_times_by_trip: Mapping[str, list[StopTime]],
    now: datetime,
) -> list[Arrival]:
    trip_id = tu.trip.trip_id
    static_trip = trips_by_id.get(trip_id)
    is_added = static_trip is None

    trip_sr_pb = tu.trip.schedule_relationship
    trip_sr = _map_trip_sr(trip_sr_pb, is_added=is_added)

    service_date = _resolve_service_date(tu.trip.start_date, now)

    rt_updates_by_stop_id, rt_updates_by_sequence = _index_rt_updates(tu)

    if is_added:
        return _arrivals_for_added_trip(
            tu=tu,
            stops_by_id=stops_by_id,
            service_date=service_date,
            trip_sr=trip_sr,
        )

    assert static_trip is not None  # narrowing for type-checker
    return _arrivals_for_scheduled_trip(
        tu=tu,
        static_trip=static_trip,
        static_stop_times=static_stop_times_by_trip.get(trip_id, []),
        stops_by_id=stops_by_id,
        rt_updates_by_stop_id=rt_updates_by_stop_id,
        rt_updates_by_sequence=rt_updates_by_sequence,
        service_date=service_date,
        trip_sr=trip_sr,
    )


def _arrivals_for_scheduled_trip(
    *,
    tu: gtfs_realtime_pb2.TripUpdate,
    static_trip: Trip,
    static_stop_times: list[StopTime],
    stops_by_id: Mapping[str, Stop],
    rt_updates_by_stop_id: Mapping[str, gtfs_realtime_pb2.TripUpdate.StopTimeUpdate],
    rt_updates_by_sequence: Mapping[int, gtfs_realtime_pb2.TripUpdate.StopTimeUpdate],
    service_date: date,
    trip_sr: ScheduleRelationship,
) -> list[Arrival]:
    """Build arrivals for a trip we know from the static feed.

    Walks the static stop_times in order, applying RT delays where present and
    propagating the last-seen explicit delay forward (the partial-coverage rule).
    """
    out: list[Arrival] = []
    current_delay_seconds: int | None = None
    current_predicted_override: datetime | None = None

    for st in static_stop_times:
        rt_stu = rt_updates_by_stop_id.get(st.stop_id) or rt_updates_by_sequence.get(
            st.stop_sequence
        )

        stop_sr = ScheduleRelationship.SCHEDULED
        if rt_stu is not None:
            explicit_delay, explicit_time = _extract_delay_and_time(rt_stu)
            if explicit_delay is not None:
                current_delay_seconds = explicit_delay
                current_predicted_override = None
            if explicit_time is not None:
                current_predicted_override = explicit_time
            if rt_stu.schedule_relationship == _STOP_SR_SKIPPED:
                stop_sr = ScheduleRelationship.SKIPPED

        scheduled_at = _static_time_to_datetime(st.arrival_time or st.departure_time, service_date)

        predicted_at: datetime | None
        delay: int | None
        if current_predicted_override is not None:
            predicted_at = current_predicted_override
            delay = (
                int((current_predicted_override - scheduled_at).total_seconds())
                if scheduled_at is not None
                else None
            )
        elif current_delay_seconds is not None and scheduled_at is not None:
            predicted_at = scheduled_at + timedelta(seconds=current_delay_seconds)
            delay = current_delay_seconds
        else:
            predicted_at = scheduled_at
            delay = None

        # Trip-level CANCELED dominates the per-stop label.
        final_sr = trip_sr if trip_sr == ScheduleRelationship.CANCELED else stop_sr

        out.append(
            Arrival(
                stop_id=st.stop_id,
                parent_station=_lookup_parent_station(stops_by_id, st.stop_id),
                stop_name=_lookup_stop_name(stops_by_id, st.stop_id),
                route_id=static_trip.route_id,
                trip_id=static_trip.trip_id,
                direction_id=static_trip.direction_id,
                scheduled_at=scheduled_at,
                predicted_at=predicted_at,
                delay_seconds=delay,
                schedule_relationship=final_sr,
                is_added=False,
            )
        )
    return out


def _arrivals_for_added_trip(
    *,
    tu: gtfs_realtime_pb2.TripUpdate,
    stops_by_id: Mapping[str, Stop],
    service_date: date,
    trip_sr: ScheduleRelationship,
) -> list[Arrival]:
    """Build arrivals for an ADDED trip — stop sequence comes from RT itself."""
    out: list[Arrival] = []
    for stu in tu.stop_time_update:
        _, explicit_time = _extract_delay_and_time(stu)
        predicted_at = explicit_time
        out.append(
            Arrival(
                stop_id=stu.stop_id,
                parent_station=_lookup_parent_station(stops_by_id, stu.stop_id),
                stop_name=_lookup_stop_name(stops_by_id, stu.stop_id),
                route_id=tu.trip.route_id,
                trip_id=tu.trip.trip_id,
                direction_id=None,
                scheduled_at=None,
                predicted_at=predicted_at,
                delay_seconds=None,
                schedule_relationship=trip_sr,
                is_added=True,
            )
        )
    return out


def _map_trip_sr(pb_value: int, *, is_added: bool) -> ScheduleRelationship:
    """Translate a TripDescriptor.ScheduleRelationship enum int to our enum."""
    if pb_value == _TRIP_SR_CANCELED:
        return ScheduleRelationship.CANCELED
    if pb_value == _TRIP_SR_ADDED or is_added:
        return ScheduleRelationship.ADDED
    if pb_value == _TRIP_SR_UNSCHEDULED:
        return ScheduleRelationship.UNSCHEDULED
    return ScheduleRelationship.SCHEDULED


def _index_rt_updates(
    tu: gtfs_realtime_pb2.TripUpdate,
) -> tuple[
    dict[str, gtfs_realtime_pb2.TripUpdate.StopTimeUpdate],
    dict[int, gtfs_realtime_pb2.TripUpdate.StopTimeUpdate],
]:
    by_stop_id: dict[str, gtfs_realtime_pb2.TripUpdate.StopTimeUpdate] = {}
    by_sequence: dict[int, gtfs_realtime_pb2.TripUpdate.StopTimeUpdate] = {}
    for stu in tu.stop_time_update:
        if stu.stop_id:
            by_stop_id[stu.stop_id] = stu
        if stu.HasField("stop_sequence"):
            by_sequence[stu.stop_sequence] = stu
    return by_stop_id, by_sequence


def _extract_delay_and_time(
    stu: gtfs_realtime_pb2.TripUpdate.StopTimeUpdate,
) -> tuple[int | None, datetime | None]:
    """Read either ``arrival`` or ``departure`` for an explicit ``delay``/``time``."""
    for event_field in ("arrival", "departure"):
        if not stu.HasField(event_field):
            continue
        event = getattr(stu, event_field)
        delay = event.delay if event.HasField("delay") else None
        explicit_time = (
            datetime.fromtimestamp(event.time, tz=MBTA_TZ) if event.HasField("time") else None
        )
        if delay is not None or explicit_time is not None:
            return delay, explicit_time
    return None, None


def _static_time_to_datetime(time_str: str | None, service_date: date) -> datetime | None:
    """Convert a GTFS ``HH:MM:SS`` (possibly >24h) into a tz-aware ``datetime``.

    GTFS times are anchored to the **service date**, not the calendar date — a
    trip starting at ``02:00:00`` on Friday's service date might run after
    midnight on Saturday's calendar date. Values >= 24h roll into the next day.
    """
    if not time_str:
        return None
    try:
        hh, mm, ss = (int(p) for p in time_str.split(":"))
    except ValueError:
        return None
    days_overflow, hh = divmod(hh, 24)
    naive = datetime.combine(service_date, datetime.min.time()).replace(
        hour=hh, minute=mm, second=ss
    )
    return (naive + timedelta(days=days_overflow)).replace(tzinfo=MBTA_TZ)


def _resolve_service_date(start_date_str: str, now: datetime) -> date:
    """Parse the RT ``start_date`` (``YYYYMMDD``); fall back to the local date today."""
    if start_date_str and len(start_date_str) == 8:
        try:
            return date(
                int(start_date_str[0:4]),
                int(start_date_str[4:6]),
                int(start_date_str[6:8]),
            )
        except ValueError:
            pass
    return now.astimezone(MBTA_TZ).date()


def _lookup_stop_name(stops_by_id: Mapping[str, Stop], stop_id: str) -> str | None:
    """Return a stop's name, preferring its parent station's name when available."""
    stop = stops_by_id.get(stop_id)
    if stop is None:
        return None
    if stop.parent_station and stop.parent_station in stops_by_id:
        parent_name = stops_by_id[stop.parent_station].stop_name
        if parent_name:
            return parent_name
    return stop.stop_name


def _lookup_parent_station(stops_by_id: Mapping[str, Stop], stop_id: str) -> str | None:
    """Return ``stop_id``'s parent station, or ``None`` when the stop has no parent.

    GTFS static represents platform-level stops with a ``parent_station`` field
    pointing at the station ID (``place-*`` in MBTA's convention). The Streamlit
    page filters by station — ``next_n_arrivals`` needs this populated so it can
    match without enumerating platform IDs.
    """
    stop = stops_by_id.get(stop_id)
    if stop is None:
        return None
    return stop.parent_station


__all__ = ("MBTA_TZ", "parse")
