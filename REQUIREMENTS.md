# Requirements

This is the narrative specification for the gtfs-dleung spike. Functional requirements (F-NNN) and non-functional requirements (NF-NNN) have structured counterparts under [docs/agent-spec/](docs/agent-spec/); the contract for those files is in [docs/agent-spec/schema.md](docs/agent-spec/schema.md).

## 1. Context

A 4–6 hour exploration spike built to demonstrate GTFS-RT competence to a transit-systems recruiter. Two deliverables:

1. A rendered notebook hosted via GitHub Pages — read-only walkthrough.
2. A live Streamlit application — screen-shared during the recruiter call.

The locked decisions in [project memory](https://github.com/dcltdw/gtfs-dleung/issues/1) capture the immovable choices. The summary below restates the contract the code must satisfy.

## 2. Scope

- **In scope (pre-demo, #1–#14):**
  - Red Line (Park St ↔ Davis Sq) and Green Line E branch (Park St ↔ Ball Sq) only.
  - Static GTFS bundle ingestion + scope filtering.
  - GTFS-RT TripUpdates, VehiclePositions, ServiceAlerts subscription + parsing.
  - Single-user demo authentication, sliding-window inbound rate limiter, polite outbound rate limiter.
  - Streamlit UI: login, arrivals board, alerts panel, feed-health panel.
  - DEMO.md runbook + RECRUITER-NOTES.md.
  - Architecture docs: ADRs, Mermaid diagram, UPGRADE-PATH, GLOSSARY.
- **Out of scope (post-demo, #15–#41):**
  - Buses, commuter rail, other Green Line branches.
  - Real (DB-backed) user accounts, OAuth/SSO, MFA, per-IP rate limiting.
  - Container packaging, K8s, observability backends.
  - Persistence, anomaly detection, schedule-vs-actual analytics.

## 3. Functional requirements

> Each F-NNN below has a structured counterpart in `docs/agent-spec/F-NNN-*.md`.

- **F-001 Static GTFS ingestion**: load the MBTA static feed, filter to Red Line + Green Line E branch. See [docs/agent-spec/F-001-load-static-feed.md](docs/agent-spec/F-001-load-static-feed.md).
- **F-002 GTFS-RT fetcher**: fetch + decode the three RT feeds with an identifying User-Agent, a per-URL outbound rate limit (≤ 1 fetch / 10 s), and exponential-backoff retry on transient failures. See [docs/agent-spec/F-002-gtfs-rt-fetcher.md](docs/agent-spec/F-002-gtfs-rt-fetcher.md). Feed URLs:
  - `TripUpdates`: `https://cdn.mbta.com/realtime/TripUpdates.pb`
  - `VehiclePositions`: `https://cdn.mbta.com/realtime/VehiclePositions.pb`
  - `Alerts`: `https://cdn.mbta.com/realtime/Alerts.pb`
- **F-003 TripUpdates → arrivals board**: surface predicted arrival times scoped to the demo stops, with `schedule_relationship` honoured. Handles partial StopTimeUpdate propagation and ADDED trips. See [docs/agent-spec/F-003-tripupdates-arrivals.md](docs/agent-spec/F-003-tripupdates-arrivals.md).
- **F-004 VehiclePositions**: parse current vehicle positions, scope-filter to Red Line + Green-E, surface a typed `VehiclePosition` model. See [docs/agent-spec/F-004-vehiclepositions.md](docs/agent-spec/F-004-vehiclepositions.md). Map rendering is post-demo (#15).
- **F-005 ServiceAlerts**: surface active alerts that touch the demo scope.
- **F-006 Feed staleness detection**: detect stale feeds and degrade gracefully.
- **F-007 Authentication**: single demo user, bcrypt-hashed password from env.
- **F-008 Inbound rate limiting**: sliding window per Streamlit session.
- **F-009 Streamlit UI**: login → arrivals + alerts + feed-health panels.

## 4. Non-functional requirements

> Each NF-NNN below has a structured counterpart in `docs/agent-spec/NF-NNN-*.md`.

- **NF-001 Reproducibility**: `uv sync` on a clean checkout reproduces a working environment.
- **NF-002 Type safety**: `mypy --strict` passes.
- **NF-003 Lint cleanliness**: ruff passes with the configured rule set.
- **NF-004 Test cadence**: every issue PR ships its own tests; smoke test is the floor.
- **NF-005 Public-repo posture**: no secrets, PII, or internal references in the tree or in diffs.
- **NF-006 Rate limiting**: outbound ≤ 1 fetch / 10 s per feed; inbound configurable.
- **NF-012 CI pipeline**: parallel `lint` / `typecheck` / `test` jobs run on every PR + push to `main`; pre-commit hooks reproduce the lint + typecheck + secrets-scan locally. See [docs/agent-spec/NF-012-ci-pipeline.md](docs/agent-spec/NF-012-ci-pipeline.md).

## 5. Routes (Streamlit pages)

> Detailed in the F-009 spec. Summary:
>
> - `/` — login screen.
> - `/board` — arrivals board for the demo stops.
> - `/alerts` — active service alerts in scope.
> - `/health` — feed-health panel (last-fetched timestamps, staleness, fetch success rates).

## 6. Acceptance for the spike as a whole

- Recruiter call can be conducted by sharing the live Streamlit app and the rendered notebook URL.
- Every pre-demo issue is closed via a merged PR.
- `docs/AI-COLLABORATION-CONVENTIONS.md` has not been violated; the audit trail in PR bodies makes that claim verifiable.
- RETROSPECTIVE.md is filed after the call.
