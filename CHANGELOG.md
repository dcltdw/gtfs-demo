# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- CI pipeline (`.github/workflows/pr-tests.yml`) with parallel `lint` / `typecheck` / `test` jobs on Python 3.13 + uv; cancel-in-progress on PR commits, every push to `main` verified.
- `.pre-commit-config.yaml` with ruff, mypy, `detect-secrets`, and file-hygiene hooks; `.secrets.baseline` checked in.
- `pre-commit` + `detect-secrets` added to dev deps; `just precommit` recipe runs the full hook suite.
- `docs/agent-spec/NF-012-ci-pipeline.md` — the spec file for the CI gate.
- `tests/test_typing.py::test_strict_mypy_clean_on_package` — placeholder marker (the CI `typecheck` job is the real gate).
- Static GTFS feed loader (`gtfs_dleung.fetcher.static.fetch_static_feed`) with 7-day TTL cache, configurable cache dir + URL via `pydantic-settings`, identifying `User-Agent`, typed `StaticFeedError` on failure.
- GTFS-RT HTTP fetcher (`gtfs_dleung.fetcher.realtime.fetch_feed`) returning a decoded `FeedMessage`. Per-URL outbound rate limit (10s default), tenacity exponential-backoff retry (2–8s, 3 attempts) on 5xx + timeouts, typed `TransientFeedError` / `PermanentFeedError`, structured per-attempt logging.
- TripUpdates parser (`gtfs_dleung.parser.tripupdates.parse`) returning typed `Arrival` rows. Handles trip-level + stop-level `schedule_relationship`, partial StopTimeUpdate propagation (downstream stops inherit the last explicit delay), and ADDED trips (RT references a `trip_id` absent from the static feed → `is_added=True`). Times are tz-aware `datetime` in `America/New_York`.
- VehiclePositions parser (`gtfs_dleung.parser.vehicles.parse`) returning typed `VehiclePosition` rows; scope-filtered to Red + Green-E by `trip.route_id`. Keeps `vehicle_id` (system-internal), `vehicle_label` (rider-facing), and `trip_id` distinct.
- `gtfs_dleung.models.vehicle.VehiclePosition` + `VehicleStatus` StrEnum (`INCOMING_AT` / `STOPPED_AT` / `IN_TRANSIT_TO`).
- `tests/fixtures/vehiclepositions_sample.pb` — 2.2 KB trimmed real-feed snapshot (15 entities: 5 Red, 5 Green-E, 5 out-of-scope routes for filter coverage).
- `make_vehiclepositions_feed` helper in `tests/helpers.py`.
- `docs/agent-spec/F-004-vehiclepositions.md` — VehiclePositions spec at the correct F-004 slot (the originating issue's `F-003-vehiclepositions-parser` name conflicted with TripUpdates).
- ServiceAlerts parser (`gtfs_dleung.parser.alerts.parse`) returning typed `ServiceAlert` rows. Two layered filters — scope (informed_entity touches Red / Green-E / corridor parent station) + active-period (overlaps `now`). `now` is a required argument so tests pin time without monkey-patching.
- Feed-health tracker (`gtfs_dleung.fetcher.health.HealthTrackedFetcher`) wrapping the stateless `fetch_feed` with last-success caching, graceful degradation, transition logging, and a metrics dict (`fetches_total`, `fetch_errors_total`, `feed_age_seconds`). Module-level singleton + `fetch_with_health` / `get_feed_health` / `get_metrics` / `reset_tracker_for_tests` thin wrappers.
- `gtfs_dleung.auth` module — `verify_credentials` (bcrypt-checked, three named failure reasons), `build_authenticator_config` (returns the credentials/cookie config the Streamlit page wires up in #11), `log_auth_event` (structured INFO records; raises if a caller passes `password=`).
- `gtfs_dleung.security.rate_limit.SessionRateLimiter` — sliding-window inbound rate limiter, per Streamlit session. In-memory `dict[str, deque[float]]`; lazy idle eviction at 1h. `acquire`, `remaining`, `session_count` API. Thread-safe via `threading.Lock`. Streamlit-page integration deferred to #11.
- `Settings.gtfs_inbound_limit_per_min` / `gtfs_inbound_window_s` / `gtfs_inbound_idle_evict_s` — env-backed (defaults 30 req / 60 s window / 3600 s idle eviction).
- `docs/agent-spec/F-008-inbound-rate-limit.md` — inbound rate-limit spec (absorbs NF-002 from the issue's wording; the correct slot is F-008 per REQUIREMENTS.md).
- `gtfs_dleung.validation.validate_stop_id` — defence-in-depth allow-list of corridor parent stations; rejects platform-level IDs and out-of-scope stops.
- `Settings.gtfs_demo_username`, `gtfs_demo_password_bcrypt`, `gtfs_cookie_key`, `gtfs_cookie_expiry_days` — env-backed. Cookie key is intentionally separate from the password hash.
- `docs/agent-spec/F-007-auth-validation.md` — auth + validation + structured-logging spec (absorbs NF-003/004/005 from the issue's wording).
- `docs/SECURITY.md` gains an expanded rotation checklist (including cookie-key rotation) and an Auth-event-logging section listing the three emitted events.
- `gtfs_dleung.models.feed_health.{FeedHealth, FeedType}` — typed surface for the health panel. `is_stale` and `is_degraded` are independent flags (data age vs fetch failure).
- `Settings.gtfs_stale_threshold_s` (env: `GTFS_STALE_THRESHOLD_S`, default 30) — threshold beyond which feed data is flagged stale.
- `docs/agent-spec/F-006-feed-staleness.md` — staleness + degradation + metrics spec (absorbs NF-008/NF-009 from the issue's wording).
- `gtfs_dleung.models.alert.{ServiceAlert, Cause, Effect, ActivePeriod, InformedEntity}` — typed surface for the alerts panel.
- `tests/fixtures/alerts_sample.pb` — 42 KB trimmed real-feed snapshot (5 in-scope + 3 out-of-scope alerts).
- `make_alerts_feed` helper in `tests/helpers.py`.
- `docs/agent-spec/F-005-servicealerts.md` — ServiceAlerts spec at the correct F-005 slot.
- `gtfs_dleung.models.arrival.Arrival` + `ScheduleRelationship` enum — the user-facing typed boundary for the arrivals board.
- `gtfs_dleung.presenter.arrivals.next_n_arrivals` — pure helper returning the next N future SCHEDULED-or-ADDED arrivals at a stop.
- `tests/helpers.py` — programmatic `FeedMessage` and `StaticFeed` builders so tests can express GTFS-RT scenarios as Python dicts.
- `docs/agent-spec/F-003-tripupdates-arrivals.md` — parser + presenter spec; absorbs what the originating issue split across F-002b/F-006/F-007 (those numbers were already taken).
- `gtfs_dleung.feeds` — `TRIP_UPDATES_URL`, `VEHICLE_POSITIONS_URL`, `SERVICE_ALERTS_URL` constants plus `ALL_FEED_URLS` tuple.
- `gtfs_dleung.fetcher.rate_limit.OutboundRateLimiter` — per-URL minimum-interval limiter.
- `tests/fixtures/tripupdates_sample.pb` — 11 KB protobuf snapshot (20 entities, trimmed from a real MBTA TripUpdates feed).
- `docs/agent-spec/F-002-gtfs-rt-fetcher.md` — fetcher spec covering user-agent, rate-limit, and retry properties (absorbs what #4 originally split across NF-001/006/007 — those numbers were already taken).
- Pydantic v2 models for `Stop`, `Route`, `Trip`, `StopTime`, `Shape`, plus a `StaticFeed` container (`gtfs_dleung.models.static`).
- Scope constants for Red Line (Park ↔ Davis) and Green Line E (Park ↔ Ball Sq) corridors (`gtfs_dleung.scope`).
- Route-aware corridor filter (`gtfs_dleung.parser.static.filter_to_scope`) that drops Green-B/C/D trips even where they share platforms with Green-E.
- `tests/fixtures/mbta-mini.zip` — a 7 KB GTFS bundle trimmed from the real MBTA feed; includes one out-of-scope route (the 39 bus) so the filter is exercised both ways.
- `scripts/build_test_fixture.py` — reproducible script for regenerating the fixture from a freshly-unzipped real MBTA feed.
- `docs/agent-spec/F-001-load-static-feed.md` — the spec file for static-feed ingestion.

### Changed

- README Quickstart and CONTRIBUTING now walk through the pre-commit + CI workflow.
- README Architecture section now describes the static-vs-realtime split and points at the corridor filter.
- README Security section adds the "polite consumer" principle (UA + rate limit + retry).
- GLOSSARY adds `route`, `trip`, `stop_time`, `service_id`, `shape`, `parent station`, "trunk overlap", expanded `schedule_relationship`, `ADDED trip`, `partial StopTimeUpdate / propagation`, `vehicle.id vs vehicle.label`, `current_status`, `informed_entity`, alert `cause`, alert `effect`, `active_period`, `feed staleness vs fetch degradation`, and `feed_age_seconds` entries.
- README Operational notes gains the feed-staleness + degradation paragraph.
- README Security gains the **dual rate limit** paragraph (inbound vs outbound) calling out the different threats each protects against.
- `.env.example` rate-limit env-var names renamed for clarity: `GTFS_INBOUND_RATE_LIMIT_REQUESTS` → `GTFS_INBOUND_LIMIT_PER_MIN`, `GTFS_INBOUND_RATE_LIMIT_WINDOW_SECONDS` → `GTFS_INBOUND_WINDOW_S`, plus new `GTFS_INBOUND_IDLE_EVICT_S`.
- Default `User-Agent` updated from URL-style to maintainer-style (`<app>/<ver> (<name>; <email>)`) to match the §6 disclosure pattern; reflected in `gtfs_dleung/config.py` and `.env.example`.
- `Settings.gtfs_rt_fetch_interval_seconds` (env: `GTFS_RT_FETCH_INTERVAL_SECONDS`) — default 10s.
- README Architecture gains a paragraph describing the TripUpdates parser's two non-obvious behaviours.

## [0.0.1] — 2026-05-11

### Added

- Initial project scaffold: package layout (`gtfs_dleung/{fetcher,parser,store,presenter,cli}`), uv-managed dependencies on Python 3.13, MIT licence, `.gitignore`.
- Documentation skeletons: `README.md`, `REQUIREMENTS.md`, `docs/agent-spec/` (`README.md`, `schema.md`), `docs/SECURITY.md`, `docs/GLOSSARY.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`.
- `docs/AI-COLLABORATION-CONVENTIONS.md` ported from the annotated-maps project — universal rules only (ticket sizing, status lifecycle, default board, PR body sections, commit co-author, public-repo diff scan, doc-as-master, stale-cache refresh). Wave / cadence / midpoint / burst rules dropped as spike-inappropriate.
- `.env.example` with bcrypt-hashed demo credential (rotation policy in `docs/SECURITY.md`).
- `.github/` templates (issue, PR, CODEOWNERS, dependabot).
- `justfile` recipes (`install`, `test`, `lint`, `typecheck`, `demo`, `snapshot`).
- `tests/test_smoke.py` smoke test confirming the package imports cleanly.

[Unreleased]: https://github.com/dcltdw/gtfs-dleung/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/dcltdw/gtfs-dleung/releases/tag/v0.0.1
