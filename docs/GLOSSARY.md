# Glossary

Terms specific to the GTFS ecosystem, the MBTA's flavour of it, and the conventions used in this repository.

## GTFS terms

- **GTFS (General Transit Feed Specification)**: the static schedule format. A zip of CSV files describing routes, stops, trips, stop_times, and service calendars. Updated periodically (MBTA: ~weekly).
- **GTFS-RT (GTFS Realtime)**: the realtime supplement, transported as Protocol Buffers over HTTPS. Three message types:
  - **TripUpdates**: predicted arrival/departure times for in-service trips. Includes `schedule_relationship` per stop (`SCHEDULED`, `SKIPPED`, `NO_DATA`).
  - **VehiclePositions**: live vehicle locations (lat/lon, bearing, speed, occupancy).
  - **ServiceAlerts**: text alerts (planned closures, elevator outages, etc.) with informed-entity selectors.
- **`FeedMessage`**: the top-level GTFS-RT protobuf envelope. Carries a `header` (with `gtfs_realtime_version`, `incrementality`, `timestamp`) plus a list of `entity` objects. Each entity wraps one of `trip_update` / `vehicle` / `alert`. The parser's input type is always `gtfs_realtime_pb2.FeedMessage`.
- **Headway**: the time gap between consecutive trips on the same route + direction (e.g. "Red Line southbound runs every 6 minutes during rush hour" = a 6-minute headway). Distinct from delay, which is per-trip variance from the published schedule. The spike doesn't compute headways but the term appears in MBTA's published schedule data and in the `frequencies.txt` static GTFS file (which the spike intentionally ignores; the demo routes are fully scheduled, not frequency-based).
- **Block**: a sequence of trips assigned to a single vehicle in a single service day (`block_id` in `trips.txt`). A train serving an outbound Red Line trip and then an inbound trip is the same block. Relevant for vehicle-tracking semantics — `vehicle.id` typically stays stable across all trips in a block. Not used by the spike's parsers, but the column appears in the static feed.
- **Trip ID**: unique identifier for one specific trip (a single run of a route in one direction on one date). Must match between static and realtime feeds.
- **Stop ID**: unique identifier for a stop. The MBTA uses suffixed IDs to distinguish platforms (e.g. `place-pktrm` vs `70075`).
- **`schedule_relationship`**: a GTFS-RT label appearing in two places. **Trip-level** (`TripDescriptor.ScheduleRelationship`): `SCHEDULED`, `ADDED`, `UNSCHEDULED`, `CANCELED` (plus deprecated/experimental variants the parser maps to SCHEDULED). **Stop-level** (`StopTimeUpdate.ScheduleRelationship`): `SCHEDULED`, `SKIPPED`, `NO_DATA`, `UNSCHEDULED`. The arrivals parser collapses both into a single user-facing `gtfs_dleung.models.arrival.ScheduleRelationship` enum on each row.
- **`ADDED` trip**: an unscheduled trip introduced at runtime (e.g. a shuttle bus filling in for a disabled train). RT references a `trip_id` not in the static feed; the parser surfaces it with `is_added=True` instead of dropping the row.
- **Partial StopTimeUpdate / propagation**: a TripUpdate's `stop_time_update` list is sparse. The GTFS-RT spec says that when stop K has an explicit delay, every downstream stop on the same trip inherits that delay until the next explicit update. Naively dropping unexplicit stops would lose half the realtime signal; the parser walks static `stop_times` and threads a `current_delay_seconds` accumulator.
- **`vehicle.id` vs `vehicle.label`**: GTFS-RT's `VehicleDescriptor` carries two id-like strings. `id` is the transport-system-internal identifier (serial-number-like, stable across trips; used internally by ops). `label` is the rider-facing label (e.g. `"1701"` painted on the side of an MBTA car). Conflating one for the other is a beginner mistake; the parser keeps them separate.
- **`current_status`** (VehiclePosition): per-vehicle stop status enum. `INCOMING_AT` (about to arrive at `current_stop_sequence`), `STOPPED_AT` (currently stopped), `IN_TRANSIT_TO` (en route).
- **`informed_entity`** (Alert): the GTFS-RT selector format for which entities an alert applies to. Each selector can carry any of `agency_id`, `route_id`, `trip_id`, `stop_id`; an alert with selector `{route_id: "Red"}` applies to the whole Red Line. The parser narrows alerts by checking these selectors against `SCOPE_ROUTES` and `ALL_CORRIDOR_PARENT_STATIONS`.
- **Alert `cause`**: why an alert was issued (`UNKNOWN_CAUSE`, `OTHER_CAUSE`, `TECHNICAL_PROBLEM`, `STRIKE`, `DEMONSTRATION`, `ACCIDENT`, `HOLIDAY`, `WEATHER`, `MAINTENANCE`, `CONSTRUCTION`, `POLICE_ACTIVITY`, `MEDICAL_EMERGENCY`).
- **Alert `effect`**: what the alert means for service (`NO_SERVICE`, `REDUCED_SERVICE`, `SIGNIFICANT_DELAYS`, `DETOUR`, `ADDITIONAL_SERVICE`, `MODIFIED_SERVICE`, `OTHER_EFFECT`, `UNKNOWN_EFFECT`, `STOP_MOVED`, `NO_EFFECT`, `ACCESSIBILITY_ISSUE`).
- **`active_period`**: list of `[start, end)` TimeRange entries describing when an alert applies. Empty list means "always on" per GTFS-RT spec. Either side may be missing (open-ended in that direction).
- **Feed staleness vs fetch degradation**: two independent signals on `FeedHealth`. **Stale** means the data is old (`now − header.timestamp > GTFS_STALE_THRESHOLD_S`, default 30s). **Degraded** means our most recent fetch failed and we're serving the cached last-good message. Fresh data over a now-broken connection is `is_stale=False, is_degraded=True`; perpetually-stale publisher with our fetches still succeeding is `is_stale=True, is_degraded=False`.
- **`feed_age_seconds`**: gauge metric on the metrics dict; the age of the most recently received `FeedMessage` for a feed URL. Drives the Streamlit feed-health panel; future Prometheus translation lives in post-demo #33.
- **Route**: one of the named services in `routes.txt` (e.g. `Red`, `Green-E`). `route_type` distinguishes mode (0 = tram/streetcar, 1 = subway, 2 = rail, 3 = bus).
- **Trip**: one run of a route in one direction (`trips.txt`). Identified by `trip_id`; references a `route_id`, a `service_id`, optionally a `shape_id`.
- **`stop_time`**: one row in `stop_times.txt` tying a `trip_id` to a `stop_id` with arrival + departure times and a `stop_sequence`. Times may exceed 24h (e.g. `27:30:00`) for trips that span midnight on the prior service day.
- **`service_id`**: identifier in `calendar.txt` / `calendar_dates.txt` describing which days a trip runs (e.g. `Weekday`, `Saturday`, `Holiday-Memorial`). Trips link to dates through this.
- **Shape**: an ordered list of lat/lon points (`shapes.txt`) describing the geometry of a trip's route, indexed by `shape_id`. Each row is one point with a `shape_pt_sequence`.
- **Parent station**: a station-level `stop_id` (MBTA convention: `place-*`) with multiple platform-level `stop_id`s linked via `parent_station`. Filtering on parent stations catches all platforms for a stop.

