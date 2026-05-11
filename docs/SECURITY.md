# Threat model and security notes

This document covers the security posture of the gtfs-dleung spike. It complements the project-root [SECURITY.md](../SECURITY.md), which is the public disclosure entry point.

## Scope

A single-user Streamlit application that:

- Fetches three public GTFS-RT feeds from the MBTA CDN.
- Filters them against a vendored static GTFS bundle.
- Renders an arrivals board, alerts panel, and feed-health panel.
- Authenticates a single demo user via `streamlit-authenticator` + bcrypt.

Out of scope: anything not exercised by the spike (real user accounts, multi-tenant authz, audit logging, MFA — all enumerated as post-demo issues).

## Assets

| Asset | Sensitivity | Notes |
|---|---|---|
| Demo credential | Low | Shared with recruiter for the live demo. Rotated each cycle. |
| Outbound traffic to MBTA CDN | Low | Public feed; politeness, not secrecy. |
| Code / config | Public | Repo is public. No secrets in tree. |

## Threats considered

- **Unauthenticated abuse of the live Streamlit app**: mitigated by `streamlit-authenticator` + a sliding-window inbound rate limit per session.
- **MBTA feed abuse via the app**: mitigated by an outbound rate limit (≤1 fetch / 10 s per feed) and an identifying `User-Agent`.
- **Credential exposure**: only the bcrypt hash lives on disk (`.env.example`, public); the plaintext lives in the maintainer's password manager and is rotated before each demo cycle.
- **Compromise of `gh` PATs / repo write access**: out of scope for the spike (single-maintainer repo).

## Rotation policy

- **Demo credential**: rotate before every demo cycle. Generate the new hash with:

  ```bash
  uv run python -c "import bcrypt, getpass; pw = getpass.getpass('new demo password: ').encode(); print(bcrypt.hashpw(pw, bcrypt.gensalt(rounds=12)).decode())"
  ```

  Update both `.env.example` (committed hash) and the deployed `.env` (real hash). The committed hash and the deployed hash are intentionally the same value during the spike; for any longer-lived deployment they should diverge.

- **MBTA feeds**: no rotation needed; the feeds are public and unauthenticated.

## Public-repo posture

This repository is public. Before opening every PR:

- Run `git diff main...HEAD` and skim for secrets, PII, internal references.
- Sensitive demo values (the live password, real personal data) never enter the diff.
- The bcrypt hash in `.env.example` is intentionally committed: it is one-way and the underlying plaintext is short-lived.

See [docs/AI-COLLABORATION-CONVENTIONS.md §6](AI-COLLABORATION-CONVENTIONS.md) for the full diff-scan checklist.
