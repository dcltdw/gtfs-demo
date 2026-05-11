---
id: F-006
title: Feed staleness detection + graceful degradation + metrics
type: functional
status: in-progress
issue: 8
pr: null
depends_on: [F-002]
owner: dcltdw
last_updated: 2026-05-11
---

## Summary

Layer a stateful tracker on top of the stateless :func:`fetch_feed` so the Streamlit feed-health panel and the alerts/arrivals pipelines can distinguish three operational states: **fresh**, **stale data**, and **degraded fetch**. The tracker caches the last successful :class:`FeedMessage` per feed URL, exposes a per-feed :class:`FeedHealth` record (age, stale flag, last-success time, degraded flag), and surfaces a thin metrics dict that the post-demo Prometheus exporter (#33) will translate.

This spec absorbs what the originating issue called `NF-008-feed-staleness` and `NF-009-feed-age-metrics`. Both numbers were unallocated in `REQUIREMENTS.md`, but the work is one cohesive feature and folding the properties into a single F-006 matches the pattern from F-002 / F-003 / F-005.

## Inputs

- `feed_url: str` — one of `gtfs_dleung.feeds.{TRIP_UPDATES_URL, VEHICLE_POSITIONS_URL, SERVICE_ALERTS_URL}`.
- `Settings.gtfs_stale_threshold_s` (env: `GTFS_STALE_THRESHOLD_S`; default 30) — seconds above which data is considered stale. MBTA publishes ~5s, so 30s is a real publisher problem.
- Optional injectable `fetch_fn` and `now_fn` for tests.

## Properties

1. **Last-success cache.** On every successful fetch, the tracker stores the message in an in-memory dict keyed by feed URL.
2. **Graceful degradation.** When a fetch raises :class:`FeedFetchError`, the tracker returns the cached message + a :class:`FeedHealth` with ``is_degraded=True``. Only when there is no cache at all does the error propagate.
3. **Two-axis health.** ``FeedHealth.is_stale`` reflects the data (now − ``header.timestamp`` > threshold); ``FeedHealth.is_degraded`` reflects the **fetch path** (current attempt failed → serving cache). Fresh data over a now-broken connection shows ``is_stale=False, is_degraded=True``.
4. **Transition logging, not per-fetch noise.** A structured log line is emitted only on fresh↔stale transitions per feed. A perpetually-stale feed logs once, not on every poll.
5. **Per-feed metrics.** ``fetches_total`` (every call), ``fetch_errors_total`` (failures), ``feed_age_seconds`` (gauge of the most recent successful fetch's age). The dict is keyed by feed URL; future Prometheus translation (post-demo #33) is documented in code as a TODO.
6. **Missing `header.timestamp`.** Some implementations omit it; the tracker reports ``age_seconds=None`` and ``is_stale=False`` rather than crashing.
7. **Thread-safe state.** A module-level `threading.Lock` guards the singleton's mutable dicts. The Streamlit page (#11) drives this from a session thread; a future async fetcher (post-demo) would replace it with `asyncio.Lock`.
8. **Pure surface where it matters.** :class:`HealthTrackedFetcher` itself is constructible (tests pass their own instance); the module-level singleton + thin wrapper functions exist only for the public API the issue specifies.

## Outputs

- `HealthTrackedFetcher.fetch(feed_url) -> tuple[FeedMessage, FeedHealth]`
- `HealthTrackedFetcher.get_health() -> dict[FeedType, FeedHealth]`
- `HealthTrackedFetcher.get_metrics() -> dict[str, dict[str, int | float]]`
- Module-level: `fetch_with_health`, `get_feed_health`, `get_metrics`, `reset_tracker_for_tests`.

## Edge cases

- **First fetch fails**: no cache → the underlying exception propagates. This is intentional — degradation only makes sense when there's a known-good prior.
- **`header.timestamp` missing**: `age_seconds=None`, `is_stale=False`. The Streamlit panel can show "no timestamp" rather than a misleading "stale" badge.
- **Feed published in the future** (clock skew): `age_seconds` goes negative; `is_stale` stays False. Acceptable for the spike; a future hardening could clamp to zero.
- **Threshold reconfigured at runtime**: `_compute_health` reads `self._settings.gtfs_stale_threshold_s` every call, so a new setting takes effect on the next health computation without restart.
- **Singleton state leaks between tests**: `reset_tracker_for_tests()` clears the module-level singleton. Tests are expected to instantiate their own :class:`HealthTrackedFetcher` to avoid the singleton entirely.

## Out of scope

- **Prometheus `/metrics` endpoint**: tracked as post-demo #33. The metrics dict here is the input to that exporter; the translation is the future PR's job.
- **Per-IP / per-session rate limiting** for inbound traffic (post-demo #40).
- **Persisting health/metrics across process restarts** (the dict is in-memory).
- **Async fetch path** (post-demo #29 / WebSocket push).
- **Trend windows** (rolling 5-min error rate, etc.) — the metrics dict carries raw counters; rolling windows live downstream.

## Verification

- `tests/test_feed_health.py::test_stale_when_timestamp_older_than_threshold` — `age_seconds=60` with `threshold=30` → `is_stale=True`.
- `tests/test_feed_health.py::test_fresh_when_timestamp_within_threshold` — `age_seconds=5` → `is_stale=False`.
- `tests/test_feed_health.py::test_falls_back_to_cache_on_fetch_failure` — success-then-failure returns the cached message + `is_degraded=True`.
- `tests/test_feed_health.py::test_raises_when_first_fetch_fails_with_no_cache` — no-cache + failure propagates the error.
- `tests/test_feed_health.py::test_metrics_counters_increment` — four fetches (2 ok + 2 failure) → `fetches_total=4, fetch_errors_total=2`.
- `tests/test_feed_health.py::test_staleness_transition_logs_once` — `[fresh, fresh, stale, stale, fresh]` → exactly two transition log records.
- `tests/test_feed_health.py::test_get_health_aggregates_across_feeds` — fetching both `trip_updates` and `vehicle_positions` puts both keys in `get_health()`.
- `tests/test_feed_health.py::test_feed_message_without_header_timestamp_reports_none_age` — missing `header.timestamp` → `age_seconds=None`.

Manual:

```bash
uv run python - <<'PY'
from gtfs_dleung.feeds import TRIP_UPDATES_URL
from gtfs_dleung.fetcher.health import fetch_with_health, get_metrics
for _ in range(3):
    msg, health = fetch_with_health(TRIP_UPDATES_URL)
    print(health)
print(get_metrics())
PY
```

## Open questions

_None._