## MBTA-specific terms

- **Red Line**: heavy rail, branches to Ashmont and Braintree. Spike scope: Park St ↔ Davis Sq (downtown to Cambridge/Somerville).
- **Green Line E branch**: light rail, the only Green Line branch that runs through Lechmere on the Medford/Tufts extension. Spike scope: Park St ↔ Ball Sq.
- **Trunk overlap**: the four Green Line branches (B/C/D/E) share platforms downtown — Park Street, Boylston, Arlington, Copley. A scope filter using only stop IDs would incorrectly keep B/C/D trips; route-id filtering is required.
- **MBTA V3 API**: the REST-shaped API that wraps GTFS-RT (`https://api-v3.mbta.com/`). The spike intentionally does NOT use it; see [docs/UPGRADE-PATH.md](UPGRADE-PATH.md) and [ADR 0003](adr/0003-strict-gtfs-rt.md) for the trade-off.

## Project-specific terms

- **Spike**: a time-boxed exploration with no intent to build a production system. The whole repository is one. See [REQUIREMENTS.md](../REQUIREMENTS.md).
- **Pre-demo issue**: an issue tagged `pre-demo` that must land before the recruiter call. Numbered `#1`–`#14`.
- **Post-demo issue**: an issue tagged `post-demo` enumerating natural follow-ons. Numbered `#15`–`#41`. Explicit non-goals for the spike.
- **Agent spec (`F-NNN-*.md`, `NF-NNN-*.md`)**: a structured spec file. `F-` = functional, `NF-` = non-functional. Schema lives in [docs/agent-spec/schema.md](agent-spec/schema.md).

## Convention terms

- **Convention §N**: a reference to a numbered rule in [docs/AI-COLLABORATION-CONVENTIONS.md](AI-COLLABORATION-CONVENTIONS.md).
- **Memory entry**: a per-rule pointer file under `~/.claude/projects/<project>/memory/`. Per §8, the conventions doc is the master; memory entries are thin replicas.
