# Recruiter-conversation notes

Concrete talking points mapped to where in the code each is demonstrable. Read alongside the [DEMO.md](../DEMO.md) screen-share runbook. The goal is to be specific: not "the parser handles realtime data" but "[gtfs_demo/parser/tripupdates.py](../gtfs_demo/parser/tripupdates.py) line 143 is where partial-update propagation lives."

## What I considered → chose → because

Three load-bearing decisions, each with a one-page ADR:

| Considered | Chose | Why | ADR |
|---|---|---|---|
| Flask / FastAPI / Streamlit | Streamlit | Zero scaffolding cost for auth + layout + autorefresh in a 4–6h budget; pure-Python testable underneath | [docs/adr/0001](adr/0001-streamlit-not-flask.md) |
| SQLite / DuckDB / no-DB | No database (in-memory only) | Forces every state container into one process; no migration churn during the spike; analytics deferred to post-demo #26 | [docs/adr/0002](adr/0002-no-database.md) |
| GTFS-RT (protobuf) / V3 REST (JSON) | Strict GTFS-RT | Direct relevance to the role; portable to other agencies; V3 staging plan documented for when this outgrows the spike | [docs/adr/0003](adr/0003-strict-gtfs-rt.md) |

The V3 upgrade story is in [docs/UPGRADE-PATH.md](UPGRADE-PATH.md) — additive staging across four stages, each replacing a specific surface without rewriting the parsers.

## The four code talking points

### 1. Partial StopTimeUpdate propagation (the GTFS-RT competence signal)

**Where**: [gtfs_demo/parser/tripupdates.py:140-175](../gtfs_demo/parser/tripupdates.py#L140-L175), function `_arrivals_for_scheduled_trip`.

The GTFS-RT spec says: a TripUpdate's `stop_time_update` list is sparse. When stop K has an explicit delay, every downstream stop on the same trip inherits that delay until the next explicit update appears. Naively iterating only over the explicit updates drops half the realtime signal.

The implementation walks the static `stop_times` in `stop_sequence` order and threads a `current_delay_seconds` accumulator. An explicit RT update for a stop sets the accumulator; stops without an explicit update inherit the most recent value. Stops upstream of the first explicit update get `delay_seconds=None` (no propagation backward — that would be making up data).

Tested at [tests/test_tripupdates_parser.py::test_partial_stop_time_update_propagates](../tests/test_tripupdates_parser.py).

### 2. Polite-consumer dual rate limiting

**Outbound** (us-as-consumer): [gtfs_demo/fetcher/rate_limit.py:19-67](../gtfs_demo/fetcher/rate_limit.py#L19-L67) — `OutboundRateLimiter`. Per-URL minimum-interval enforcement; ≤ 1 fetch / 10s per feed by default. Protects MBTA's CDN from us.

**Inbound** (us-as-server): [gtfs_demo/security/rate_limit.py:41-104](../gtfs_demo/security/rate_limit.py#L41-L104) — `SessionRateLimiter`. Sliding-window per Streamlit session; default 30 req / 60s. Protects us from a runaway authenticated session.

Two limiters because the directions of traffic protect against different threats. The directories reflect intent (`fetcher/` for outbound politeness, `security/` for inbound abuse protection) and the README's [Security section](../README.md#security) calls out the split explicitly.

### 3. Three-tier data path (graceful degradation)

**Where**: [gtfs_demo/fetcher/health.py:87-132](../gtfs_demo/fetcher/health.py#L87-L132), `HealthTrackedFetcher.fetch`.

Each tier kicks in when the one above fails:

1. **Live fetch** — happy path, fresh bytes from MBTA's CDN ([fetcher/realtime.py](../gtfs_demo/fetcher/realtime.py)).
2. **Soft cache** — `dict[str, FeedMessage]` of last-success messages, in memory. Survives transient network blips within a process.
3. **Hard snapshot** — committed `.pb` files under [examples/](../examples/), loaded by [fetcher/fallback.py](../gtfs_demo/fetcher/fallback.py). Stale by design but keeps the UI usable through a cold-start outage.

The `FeedHealth` model exposes two independent flags — `is_stale` (the **data** is old) and `is_degraded` (our **fetch** is failing). Together they cover the four combinations operators actually care about. The `is_snapshot` flag (new in [#13](https://github.com/dcltdw/gtfs-demo/issues/13)) surfaces the third tier so the UI labels honestly.

### 4. Auth surface that never logs passwords

**Where**: [gtfs_demo/auth.py:40-79](../gtfs_demo/auth.py#L40-L79) — `verify_credentials`. Bcrypt-checked; emits structured `auth.login.success` / `auth.login.failure` records with three distinct failure reasons (`unknown_user` / `wrong_password` / `invalid_hash`).

**The password is never written to any log record.** Two layers of defence:

1. `log_auth_event` raises `ValueError` if a caller passes `password=` as an extra. Explicit guard, fails loud.
2. `test_failure_log_does_not_contain_password` is a backstop: produces failed-login records, scans every captured log record's rendered form for the password substring. If the substring appears, the test fails.

The Streamlit-page wiring sits one layer up ([gtfs_demo/app.py](../gtfs_demo/app.py)), using `build_authenticator_config` to feed the bcrypt hash + cookie key into `streamlit-authenticator`. The cookie HMAC key is a **separate setting** from the password hash so "hash leaked" and "sessions forgeable" stay distinct threats.

Real auth (DB-backed users, OAuth, MFA, audit log) is enumerated as post-demo #35–#38. The current setup is honest about being "a single seeded credential rotated each demo cycle."

## Process discipline

I worked the project as 14 small PRs (one issue → one PR), each following the same body shape — Summary / Work breakdown / Files changed / Docs and tests / Operational impact. The conventions doc that codifies this is [docs/AI-COLLABORATION-CONVENTIONS.md](AI-COLLABORATION-CONVENTIONS.md): 9 numbered rules, each Rule / Why / How-to-apply. Ported from prior work; spike-inappropriate sections (long-running branches, midpoint audits, burst-mode multi-PR) explicitly dropped with a note about why.

Why mention this: the *what* of the project is GTFS-RT competence; the *how* is process. Both matter for a real team. The PR audit trail on the repo's [merged-PR list](https://github.com/dcltdw/gtfs-demo/pulls?q=is%3Apr+is%3Aclosed+is%3Amerged) is the artefact.

## Honest limitations

- **Single user, single replica.** Real auth, per-IP rate limiting, and Redis-backed shared state are all post-demo (#35, #40, ADR #41).
- **No historical data.** "What was the typical delay at 8 a.m. yesterday?" can't be answered — there's no DB. Post-demo #26 / #27 / #34 cover this.
- **In-process snapshot cache.** A process restart drops every session's rate-limit bucket and last-success message.
- **No HTTP 429.** Streamlit isn't a request/response server; the limiter returns a bool and the page renders a banner. A real API with proper 429 + `Retry-After` is post-demo.
- **MBTA-specific.** The parsers would run unchanged against any GTFS-RT publisher, but the corridor + scope decisions ([gtfs_demo/scope.py](../gtfs_demo/scope.py)) are MBTA-specific.

## Retrospective

See [RETROSPECTIVE.md](../RETROSPECTIVE.md) for "what I learned / what surprised me / what I'd do differently." Written at the end of the spike; honest, not curated.
