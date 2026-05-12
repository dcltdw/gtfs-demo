---
id: F-002
title: GTFS-RT HTTP fetcher (TripUpdates / VehiclePositions / ServiceAlerts)
type: functional
status: in-progress
issue: 4
pr: null
depends_on: []
owner: dcltdw
last_updated: 2026-05-11
---

## Summary

Fetch one of the three GTFS-RT protobuf feeds — `TripUpdates`, `VehiclePositions`, or `Alerts` — from the MBTA's public CDN, decode it into a `gtfs_realtime_pb2.FeedMessage`, and return it. The fetcher carries an identifying `User-Agent`, enforces a per-URL outbound rate limit, retries transient HTTP failures with exponential backoff, and raises typed exceptions on permanent failure so the caller can choose between giving up and degrading gracefully.

The fetcher does not parse trip-level data — that lives in F-003 / F-004 / F-005. F-002 is the I/O surface they share.

This spec absorbs what the originating issue (#4) called `NF-001-outbound-rate-limit`, `NF-006-user-agent`, and `NF-007-retry-backoff`. Those NF numbers were already taken in `REQUIREMENTS.md` by the time the issue was implemented, so the three properties are documented here as `Properties` of F-002 instead of separate NF specs.

## Inputs

- `feed_url` (one of `gtfs_demo.feeds.TRIP_UPDATES_URL`, `VEHICLE_POSITIONS_URL`, `SERVICE_ALERTS_URL`).
- `Settings.gtfs_user_agent` (env: `GTFS_USER_AGENT`; default: `gtfs-demo/0.1.0 (David Leung; claude.unraveled663@simplelogin.com)`).
- `Settings.gtfs_rt_fetch_interval_seconds` (env: `GTFS_RT_FETCH_INTERVAL_SECONDS`; default: 10).
- Optional injectable `rate_limiter` and `session` for tests.

## Properties

1. **Identifying User-Agent.** Every outbound HTTP request carries the `User-Agent` from settings — `<app>/<version> (<maintainer name>; <disclosure email>)`. Identifies the app to MBTA ops in case of feed abuse; uses the project's documented SimpleLogin alias as the disclosure address (see §6).
2. **Outbound rate limit.** A per-URL minimum-interval limiter prevents two fetches of the same feed within `gtfs_rt_fetch_interval_seconds` seconds (default 10s). Limits are per-URL, so the three feeds can fetch independently.
3. **Retry with exponential backoff.** Transient HTTP failures (5xx, `requests.Timeout`, `requests.ConnectionError`) are retried using tenacity with `wait_exponential(min=2, max=8)` and `stop_after_attempt(3)`. After three failed attempts, a `TransientFeedError` is raised.
4. **No retry on permanent failures.** Any 4xx response, malformed-protobuf decode, or other non-retryable `RequestException` raises `PermanentFeedError` on the first attempt.
5. **Structured logging.** Every fetch attempt emits one log line at INFO (success) or WARNING/ERROR (failure) with `url`, `status` (where applicable), `attempt`, `latency_ms`, and `bytes`. Uses stdlib `logging` so a downstream handler can format JSON.
6. **Protobuf decode.** The response body is parsed into `gtfs_realtime_pb2.FeedMessage` via `gtfs-realtime-bindings`. Decode failures raise `PermanentFeedError` (a malformed feed isn't fixed by retrying).

## Outputs

- `gtfs_realtime_pb2.FeedMessage` on success.
- `TransientFeedError` after `stop_after_attempt(3)` is exhausted.
- `PermanentFeedError` on the first 4xx or decode failure.
- One structured log line per attempt.

## Edge cases

- **Process-level limiter sharing**: the default singleton `OutboundRateLimiter` is module-level. Tests inject their own to avoid cross-test contamination. Reset is intentional: production code paths share one limiter instance per process.
- **Empty / zero-byte response**: protobuf decode succeeds (a zero-entity `FeedMessage` is valid) and the caller sees an empty `entity` list. This is treated as a successful fetch, not an error — the realtime feed is allowed to be empty between events.
- **Feed URL not in the project's constants**: `fetch_feed` accepts any URL string. Useful for tests; production callers should use the constants from `gtfs_demo.feeds`.
- **`requests.Timeout` on every attempt**: classified as transient, retried up to 3 times, then `TransientFeedError`.
- **HTTPS connection refused (e.g. invalid hostname)**: surfaces as `requests.ConnectionError` → `TransientFeedError` after 3 attempts. The "stale fallback" logic for this case lives in F-006 (#8), not here.

## Out of scope

- Caching responses (the realtime feed is by definition realtime — caching is anti-feature).
- Conditional `If-Modified-Since` requests (post-demo #16).
- Stale-feed fallback / degraded mode (pre-demo #8).
- Per-IP inbound rate limiting (post-demo #40).
- Token-bucket vs sliding-window ADR (post-demo #41).
- Async fetch / WebSocket push (post-demo #29).

## Verification

- `tests/test_realtime_fetcher.py::test_user_agent_header_present` — `User-Agent` matches settings.
- `tests/test_realtime_fetcher.py::test_outbound_rate_limit_blocks_second_call` — second fetch within the interval sleeps the right duration.
- `tests/test_realtime_fetcher.py::test_retry_on_5xx_then_success` — 502 then 200 yields a successful decode.
- `tests/test_realtime_fetcher.py::test_no_retry_on_4xx` — 400 raises `PermanentFeedError`, exactly one HTTP attempt made.
- `tests/test_realtime_fetcher.py::test_parses_protobuf_from_fixture` — committed `tripupdates_sample.pb` decodes to a `FeedMessage` with 20 entities.
- `tests/test_realtime_fetcher.py::test_transient_after_max_retries_raises_typed_error` — three 5xx → `TransientFeedError` after 3 attempts.
- `tests/test_realtime_fetcher.py::test_timeout_is_transient` — `requests.Timeout` is retried and then surfaces as `TransientFeedError`.
- `tests/test_realtime_fetcher.py::test_rate_limiter_per_url_independence` — two URLs share no quota.

Manual:

```bash
uv run python -c "from gtfs_demo.fetcher.realtime import fetch_feed; \
                  from gtfs_demo.feeds import TRIP_UPDATES_URL; \
                  feed = fetch_feed(TRIP_UPDATES_URL); \
                  print(len(feed.entity), 'entities')"
```

## Open questions

_None._
