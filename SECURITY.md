# Security policy

## Supported versions

This is a time-boxed exploration project. No version of the software is supported in production. Use at your own risk.

## Reporting a vulnerability

If you find a security issue, please email **claude.unraveled663@simplelogin.com** with the subject `[gtfs-demo security]`. Please do not open a public issue for unresolved security defects.

Expect an acknowledgement within one business week. There is no formal SLA — this is a personal project.

## Threat model (summary)

The full threat model lives in [docs/SECURITY.md](docs/SECURITY.md). Highlights:

- The app is intended to be hosted publicly for a recruiter demo. The single seeded credential is treated as low-value but is rotated before each demo cycle.
- Outbound traffic is rate-limited and identified by a project `User-Agent`; inbound traffic is rate-limited by a sliding window per Streamlit session.
- No PII is ingested. No tracking, no analytics.
