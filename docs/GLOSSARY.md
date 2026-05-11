# Glossary

Terms specific to the GTFS ecosystem, the MBTA's flavour of it, and the conventions used in this repository.

## GTFS terms

- **GTFS (General Transit Feed Specification)**: the static schedule format. A zip of CSV files describing routes, stops, trips, stop_times, and service calendars. Updated periodically (MBTA: ~weekly).
- **GTFS-RT (GTFS Realtime)**: the realtime supplement, transported as Protocol Buffers over HTTPS. Three message types:
  - **TripUpdates**: predicted arrival/departure times for in-service trips. Includes `schedule_relationship` per stop (`SCHEDULED`, `SKIPPED`, `NO_DATA`).
  - **VehiclePositions**: live vehicle locations (lat/lon, bearing, speed, occupancy).
  - **ServiceAlerts**: text alerts (planned closures, elevator outages, etc.) with informed-entity selectors.
- **Trip ID**: unique identifier for one specific trip (a single run of a route in one direction on one date). Must match between static and realtime feeds.
- **Stop ID**: unique identifier for a stop. The MBTA uses suffixed IDs to distinguish platforms (e.g. `place-pktrm` vs `70075`).
- **`schedule_relationship`**: a GTFS-RT label appearing in two places. **Trip-level** (`TripDescriptor.ScheduleRelationship`): `SCHEDULED`, `ADDED`, `UNSCHEDULED`, `CANCELED` (plus deprecated/experimental variants the parser maps to SCHEDULED). **Stop-level** (`StopTimeUpdate.ScheduleRelationship`): `SCHEDULED`, `SKIPPED`, `NO_DATA`, `UNSCHEDULED`. The arrivals parser collapses both into a single user-facing `gtfs_dleung.models.arrival.ScheduleRelationship` enum on each row.
- **`ADDED` trip**: an unscheduled trip introduced at runtime (e.g. a shuttle bus filling in for a disabled train). RT references a `trip_id` not in the static feed; the parser surfaces it with `is_added=True` instead of dropping the row.
- **Partial StopTimeUpdate / propagation**: a TripUpdate's `stop_time_update` list is sparse. The GTFS-RT spec says that when stop K has an explicit delay, every downstream stop on the same trip inherits that delay until the next explicit update. Naively dropping unexplicit stops would lose half the realtime signal; the parser walks static `stop_times` and threads a `current_delay_seconds` accumulator.
- **`vehicle.id` vs `vehicle.label`**: GTFS-RT's `VehicleDescriptor` carries two id-like strings. `id` is the transport-system-internal identifier (serial-number-like, stable across trips; used internally by ops). `label` is the rider-facing label (e.g. `"1701"` painted on the side of an MBTA car). Conflating one for the other is a beginner mistake; the parser keeps them separate.
- **`current_status`** (VehiclePosition): per-vehicle stop status enum. `INCOMING_AT` (about to arrive at `current_stop_sequence`), `STOPPED_AT` (currently stopped), `IN_TRANSIT_TO` (en route).
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
- **MBTA V3 API**: the REST-shaped API that wraps GTFS-RT. The spike intentionally does NOT use it; see `docs/UPGRADE-PATH.md` (PR #12) for the trade-off.

## Project-specific terms

- **Spike**: a time-boxed exploration with no intent to build a production system. The whole repository is one. See [REQUIREMENTS.md](../REQUIREMENTS.md).
- **Pre-demo issue**: an issue tagged `pre-demo` that must land before the recruiter call. Numbered `#1`–`#14`.
- **Post-demo issue**: an issue tagged `post-demo` enumerating natural follow-ons. Numbered `#15`–`#41`. Explicit non-goals for the spike.
- **Agent spec (`F-NNN-*.md`, `NF-NNN-*.md`)**: a structured spec file. `F-` = functional, `NF-` = non-functional. Schema lives in [docs/agent-spec/schema.md](agent-spec/schema.md).

## Convention terms

- **Convention §N**: a reference to a numbered rule in [docs/AI-COLLABORATION-CONVENTIONS.md](AI-COLLABORATION-CONVENTIONS.md).
- **Memory entry**: a per-rule pointer file under `~/.claude/projects/<project>/memory/`. Per §8, the conventions doc is the master; memory entries are thin replicas.
