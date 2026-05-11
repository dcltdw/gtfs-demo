# Upgrade path: what changes when this stops being a spike

This doc is the corollary to [ADR 0003](adr/0003-strict-gtfs-rt.md) (and to a lesser extent [ADR 0001](adr/0001-streamlit-not-flask.md) and [ADR 0002](adr/0002-no-database.md)). It captures the GTFS-RT → MBTA V3 REST API tradeoff in enough detail that a future maintainer (or successor team) can stage the upgrade without re-deriving the rationale.

## Where we are today

- **Realtime ingestion**: poll three Protocol-Buffer feeds at `cdn.mbta.com/realtime/` every 10 s per feed (rate-limited in F-002).
- **Parsing**: in-process protobuf decode + custom GTFS-RT semantics (partial-update propagation, `ADDED` trips, two-axis health flags).
- **Persistence**: none — last-good cache lives in `HealthTrackedFetcher`, rate-limit state lives in `SessionRateLimiter`.
- **UI**: single-process Streamlit; no API surface; no webhooks.

This is the right shape for a 4–6h competence-demonstration spike. It is **not** the right shape for a production deployment.

## V3 REST — what it is

[`https://api-v3.mbta.com/`](https://api-v3.mbta.com/) is a JSON:API-shaped layer over the same data. Key endpoints used by an arrivals app:

| GTFS-RT (what we use) | V3 REST equivalent | Notes |
|---|---|---|
| `TripUpdates.pb` | `GET /predictions?filter[stop]=...` | V3 returns pre-computed countdowns + JSON:API relations. Server-side filtering by stop, route, direction, trip. |
| `VehiclePositions.pb` | `GET /vehicles?filter[route]=Red` | Same data, JSON-shaped. |
| `Alerts.pb` | `GET /alerts?filter[route]=Red,Green-E` | Same data, server-side filter by informed_entity. |
| (poll-based) | `GET /predictions/stream?...` (Server-Sent Events) | Push instead of poll; lower latency, no polite-interval logic needed. |
| Static GTFS zip | `GET /routes`, `/stops`, `/trips` | Per-entity REST; convenient for one-off lookups; not a substitute for the full bundle download. |

V3 requires an API key for any meaningful rate (the no-key tier is ~20 req/min). The MBTA portal issues keys; the project would need to manage one.

## What's gained by adopting V3

- **Server-side filtering** — `?filter[stop]=place-davis` returns only the rows we want; no in-process scope filter needed. Reduces wire bytes and parsing time at scale.
- **Pre-computed countdowns** — V3's `arrival_time` and `departure_time` are already "seconds from now" oriented; the spike's `_static_time_to_datetime` + delay propagation logic isn't needed for display.
- **Relations via `?include=`** — `?include=trip,route,stop` returns everything in one request; we don't have to join with the static feed in-process.
- **Webhooks (SSE)** — `/predictions/stream` replaces 10-second polling with push semantics. Lower latency, lower outbound traffic.
- **Simpler error shape** — V3 returns JSON:API errors with HTTP semantics; the GTFS-RT path catches `requests.Timeout`, malformed protobuf, etc., and translates them to typed exceptions ourselves (F-002).

## What's lost by adopting V3

- **Direct GTFS-RT experience** — for a job that values this specifically, every line of code that wraps V3 is a line not demonstrating familiarity with the lower-level spec.
- **Portability** — the same parsers in this repo will run against BART, TfL, MTA, or any GTFS-RT publisher. V3 is MBTA-specific.
- **Dependency on MBTA's abstractions** — V3's view of "what's an active alert" might not match what we want; the GTFS-RT path lets us decide our own filter semantics (active_period overlap, scope match — see F-005).
- **Key management** — `.env` gains an `MBTA_API_KEY` secret; the diff-scan rule (§6) gets one more pattern to watch for; the rotation policy gains a step.
- **Rate-limit visibility** — GTFS-RT is just a CDN; we polite-fetch via our own outbound RL. V3 enforces per-key limits; an exceeded budget is a per-app failure rather than a per-feed one.
- **Less defensive code is needed** — and that's both a feature and a loss. The spike's parser handles weird shapes (missing `header.timestamp`, ADDED trips, partial updates) explicitly; V3 hides these. If something goes wrong upstream, V3's abstraction can become opaque.

## When to switch

A non-exhaustive checklist of "you've outgrown the spike":

1. **More than one Streamlit replica.** Per-IP rate limiting + shared session state cross the GTFS-RT-via-cdn → V3-via-key threshold cleanly. Driven by post-demo #40.
2. **Webhook consumers want push.** GTFS-RT is poll-only; V3 supports SSE. If a downstream system wants events, switch.
3. **Server-side filtering becomes a real cost lever.** At ~20 vehicles in scope, full-feed parse is microseconds. At ~5000 vehicles, it isn't. (Not a real concern for the Red Line + Green-E corridor; would matter for a system-wide app.)
4. **The MBTA team you work with publishes a stable derived field you'd otherwise re-derive.** E.g., V3's `predicted_arrival_seconds_from_now` is exactly the field a board displays; computing it from scratch is academic exercise once the *job* is to ship arrivals.

## Staging plan (if/when)

This is additive — V3 can replace specific surfaces without rewriting the parsers:

1. **Stage 1**: Add a `gtfs_dleung.fetcher.v3` module that wraps V3's `/predictions` endpoint. Keep the GTFS-RT path active in parallel. Compare the two during a soak test; reconcile any discrepancies.
2. **Stage 2**: Switch the Streamlit arrivals board's data source to V3 predictions (lower latency for users). Keep VehiclePositions + Alerts on GTFS-RT for now (they're cheaper through the existing parsers).
3. **Stage 3**: Switch Alerts to V3 (server-side filter is meaningful for alerts at scale).
4. **Stage 4**: Add V3's `/predictions/stream` SSE consumer; deprecate the 10-second poll path. At this point GTFS-RT becomes the static-feed loader only.

Each stage can ship as its own PR with the corresponding ADR.

## Related

- [ADR 0001 — Streamlit, not Flask](adr/0001-streamlit-not-flask.md): a similar "right tool for the spike, not for production" decision.
- [ADR 0002 — No database](adr/0002-no-database.md): persistence is the other axis where this project will outgrow itself.
- [ADR 0003 — Strict GTFS-RT, not V3 REST](adr/0003-strict-gtfs-rt.md): the decision this doc elaborates on.
- [F-002 — GTFS-RT fetcher](agent-spec/F-002-gtfs-rt-fetcher.md): the surface that V3 would replace.
- [REQUIREMENTS.md §1](../REQUIREMENTS.md): the spike's locked decisions.
