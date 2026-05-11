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
- **`schedule_relationship`**: per-stop indicator on a TripUpdate describing whether the stop is `SCHEDULED`, `SKIPPED`, `NO_DATA`, or (newer) `UNSCHEDULED`. Critical for an honest arrivals board.

## MBTA-specific terms

- **Red Line**: heavy rail, branches to Ashmont and Braintree. Spike scope: Park St ↔ Davis Sq (downtown to Cambridge/Somerville).
- **Green Line E branch**: light rail, the only Green Line branch that runs through Lechmere. Spike scope: Park St ↔ Ball Sq.
- **MBTA V3 API**: the REST-shaped API that wraps GTFS-RT. The spike intentionally does NOT use it; see `docs/UPGRADE-PATH.md` (PR #12) for the trade-off.

## Project-specific terms

- **Spike**: a time-boxed exploration with no intent to build a production system. The whole repository is one. See [REQUIREMENTS.md](../REQUIREMENTS.md).
- **Pre-demo issue**: an issue tagged `pre-demo` that must land before the recruiter call. Numbered `#1`–`#14`.
- **Post-demo issue**: an issue tagged `post-demo` enumerating natural follow-ons. Numbered `#15`–`#41`. Explicit non-goals for the spike.
- **Agent spec (`F-NNN-*.md`, `NF-NNN-*.md`)**: a structured spec file. `F-` = functional, `NF-` = non-functional. Schema lives in [docs/agent-spec/schema.md](agent-spec/schema.md).

## Convention terms

- **Convention §N**: a reference to a numbered rule in [docs/AI-COLLABORATION-CONVENTIONS.md](AI-COLLABORATION-CONVENTIONS.md).
- **Memory entry**: a per-rule pointer file under `~/.claude/projects/<project>/memory/`. Per §8, the conventions doc is the master; memory entries are thin replicas.
