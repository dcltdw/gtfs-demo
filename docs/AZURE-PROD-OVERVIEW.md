# Azure-prod architecture: short overview

> **Audience.** A reader who knows AWS, wants a fast read of how this demo's spike-grade architecture would shift if it were rebuilt for production on Azure. Every Azure service named has its AWS equivalent in the same row or sentence.
>
> **Companion doc:** [AZURE-PROD-DETAILED](AZURE-PROD-DETAILED.md) covers the same comparison plus the [post-demo backlog](https://github.com/dcltdw/gtfs-demo/issues?q=is%3Aopen+label%3Apost-demo) (live vehicle map, real DB-backed users, OpenTelemetry, etc.) at ~6× the depth.
>
> **Production target.** Single transit agency at MBTA scale (~1M daily riders, ~50K peak concurrent), single Azure primary region with cross-region disaster recovery. Multi-region active-active and multi-tenant SaaS are explicit non-goals; see the closing section.

## What the demo runs today

A single Python process started with `streamlit run` on a developer laptop, polling MBTA's public GTFS-RT feeds every 10 s, parsing the protobufs against a vendored static GTFS bundle, and rendering an arrivals board / alerts panel / feed-health panel behind one bcrypt-hashed shared credential. State lives in `@st.cache_resource` (per-process) and `st.session_state` (per-tab). Logs go to stdout. Secrets live in `.env`. The data path is diagrammed in the [README](../README.md#architecture).

It works for a recruiter screen-share. It collapses the moment you add a second concurrent web instance.

## The big map

| Component | Demo today | Prod Azure (single region + DR) | AWS equivalent | Why upgrade |
|---|---|---|---|---|
| **Web hosting** | `streamlit run`, single process | **Azure Container Apps** (ACA) — autoscale on HTTP concurrency, zero-downtime revisions | **AWS App Runner** or **ECS Fargate** | Horizontal scale; survives instance death; reviewable rollouts |
| **Edge / TLS / WAF** | Streamlit's built-in HTTP server | **Azure Front Door** + WAF policy (rate limit, geo, DDoS L7) | **CloudFront** + **AWS WAF** | TLS termination at the edge; per-IP rate limit before compute spends cycles |
| **Auth** | `streamlit-authenticator` + bcrypt + env-file credential, single user | **Microsoft Entra ID** (formerly Azure AD) — OIDC, MFA, conditional access | **Cognito User Pools** + **IAM Identity Center** | Real identity, MFA, session revocation, per-user audit trail |
| **Session cookie signing** | PyJWT, HMAC key from `.env` | Same code; key in **Azure Key Vault** read via **Managed Identity** | Same; key in **AWS Secrets Manager** read via **IAM role** | Audited secret access; automatic rotation; no secret on disk |
| **Secrets / config** | `.env` file | **Azure App Configuration** + **Key Vault** | **AWS AppConfig** + **Secrets Manager** | Per-environment overrides; rotation policies; access audit |
| **Realtime feed fetcher** | in-process polling inside the web app | **Azure Function** (timer trigger, 10 s) → **Azure Service Bus** topic → web subscribes | **Lambda** (EventBridge schedule) → **SNS** / **Kinesis** → web subscribes | Decouples ingest from rendering; one fetch serves N web instances; respects MBTA's outbound budget globally |
| **Static GTFS bundle** | local 7-day disk cache | **Azure Blob Storage** (RA-GZRS for DR) fronted by **Azure CDN** | **S3 Cross-Region Replication** + **CloudFront** | Replicated, cheap, edge-cacheable, conditional-GET friendly |
| **Snapshot fallback** (`examples/*.pb`) | committed in git | Same Blob container, `versioning` on, retention policy | **S3 Versioning** + lifecycle | Versioned outside git; cheaper; rotatable |
| **Parsed-feed cache** | `@st.cache_resource` (per process) | **Azure Cache for Redis** (Premium with persistence) | **ElastiCache for Redis** | Shared across all web instances; no cold-start re-parse per pod |
| **Inbound rate limit** | in-process sliding window per Streamlit session | **Front Door** rate-limit rule (per-IP), backed by **Redis** counters for per-user budgets | **WAF** rate-based rules + **ElastiCache** counters | Enforced at the edge; survives a single web-pod restart; per-IP _and_ per-user budgets |
| **Outbound politeness** | `tenacity` retry + 10 s min interval, in-process | Lifted into the Function above; central token bucket in Redis if multi-Function | Same in Lambda; central limiter in **DynamoDB** or **ElastiCache** | One source of truth for "≤ 1 fetch / 10 s per feed" — survives Function scale-out |
| **Logging** | stdlib logger → stdout | **Log Analytics** workspace; structured logs forwarded automatically | **CloudWatch Logs** + **CloudWatch Logs Insights** (KQL ↔ Logs Insights query language) | Persistent, queryable, retained per compliance |
| **Tracing** | none | **Application Insights** with OpenTelemetry auto-instrumentation | **AWS X-Ray** | Distributed traces: user → web → Service Bus → Function → MBTA |
| **Metrics + alerts** | none | **Azure Monitor** metrics + alert rules → action group → PagerDuty | **CloudWatch Metrics** + **Alarms** → **SNS** → PagerDuty | Pageable SLOs (e.g. "Alerts feed stale > 10 min for 5 min") |
| **Static site (notebook + docs)** | GitHub Pages | **Azure Static Web Apps** | **S3 + CloudFront** or **Amplify Hosting** | Edge caching, custom-domain TLS, CI integration |
| **CI** | GitHub Actions on PRs | Same, _or_ **Azure DevOps Pipelines** | Same, _or_ **CodePipeline** + **CodeBuild** | No forced change; deploy targets shift, not the runner |
| **Deploy / IaC** | manual `git pull && just demo` | **Bicep** (or **Terraform**) → ACA revisions; blue-green via revision traffic split | **AWS CDK** / **Terraform** → ECS rolling, or **CodeDeploy** blue-green | Reviewable infra; reproducible envs; reversible rollouts |
| **DR** | none (single laptop) | Paired Azure region; Blob RA-GZRS; Key Vault soft-delete; **Front Door** priority-routed failover | **S3 CRR**; **Secrets Manager replicas**; **Route 53** health-check failover | Documented RPO/RTO; survives region outage |

## Four biggest deltas, in plain prose

**1. The fetcher moves out of the web tier.** Today every running Streamlit process polls MBTA's CDN itself. Two web instances = 2× the outbound traffic, and the in-process politeness limiter can't enforce the global "≤ 1 fetch / 10 s per feed" budget MBTA expects. The prod design lifts the fetcher into one timer-triggered Azure Function that publishes parsed payloads to a Service Bus topic; the web app subscribes and reads the latest snapshot from Redis. The AWS shape is identical: Lambda on an EventBridge schedule, fanning out via SNS or Kinesis. This single change unblocks horizontal scale of the web tier, makes the rate-limit promise globally enforceable, and survives web-pod restarts without losing the most recent fetch.

**2. Auth gets a real identity provider.** The demo's single hardcoded credential and bcrypt hash are enough to demonstrate "an auth gate exists." Production is OIDC against Entra ID (AWS: Cognito User Pools), with MFA, conditional access, session revocation, and per-user audit trails out-of-the-box. The session cookie is still HMAC-signed by the app — but the key now lives in Key Vault (AWS: Secrets Manager) and is fetched via Managed Identity (AWS: IAM role), with no secret on disk.

**3. State moves out of the process.** `@st.cache_resource` keeps parsed feeds in memory per process. That's fine for one instance and broken the moment you scale: each new pod warms its own cache, doubling MBTA load and producing inconsistent views across instances during the warm-up window. The prod design uses Azure Cache for Redis (AWS: ElastiCache) as the shared parsed-feed cache; the Function fetcher writes on each tick; the web app becomes effectively stateless. Same story for the inbound rate-limit buckets (today: per-process dict; prod: Redis sorted-set per user/IP, plus a Front Door / WAF rule for the L7 edge cap).

**4. Observability fills in.** Streamlit logs to stdout; in prod the same logger is wired through Application Insights (AWS: X-Ray + CloudWatch) with OpenTelemetry auto-instrumentation, so a single trace shows the path from a user request through the web app, Service Bus pull, Redis read, and back. Metric alerts on feed staleness, fetch failure rate, p95 latency, and 5xx ratio fire to PagerDuty via Azure Monitor action groups. The demo's `should_show_stale_banner` lives on; it just gets _augmented_ by an out-of-band alert that the on-call sees before any user does.

## Intentionally out of scope

| Non-goal | Why deferred |
|---|---|
| Multi-region active-active | Adds Front Door priority-set + active-active Cosmos + Service Bus geo-DR + tested traffic split. Justified by a regulatory / SLA driver, not by raw traffic at this scale. |
| Multi-tenant SaaS (multiple agencies) | Genericising for many agencies shifts the design toward per-tenant isolation, federated identity, and per-tenant config — a different doc. |
| Realtime push to clients (WebSocket) | A nice-to-have ([#29](https://github.com/dcltdw/gtfs-demo/issues/29)) that replaces 15 s polling with **Azure SignalR Service** (AWS: **API Gateway WebSockets** / **AppSync subscriptions**). Covered in [AZURE-PROD-DETAILED](AZURE-PROD-DETAILED.md). |
| Historical analytics | Demo discards each fetch; prod would land into **ADLS Gen2 + Delta Lake** (AWS: **S3 + Iceberg / Athena**) for delay-distribution charts and replay. Covered in the detailed doc. |

## Want more depth?

[AZURE-PROD-DETAILED](AZURE-PROD-DETAILED.md) — same comparison plus the post-demo backlog ([#15–#41](https://github.com/dcltdw/gtfs-demo/issues?q=is%3Aopen+label%3Apost-demo), [#49](https://github.com/dcltdw/gtfs-demo/issues/49), [#57](https://github.com/dcltdw/gtfs-demo/issues/57)), an architecture diagram, per-component subsections, cost order-of-magnitude bands, and SLO targets.
