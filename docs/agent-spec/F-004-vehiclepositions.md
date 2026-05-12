---
id: F-004
title: VehiclePositions parser
type: functional
status: in-progress
issue: 6
pr: null
depends_on: [F-002]
owner: dcltdw
last_updated: 2026-05-11
---

## Summary

Decode a GTFS-RT `FeedMessage` carrying VehiclePositions into typed `VehiclePosition` rows, scoped to the demo corridor (Red + Green-E). One row per in-scope vehicle entity. The parser is pure (no I/O). It does not render maps — the post-demo issue #15 covers that — but the typed surface here is what the map and any analytics build on.

This spec replaces what the originating issue called `F-003-vehiclepositions-parser`. The `F-003` slot was already taken by `TripUpdates → arrivals board` (issue #5); the correct number for VehiclePositions is `F-004`, matching `REQUIREMENTS.md`.

## Inputs

- `feed_message: gtfs_realtime_pb2.FeedMessage` — the decoded RT envelope from F-002's `fetch_feed`.
- `scope_routes: frozenset[str]` — defaults to `gtfs_demo.scope.SCOPE_ROUTES`; injectable for tests.

## Properties

1. **Three distinct id-like fields.** The parser keeps `vehicle_id` (internal system ID — `VehicleDescriptor.id`), `vehicle_label` (rider-facing label — `VehicleDescriptor.label`, e.g. `"1701"` painted on the train), and `trip_id` (the trip currently being run) separate. The model docstring documents the distinction; tests assert they don't get conflated.
2. **Route-based scope filter.** Vehicles whose `trip.route_id` is not in `scope_routes` are dropped. Vehicles with a missing `route_id` are also dropped (no static-feed join needed; MBTA's feed reliably carries `route_id` on the TripDescriptor).
3. **Status enum.** `VehiclePosition.VehicleStopStatus` (protobuf int) maps to the user-facing `VehicleStatus` StrEnum: `INCOMING_AT` / `STOPPED_AT` / `IN_TRANSIT_TO`.
4. **Optional fields are optional.** `latitude` / `longitude` / `bearing` / `current_status` / `current_stop_sequence` / `timestamp` are all `None` when the protobuf message omits them.
5. **Timestamps are UTC.** The RT feed's `timestamp` is unix-seconds; the parser exposes a tz-aware `datetime` in `UTC`. Conversion to local time is the consumer's job (matches the F-003 convention).
6. **Pure function.** No I/O, no logging, no module-level state. Same shape as F-003's `parse`.

## Outputs

- `parse(feed_message, *, scope_routes=SCOPE_ROUTES) -> list[VehiclePosition]`.

## Edge cases

- **Entity without `vehicle` field**: skipped (the same `FeedMessage` may carry trip_update / vehicle / alert entities — only the vehicle ones are processed here).
- **Vehicle with no trip** (e.g. an out-of-service car): no `route_id` available → dropped by the scope filter. Could be revisited if the demo needs to surface "vehicles between trips," but that's not in scope today.
- **`position` field absent**: `latitude` / `longitude` / `bearing` all `None`. Most MBTA RT messages carry these for in-service vehicles.
- **Stale timestamp**: not the parser's concern. Staleness handling lives in F-006 (#8).

## Out of scope

- Map rendering (post-demo #15).
- Anomaly detection / stuck-vehicle alerts (post-demo #28).
- Schedule-vs-actual analytics (post-demo #34).
- DuckDB persistence of position snapshots (post-demo #26).
- Inferring route from trip via static feed when RT omits it (not needed for MBTA's feed today).

## Verification

- `tests/test_vehicles_parser.py::test_basic_parse` — single Red Line vehicle round-trips with every field populated (lat/lon use `pytest.approx` because protobuf stores floats as `float32`).
- `tests/test_vehicles_parser.py::test_filters_to_scope_routes` — keeps Red + Green-E, drops Green-B, the 39 bus, commuter rail, and vehicles with no trip.
- `tests/test_vehicles_parser.py::test_current_status_enum_mapping` — three protobuf status ints map to the three enum members.
- `tests/test_vehicles_parser.py::test_id_label_trip_id_are_distinct` — asserts the parser doesn't collapse the three id-like fields.
- `tests/test_vehicles_parser.py::test_parses_real_fixture` — `tests/fixtures/vehiclepositions_sample.pb` (trimmed real feed, 15 entities including 5 Red + 5 Green-E + 5 out-of-scope) decodes + filters to Red + Green-E only.

Manual:

```bash
uv run python -c "from gtfs_demo.fetcher.realtime import fetch_feed; \
                  from gtfs_demo.feeds import VEHICLE_POSITIONS_URL; \
                  from gtfs_demo.parser.vehicles import parse; \
                  vps = parse(fetch_feed(VEHICLE_POSITIONS_URL)); \
                  print(len(vps), 'in-scope vehicles')"
```

## Open questions

_None._
