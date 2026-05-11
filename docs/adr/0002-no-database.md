# ADR 0002 — No database; in-memory state only

- **Status**: Accepted
- **Date**: 2026-05-11
- **Author**: dcltdw

## Context

The GTFS-RT pipeline reads three feeds every ~15 s, parses them into typed models, and renders the result. Two questions for state:

1. Where do we store the **last-good** message per feed so a network blip doesn't blank the UI?
2. Where do we accumulate **historical** data so users can see "what did this trip do in the past 30 minutes?"

A database addresses (2); (1) is fine with a process-local dict.

## Decision

No database. All state is in-memory, scoped to the process:

- `HealthTrackedFetcher` keeps `dict[str, FeedMessage]` for the last-success cache + a per-feed metrics dict.
- `SessionRateLimiter` keeps `dict[str, deque[float]]` keyed by Streamlit session ID.
- `@st.cache_resource`-decorated factories cache the parsed static feed for the lifetime of the process.

The Streamlit page restart wipes everything; that's expected.

## Consequences

**Gained:**

- **Zero ops complexity.** No SQLite file to migrate, no Postgres container to start. `just demo` is the entire dev cycle.
- **Trivial test injection.** Tests construct their own `HealthTrackedFetcher` / `SessionRateLimiter` with synthetic time; nothing flows through a persistence layer.
- **No schema drift risk.** A schema migration on a stateful project would compete for the spike's time budget; here it doesn't exist.

**Lost:**

- **No historical analysis.** A rider asking "what's typical delay on the 7 a.m. Red Line train at Davis?" can't be answered — we only see the live snapshot. Post-demo issues #26 (DuckDB persistence of RT feed snapshots), #27 (delay distribution dashboard), and #34 (schedule-vs-actual chart) all depend on this gap being filled.
- **Restart wipes everything.** A process restart drops every session's rate-limit bucket, the last-success cache, and the in-flight Streamlit auth cookies (these last because `streamlit-authenticator` stores them client-side and the cookie key is the same across restarts — but if the key is rotated, every session is invalidated).
- **Single-replica only.** Two Streamlit processes can't share rate-limit state; a load balancer in front of two replicas would let a single attacker get 2× the per-session budget. Multi-replica needs Redis or equivalent (post-demo #40 for per-IP, ADR #41 for the token-bucket vs sliding-window comparison).
- **No audit trail beyond stdlib logging.** Auth events go to stdout; once the process dies, they're gone unless something is scraping the logs. Durable audit log is post-demo #38.

## Alternatives considered

- **SQLite for last-success cache**: ~50 LOC for the wrapper; deferred because the in-memory dict has the same hit-rate semantics during the spike's single-process lifetime.
- **DuckDB for analytics**: explicitly deferred to #26. The analytical surface (#27, #34) requires this; the live arrivals board does not.
- **Redis for shared rate-limit state**: deferred because the spike runs a single Streamlit process. Multi-replica deployment crosses the threshold (post-demo).

## When to revisit

- The project ever runs more than one Streamlit replica → need shared rate-limit state.
- The recruiter (or anyone) asks for historical "what was the delay at 8 a.m. yesterday?" → need persistence.
- An audit-log requirement lands → need durable storage with retention semantics.

See [docs/UPGRADE-PATH.md](../UPGRADE-PATH.md) for the broader "what changes when this stops being a spike" discussion.
