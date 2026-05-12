---
id: F-003
title: TripUpdates → arrivals board
type: functional
status: in-progress
issue: 5
pr: null
depends_on: [F-001, F-002]
owner: dcltdw
last_updated: 2026-05-11
---

## Summary

Decode a GTFS-RT `FeedMessage` carrying `TripUpdate`s into a list of typed `Arrival` rows joined with the static feed (F-001), then expose a small presenter helper that returns the next *N* board-visible arrivals at a given stop. The parser is pure (no I/O); time math is tz-aware (`America/New_York`); two non-obvious GTFS-RT semantics are implemented and tested — partial StopTimeUpdate propagation and ADDED-trip surfacing.

This spec absorbs what the originating issue (#5) called `F-002b-tripupdates-parser`, `F-006-schedule-relationship`, and `F-007-partial-stoptimeupdate`. Those numbers were already taken in `REQUIREMENTS.md` by the time the issue was implemented; the three areas are documented here as Properties of F-003.

## Inputs

- `feed_message: gtfs_realtime_pb2.FeedMessage` — the decoded RT envelope from F-002's `fetch_feed`.
- `static_feed: gtfs_demo.models.static.StaticFeed` — the parsed + scope-filtered static bundle from F-001.
- Optional `now: datetime` — injectable wall-clock anchor for tests.

## Properties

1. **One `Arrival` per (trip × static stop).** For SCHEDULED trips, the parser walks the static `stop_times` for the trip and emits one row per stop, applying RT updates where present.
2. **Synthesised `ScheduleRelationship` enum.** The user-facing label collapses the two GTFS-RT enums (trip-level + stop-level). CANCELED dominates the row (every stop on a canceled trip is flagged CANCELED). SKIPPED is a per-stop label that doesn't infect siblings. ADDED appears for trips RT introduces at runtime.
3. **Partial StopTimeUpdate propagation.** When stop K has an explicit delay, every subsequent stop on the same trip inherits K's delay until the next explicit update appears. Stops *upstream* of the first explicit update receive `delay_seconds=None` (no propagation backward). Implementation walks static `stop_times` in `stop_sequence` order and threads a `current_delay_seconds` accumulator.
4. **ADDED trips.** If RT references a `trip_id` not in the static feed, the parser still emits one `Arrival` per stop in the RT `StopTimeUpdate` list, with `is_added=True`, `scheduled_at=None`, and `schedule_relationship=ADDED`. The stop name is looked up in `static_feed.stops` if available.
5. **Parent-station name preference.** When a platform-level stop has a parent station, the parent's `stop_name` is used for the `Arrival.stop_name` (riders look up "Park Street," not "Park Street — Red Line — Alewife").
5a. **Parent-station ID surfaced for filtering.** `Arrival.parent_station` carries the parent station's `stop_id` (or `None` for stops with no parent). `next_n_arrivals(arrivals, "place-davis", n=5)` matches when either `a.stop_id == stop_id` or `a.parent_station == stop_id` — without this, the Streamlit page's "filter by parent station" call would never match real-feed Arrival rows whose `stop_id` is a platform-level ID like `70063` / `70064`. See [#60](https://github.com/dcltdw/gtfs-demo/issues/60).
5b. **Direction split.** `next_n_arrivals` accepts an optional `direction_id` parameter. The Streamlit board renders each station as **two subsections** (Inbound + Outbound) by calling `next_n_arrivals` twice with `direction_id=0` and `direction_id=1` respectively. For Davis (Red) and Ball Sq (Green-E) — both north of Park St — `0` is inbound (toward downtown) and `1` is outbound; see :func:`gtfs_demo.presenter.formatters.direction_label`.
5c. **`trip_headsign` propagated.** `Arrival.trip_headsign` carries the static trip's `trip_headsign` (e.g. `"Alewife"` for Red Line northbound). The Streamlit row template renders it as `— toward Alewife` so the user sees the specific destination, not just the inbound/outbound bucket. `None` for ADDED trips that have no static counterpart.
6. **tz-aware times.** All `scheduled_at` / `predicted_at` are `datetime` objects with `tzinfo=ZoneInfo("America/New_York")`. GTFS static times that exceed 24h roll into the next calendar day with the same tz. The `start_date` field on the RT trip descriptor (`YYYYMMDD`) selects the service date; when absent, the wall-clock date is used as a fallback.
7. **Pure functions.** No I/O, no logging, no module-level state. Callers feed in `FeedMessage` + `StaticFeed`; the parser returns a list. The presenter's `next_n_arrivals` is similarly pure.

## Outputs

- `parse(feed_message, static_feed) -> list[Arrival]` — every stop on every TripUpdate, including CANCELED + SKIPPED + UNSCHEDULED + ADDED rows (flagged, not dropped).
- `next_n_arrivals(arrivals, stop_id, n=5) -> list[Arrival]` — sorted by predicted time, filtered to future + SCHEDULED-or-ADDED, capped at `n`.

## Edge cases

- **CANCELED trips**: every stop on the trip is returned with `schedule_relationship=CANCELED`. The presenter excludes them from the default board view; the alerts panel (#7) surfaces them separately.
- **SKIPPED stops**: only the stop with the SKIPPED flag is labelled SKIPPED; the surrounding stops on the same trip remain SCHEDULED.
- **`stop_id` vs `stop_sequence` keys**: RT may key its updates by either. The parser builds both indexes and prefers `stop_id` when both are present.
- **Explicit `time` vs `delay`**: GTFS-RT `StopTimeEvent` allows both. The parser prefers `time` when present; otherwise computes `scheduled_at + delay`.
- **Missing `start_date`**: falls back to today's date in `MBTA_TZ` (won't be a problem for live demo; explicit start_date is the norm).
- **Empty `stop_time_update`**: a trip-level update with no stop-level entries still emits one row per static stop, all with `delay_seconds=None` (and `predicted_at=scheduled_at`).
- **Times exceeding 24h** (e.g. `27:30:00`): split into days + remainder; mapped to the next calendar day with the same tz.

## Out of scope

- VehiclePositions (#6) and ServiceAlerts (#7).
- Streamlit rendering (#11). `next_n_arrivals` is presenter-shaped but doesn't touch Streamlit.
- Cross-trip "next vehicle at this stop" indexing for the live demo board — that's a thin layer over `parse` + `next_n_arrivals` and lives in #11.
- Persisting feed snapshots (post-demo #26).
- Anomaly detection (post-demo #28).

## Verification

- `tests/test_tripupdates_parser.py::test_parses_basic_arrival` — single explicit delay produces correct scheduled/predicted/delay.
- `tests/test_tripupdates_parser.py::test_handles_canceled_trip` — every stop on a CANCELED trip is flagged.
- `tests/test_tripupdates_parser.py::test_partial_stop_time_update_propagates` — delay on stop D propagates to B but not P.
- `tests/test_tripupdates_parser.py::test_added_trip_surfaces_with_flag` — ADDED trip with unknown `trip_id` produces `is_added=True` rows.
- `tests/test_tripupdates_parser.py::test_skipped_stop_is_flagged_individually` — SKIPPED on stop D doesn't infect P or B.
- `tests/test_tripupdates_parser.py::test_parent_station_name_preferred_over_platform_name` — `Arrival.stop_name` resolves to the parent station's name.
- `tests/test_tripupdates_parser.py::test_arrival_carries_parent_station` — Arrival rows for platform-level stops carry their parent station ID.
- `tests/test_tripupdates_parser.py::test_arrival_parent_station_none_for_top_level_stop` — Arrival rows for top-level stations (no parent) report `parent_station=None`.
- `tests/test_arrivals_presenter.py::test_next_n_matches_by_parent_station` — `next_n_arrivals(..., "place-davis")` matches Arrival rows with platform-level `stop_id` whose `parent_station == "place-davis"`.
- `tests/test_arrivals_presenter.py::test_next_n_filters_by_direction_id` — `direction_id=0` returns only inbound rows; `direction_id=1` only outbound; default `None` returns both.
- `tests/test_tripupdates_parser.py::test_arrival_carries_trip_headsign` — static trip's `trip_headsign` propagates onto every Arrival row.
- `tests/test_formatters.py::test_direction_label` — three-case truth table (0, 1, None) plus an unrecognised value falling back to "Unknown".
- `tests/test_formatters.py::test_format_arrival_row_carries_headsign` — `format_arrival_row` surfaces the headsign string for the renderer.
- `tests/test_arrivals_presenter.py::test_next_n_at_davis` — top-5 future arrivals at `place-davis`, sorted, other stops excluded.
- `tests/test_arrivals_presenter.py::test_next_n_at_ball_sq` — same for `place-balsq`; past arrivals filtered.
- `tests/test_arrivals_presenter.py::test_canceled_and_skipped_excluded_from_board` — CANCELED, SKIPPED, UNSCHEDULED filtered; SCHEDULED + ADDED retained.
- `tests/test_arrivals_presenter.py::test_n_caps_result_size` — explicit `n` honoured.

Manual:

```bash
uv run python - <<'PY'
from gtfs_demo.fetcher.realtime import fetch_feed
from gtfs_demo.fetcher.static import fetch_static_feed
from gtfs_demo.parser.static import filter_to_scope, load_feed_from_dir
from gtfs_demo.parser.tripupdates import parse
from gtfs_demo.feeds import TRIP_UPDATES_URL
from gtfs_demo.presenter.arrivals import next_n_arrivals

static = filter_to_scope(load_feed_from_dir(fetch_static_feed()))
rt = fetch_feed(TRIP_UPDATES_URL)
arrivals = parse(rt, static)
for a in next_n_arrivals(arrivals, "place-davis"):
    print(a.predicted_at, a.trip_id, a.delay_seconds)
PY
```

## Open questions

_None._
