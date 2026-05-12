---
id: F-005
title: ServiceAlerts parser
type: functional
status: in-progress
issue: 7
pr: null
depends_on: [F-002]
owner: dcltdw
last_updated: 2026-05-11
---

## Summary

Decode the GTFS-RT `Alerts.pb` feed into typed `ServiceAlert` rows, narrowed by two layered filters: **scope** (informed_entity touches Red Line, Green-E, or a corridor parent station) and **active-period** (at least one TimeRange overlaps the supplied `now`). The parser is pure; `now` is a required argument so tests pin time without monkey-patching.

This spec replaces what the originating issue called `F-004-servicealerts-parser`. The `F-004` slot was taken by `VehiclePositions` (issue #6); the correct number for ServiceAlerts is `F-005`, matching `REQUIREMENTS.md`. Same pattern as PRs #45–47.

## Inputs

- `feed_message: gtfs_realtime_pb2.FeedMessage` — the decoded RT envelope from F-002.
- `now: datetime` — wall-clock anchor for the active-period filter. Required (no ambient `datetime.now()` read).
- `scope_routes: frozenset[str]` — defaults to `gtfs_demo.scope.SCOPE_ROUTES`.
- `scope_stops: frozenset[str]` — defaults to `gtfs_demo.scope.ALL_CORRIDOR_PARENT_STATIONS`.

## Properties

1. **Scope filter (stop-aware route check).** An alert is kept iff one of:
   - **(stops present)** any `informed_entity` carries a `stop_id` AND at least one such `stop_id` is in `scope_stops`; OR
   - **(no stops)** no `informed_entity` carries a `stop_id` at all AND at least one carries `route_id ∈ scope_routes`.

   This shape — rather than a flat "any route OR any stop" — is required because MBTA tags every Red Line alert with `route_id="Red"` in addition to specific `stop_id` selectors. A flat-OR filter kept alerts whose stops were entirely outside our Park ↔ Alewife corridor (e.g. "elevator outage at Andrew", south of Park) just because of the route tag. Alerts with no informed_entity are still dropped (they don't target anything we care about).
2. **Active-period filter.** An alert is kept iff at least one of its `active_period` ranges covers `now`. Per the GTFS-RT spec, an alert with no `active_period` is considered always-on and survives. Missing `start` means "always active before `end`"; missing `end` means "always active after `start`".
3. **Cause / Effect enums.** Both protobuf int enums (`Alert.Cause`, `Alert.Effect`) map to user-facing `StrEnum` classes (`Cause`, `Effect`). Unknown protobuf values fall back to `UNKNOWN_CAUSE` / `UNKNOWN_EFFECT` (don't break the parser when GTFS-RT extends the enum).
4. **Translation preference.** `header_text` and `description_text` are GTFS-RT `TranslatedString` fields (potentially multi-language). The parser prefers `language == "en"`; falls back to the first translation if no English version is present.
5. **InformedEntity preservation.** Every selector is preserved as-is on the row (agency_id, route_id, trip_id, stop_id). The alerts panel and any later analytics can re-filter.
6. **Pure function.** No I/O, no logging, no module-level state. `now` is a parameter, not a sensed value.

## Outputs

- `parse(feed_message, *, now, scope_routes=SCOPE_ROUTES, scope_stops=ALL_CORRIDOR_PARENT_STATIONS) -> list[ServiceAlert]`

## Edge cases

- **Entity without `alert` field**: skipped (same as F-003/F-004 — the same `FeedMessage` may carry mixed entity types in principle).
- **Alert with no `informed_entity`**: dropped (we can't tell if it touches the scope).
- **Alert with no `active_period`**: kept (always-on per spec).
- **TimeRange with both `start` and `end` missing**: equivalent to no active_period at all; kept.
- **Future-only TimeRange**: dropped today, eventually kept when `now` enters the range.
- **Multilingual `header_text`** without `en`: parser uses the first translation; the demo audience is English, so this is a non-issue for MBTA but worth knowing.
- **GTFS-RT extending `Cause`/`Effect`**: unknown enum values map to UNKNOWN_*; parser doesn't crash.

## Out of scope

- Streamlit rendering of the alerts panel (#11).
- Multi-language UI (the spike serves English only).
- Severity-level filtering (the proto has `SeverityLevel`; not used for the spike — could add post-demo).
- Per-trip filtering when an alert's only selector is `trip_id` (the alert is dropped today since we don't join with the static feed here). Acceptable for the spike since real MBTA alerts almost always carry `route_id` or `stop_id` alongside.

## Verification

- `tests/test_alerts_parser.py::test_basic_parse` — header/description/cause/effect/period/informed_entity all populate.
- `tests/test_alerts_parser.py::test_filters_by_informed_route` — Red, Green-E, and corridor-stop alerts kept; Green-D, CR-Worcester, and no-informed_entity dropped.
- `tests/test_alerts_parser.py::test_red_line_alert_at_out_of_corridor_stop_is_dropped` — `[{route_id: Red, stop_id: place-andrw}]` dropped despite the route tag (Andrew is south of Park, out of corridor).
- `tests/test_alerts_parser.py::test_red_line_systemwide_alert_with_no_stops_is_kept` — `[{route_id: Red}]` kept (no stop selectors at all → route match is the gate).
- `tests/test_alerts_parser.py::test_alert_touching_in_and_out_of_corridor_stops_is_kept` — a multi-stop alert hitting Andrew AND Davis is kept (the in-scope stop saves it).
- `tests/test_alerts_parser.py::test_excludes_expired_alerts` — past + future weekend alerts dropped; only the alert covering `now` survives.
- `tests/test_alerts_parser.py::test_alert_with_no_active_period_is_always_on` — empty `active_period` survives.
- `tests/test_alerts_parser.py::test_alert_with_only_start_is_active_after_start` — open-ended-on-the-right TimeRange.
- `tests/test_alerts_parser.py::test_alert_with_only_end_is_active_until_end` — open-ended-on-the-left TimeRange.
- `tests/test_alerts_parser.py::test_cause_and_effect_enum_mapping` — sample of Cause + Effect values map correctly.
- `tests/test_alerts_parser.py::test_parses_real_fixture` — committed `alerts_sample.pb` (5 in-scope + 3 out-of-scope) decodes; every kept alert touches scope.

Manual:

```bash
uv run python -c "from datetime import UTC, datetime; \
                  from gtfs_demo.fetcher.realtime import fetch_feed; \
                  from gtfs_demo.feeds import SERVICE_ALERTS_URL; \
                  from gtfs_demo.parser.alerts import parse; \
                  alerts = parse(fetch_feed(SERVICE_ALERTS_URL), now=datetime.now(tz=UTC)); \
                  print(len(alerts), 'active in-scope alerts'); \
                  [print(' -', a.header_text) for a in alerts]"
```

## Open questions

_None._
