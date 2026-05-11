# ADR 0003 — Strict GTFS-RT, not the MBTA V3 REST API

- **Status**: Accepted
- **Date**: 2026-05-11
- **Author**: dcltdw

## Context

The MBTA exposes realtime data through two mechanisms:

1. **GTFS-RT** — three Protocol-Buffer feeds (`TripUpdates.pb`, `VehiclePositions.pb`, `Alerts.pb`) at `https://cdn.mbta.com/realtime/`. No API key, no auth, no rate limit beyond polite-consumer norms. Industry-standard format defined by [gtfs.org](https://gtfs.org/realtime/reference/); the same wire format that BART, TfL, MTA, and a hundred other transit agencies publish.
2. **V3 REST API** at `https://api-v3.mbta.com/` — a JSON:API-shaped layer that wraps GTFS-RT plus some derived fields (predicted arrival in seconds, severity rollups, includes/relations). Requires a key for any meaningful rate.

The recruiter audience is hiring for a role that involves working with GTFS-RT directly. The spike is a competence demonstration first, a working app second.

## Decision

Use GTFS-RT directly via `gtfs-realtime-bindings` (the official protobuf bindings) + `requests`. **Do not** use the V3 REST API anywhere in the codebase.

## Consequences

**Gained:**

- **Direct relevance to the role.** The conversation the recruiter wants to have is about GTFS-RT semantics — `schedule_relationship`, partial `StopTimeUpdate` propagation, `ADDED` trips, `informed_entity` selectors. All of these are *consumed* by V3 internally but *abstracted away* at its surface. The spike's parser code (F-003, F-004, F-005) is the artefact a transit-systems team would actually look at.
- **Portability.** The same parser package would run unchanged against any GTFS-RT publisher — a future job at a different agency wouldn't require relearning a different REST shape.
- **No key management.** The CDN feeds are public; nothing in the repo holds an MBTA-issued credential. Simpler ops, simpler `.env`, simpler diff-scan for secrets per §6 of the conventions doc.
- **Lower latency.** Direct CDN fetch is one hop; V3 adds a routing layer (and is rate-limited per key).

**Lost:**

- **Higher implementation cost.** Pre-computed fields (`predicted_arrival_seconds_from_now`, `severity`) we have to derive ourselves. Partial-update propagation (F-003) is ~80 LOC of careful traversal that V3 would do server-side.
- **No client-side filtering.** V3 supports `filter[stop]=place-davis`; GTFS-RT delivers the whole feed every fetch, and we filter in-process via `filter_to_scope`. At the spike's scale this is unmeasurably cheap, but at higher volume V3's server-side filter is meaningful.
- **No relations.** V3's `?include=trip,route,stop` returns the related entities in one round-trip; with GTFS-RT we join in-process against the parsed static bundle. Acceptable for the spike (static fits in memory); a different shape for analytical workloads.
- **No webhooks / subscriptions.** V3 supports server-sent events (`/predictions/stream`); GTFS-RT is poll-only. We poll every 10 s per feed (rate-limited per F-002).

## Alternatives considered

- **V3 REST only**: rejected — the conversation we want to have is about GTFS-RT mechanics, not JSON:API.
- **Both GTFS-RT + V3** (dual sources): rejected as scope creep for a 4–6h spike. Useful for a real production system that wants V3's webhooks + GTFS-RT's portability; a spike doesn't need both.
- **MBTA Performance API**: rejected as out of scope. Historical-only; not what an arrivals board needs.

## When to revisit

If the project grows into a production app with > ~10 concurrent users, V3's server-side filtering + webhooks become worth the dependency. The upgrade path is additive — V3 calls can replace specific surfaces (e.g. predictions) without rewriting the parsers. See [docs/UPGRADE-PATH.md](../UPGRADE-PATH.md) for the staging plan.

## Related

- F-002 (the realtime fetcher itself): [F-002-gtfs-rt-fetcher.md](../agent-spec/F-002-gtfs-rt-fetcher.md)
- F-003 (TripUpdates parser, where the cost of "direct GTFS-RT" is mostly paid): [F-003-tripupdates-arrivals.md](../agent-spec/F-003-tripupdates-arrivals.md)
