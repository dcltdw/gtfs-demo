# gtfs-demo — curated docs index

> The site landing page is the rendered [README](../README.md) — start there for the full overview, architecture diagram, and quickstart. This page is the curated link list across every doc in the repo.

**Source repo**: <https://github.com/dcltdw/gtfs-demo>
**Live app**: run `just demo` after `just install` — opens at `http://localhost:8501`.

## Start here

- [README](../README.md) — what / why / quickstart / architecture (with a Mermaid diagram of the data path)
- [REQUIREMENTS](../REQUIREMENTS.md) — narrative spec; functional + non-functional requirements
- [RECRUITER-NOTES](RECRUITER-NOTES.md) — talking points with file:line and ADR links

## Decisions (ADRs)

Three short MADR-lite records:

- [0001 — Streamlit, not Flask](adr/0001-streamlit-not-flask.md)
- [0002 — No database; in-memory state only](adr/0002-no-database.md)
- [0003 — Strict GTFS-RT, not MBTA's V3 REST API](adr/0003-strict-gtfs-rt.md)

The V3 staging plan is in [UPGRADE-PATH](UPGRADE-PATH.md) — additive across four stages, each replacing one surface without rewriting the parsers.

## Architecture: spike-now vs. prod-Azure

How this demo's spike-grade architecture would shift if rebuilt for production at MBTA scale on Azure, with AWS service equivalents annotated:

- [AZURE-PROD-OVERVIEW](AZURE-PROD-OVERVIEW.md) — short (2–3 pages); demo scope only; one comparison table + four big-delta callouts.
- [AZURE-PROD-DETAILED](AZURE-PROD-DETAILED.md) — medium (~6–10 pages); demo + post-demo backlog; mermaid architecture diagram; per-component deep-dives; cost order-of-magnitude bands; explicit non-goals.

## Functional + non-functional specs

Each functional requirement has a one-page spec under [agent-spec/](agent-spec/):

- [F-001 — Static GTFS loader + scope filter](agent-spec/F-001-load-static-feed.md)
- [F-002 — GTFS-RT HTTP fetcher (user-agent, rate-limit, retry)](agent-spec/F-002-gtfs-rt-fetcher.md)
- [F-003 — TripUpdates → arrivals board (partial-update propagation, ADDED trips)](agent-spec/F-003-tripupdates-arrivals.md)
- [F-004 — VehiclePositions parser](agent-spec/F-004-vehiclepositions.md)
- [F-005 — ServiceAlerts parser (scope + active-period filters)](agent-spec/F-005-servicealerts.md)
- [F-006 — Feed staleness + graceful degradation + metrics](agent-spec/F-006-feed-staleness.md)
- [F-007 — Auth + input validation + structured logging](agent-spec/F-007-auth-validation.md)
- [F-008 — Inbound rate limiter (sliding-window per session)](agent-spec/F-008-inbound-rate-limit.md)
- [F-009 — Streamlit UI](agent-spec/F-009-streamlit-ui.md)
- [NF-012 — CI pipeline](agent-spec/NF-012-ci-pipeline.md)

The spec contract is in [agent-spec/schema.md](agent-spec/schema.md).

## Operations + security

- [SECURITY](SECURITY.md) — threat model, rotation policy, auth event logging
- [DEMO](../DEMO.md) — the recruiter screen-share runbook (root of the repo)
- [RETROSPECTIVE](../RETROSPECTIVE.md) — what I learned / what surprised me / what I'd do differently
- [GLOSSARY](GLOSSARY.md) — GTFS terms, MBTA terms, project conventions

## Process

- [AI-COLLABORATION-CONVENTIONS](AI-COLLABORATION-CONVENTIONS.md) — the 9 rules every PR followed. Ported from a prior project; spike-inappropriate rules explicitly dropped.

## Aspirational backlog (not actively scheduled)

> **Project paused 2026-05-13** ([#87](https://github.com/dcltdw/gtfs-demo/issues/87)). The open issues below remain as documentation of the natural next steps, not as in-flight work. The [AZURE-PROD-DETAILED](AZURE-PROD-DETAILED.md) doc references each in the relevant production-design context.

- [Post-demo backlog](https://github.com/dcltdw/gtfs-demo/issues?q=is%3Aopen+label%3Apost-demo) — the 28 open follow-on tickets (#15–#41, plus #49 nightly live-feed CI and #57 credential-rotation script). Not scheduled.
