---
id: F-008
title: Inbound rate limiting (sliding-window, per Streamlit session)
type: functional
status: in-progress
issue: 10
pr: null
depends_on: []
owner: dcltdw
last_updated: 2026-05-11
---

## Summary

Throttle data-fetching handlers in the Streamlit app on a per-session basis: 30 requests per 60-second sliding window (configurable). Sessions that exceed their budget get a `False` from :meth:`SessionRateLimiter.acquire`; the Streamlit page (#11) catches that and shows a friendly throttle banner while serving cached data. In-memory `dict[str, deque[float]]` keyed by session ID. Idle sessions are evicted after one hour to keep the limiter's memory bounded.

This spec replaces what the originating issue called `NF-002-inbound-rate-limit`. `NF-002` is already used in `REQUIREMENTS.md` (`Type safety`); the correct slot for inbound RL is `F-008`, matching the REQUIREMENTS row. Same numbering-deviation pattern as F-002 / F-003 / F-005 / F-006 / F-007.

This pairs with [F-002 §Properties.2](./F-002-gtfs-rt-fetcher.md) (the outbound polite-consumer limiter): inbound = our-app-side abuse protection, outbound = MBTA-side neighbour politeness. The two live in separate modules by intent (`gtfs_demo.security.rate_limit` vs `gtfs_demo.fetcher.rate_limit`).

## Inputs

- `Settings.gtfs_inbound_limit_per_min` (env: `GTFS_INBOUND_LIMIT_PER_MIN`; default `30`).
- `Settings.gtfs_inbound_window_s` (env: `GTFS_INBOUND_WINDOW_S`; default `60`).
- `Settings.gtfs_inbound_idle_evict_s` (env: `GTFS_INBOUND_IDLE_EVICT_S`; default `3600`).
- Constructor takes `limit` + `window_s` positionally to match the issue's API surface; `idle_evict_s` is keyword-only.
- `acquire(session_id, *, now=None)` — `session_id` is an opaque string (Streamlit's session id from the runtime context). `now` is injectable monotonic seconds for tests.

## Properties

1. **Sliding window, not token bucket.** Each `acquire(session_id)` drops timestamps older than `window_s` and appends `now` if budget remains. Conceptually simple; one parameter instead of two (no refill rate). A token-bucket comparison ADR is post-demo #41.
2. **Per session, not per IP.** Bucket key is the session ID Streamlit assigns. A future per-IP layer (especially valuable if the app ever becomes unauthenticated) is post-demo #40.
3. **In-memory only.** No Redis, no persistence, no shared state across processes. Restarting the app clears all buckets. For a single-replica spike this is fine; multi-replica deployments need a shared store.
4. **Lazy idle eviction.** Each `acquire` call sweeps the bucket dict, dropping any session whose most recent event is older than `idle_evict_s`. O(n_sessions) per call — at the spike's expected ~100 concurrent sessions, unmeasurably cheap.
5. **Thread-safe.** A single `threading.Lock` guards all mutation. Streamlit's session threads can call into one limiter instance concurrently.
6. **Structured log on throttle.** A throttled `acquire` emits one INFO record (`inbound rate-limit throttle session_id=<id> used=<n> limit=<m> window_s=<s>`). Pure-allow paths are silent — no per-request log spam.
7. **`remaining` for UI affordances.** Doesn't consume budget; callers can render "x requests left in this window."
8. **Constructor validates arguments.** Bad input (`limit=0`, `window_s=0`, `idle_evict_s ≤ window_s`) raises `ValueError` immediately rather than silently misbehaving.
9. **Streamlit integration deferred.** This spec ships the limiter as a testable class. The Streamlit page in #11 wires it into the data-fetching handlers and the throttle banner.

## Outputs

- `SessionRateLimiter(limit=30, window_s=60.0, *, idle_evict_s=3600.0)` constructor.
- `acquire(session_id, *, now=None) -> bool`.
- `remaining(session_id, *, now=None) -> int`.
- `session_count() -> int` — operational visibility.

## Edge cases

- **Never-seen session calling `remaining`**: returns the full limit (no bucket allocated).
- **Concurrent acquires from one session**: lock serialises them; the order in which events are added to the deque matches the order of lock acquisition.
- **`now` arg going backwards**: not validated — the caller's responsibility to pass monotonic time. Tests use synthetic `now` values; production uses `time.monotonic`.
- **Idle eviction during heavy use**: the sweep runs in O(n_sessions), so adding a 101st session after 100 idled out is cheap. The lock is held during the sweep — if that ever becomes contention, this is the first thing to revisit.
- **Limit reduced at runtime**: not supported. The constructor's `limit` and `window_s` are fixed for the lifetime of the instance. Operators can restart with new env values.

## Out of scope (post-demo follow-ons)

- **Per-IP rate limiting** (post-demo #40) — particularly valuable for an unauthenticated public surface.
- **Token bucket vs sliding window ADR** (post-demo #41).
- **Redis-backed / distributed state** — multi-replica deployments need this; the spike is single-replica.
- **HTTP 429 + `Retry-After` semantics** — Streamlit isn't a request/response server.
- **Streamlit page integration** — banner UI + cached-data fallback land in #11.
- **Per-route quotas** — different handlers might warrant different budgets. The current limiter is global per session.

## Verification

- `tests/test_rate_limit.py::test_under_limit_allows` — N−1 acquires under limit all return True.
- `tests/test_rate_limit.py::test_over_limit_blocks` — limit+1th and subsequent acquires return False.
- `tests/test_rate_limit.py::test_window_slides` — past-window events are dropped; budget replenishes.
- `tests/test_rate_limit.py::test_independent_sessions_independent_counters` — sessions don't interfere.
- `tests/test_rate_limit.py::test_eviction_after_idle` — sessions idle > `idle_evict_s` are dropped from the bucket dict.
- `tests/test_rate_limit.py::test_remaining_reports_budget` — `remaining` returns budget without consuming.
- `tests/test_rate_limit.py::test_remaining_for_unknown_session` — never-seen session has the full limit.
- `tests/test_rate_limit.py::test_throttle_emits_structured_log` — throttled acquire emits one structured INFO record.
- `tests/test_rate_limit.py::test_constructor_validates_arguments` — bad inputs raise.

Manual (in #11's Streamlit page):

```python
from gtfs_demo.security.rate_limit import SessionRateLimiter
from gtfs_demo.config import get_settings

s = get_settings()
limiter = SessionRateLimiter(s.gtfs_inbound_limit_per_min, s.gtfs_inbound_window_s)

if not limiter.acquire(st.session_state.session_id):
    st.warning("You've hit the rate limit; showing cached data.")
    # fall back to last-good
else:
    # real fetch
```

## Open questions

_None._
