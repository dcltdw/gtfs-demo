# Threat model and security notes

This document covers the security posture of the gtfs-demo spike. It complements the project-root [SECURITY.md](../SECURITY.md), which is the public disclosure entry point.

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

  **Rotation checklist** (per cycle):

  1. Generate a fresh password manually (password manager, ≥16 chars).
  2. Compute the bcrypt hash with the command above.
  3. Update `GTFS_DEMO_PASSWORD_BCRYPT` in the deployed `.env`.
  4. **Rotate `GTFS_COOKIE_KEY` at the same time** and update the deployed `.env`. Old cookies become invalid; users sign in again. This is intentional — coupling the rotations makes a single audit point for "everything tied to this cycle's credential is dead." The key must be **at least 32 bytes** so PyJWT doesn't emit `InsecureKeyLengthWarning` (RFC 7518 §3.2 — HMAC-SHA256 minimum). Generate with either:

     ```bash
     openssl rand -hex 32                                      # 64-char hex (32 bytes raw → 64-byte string)
     python -c "import secrets; print(secrets.token_urlsafe(32))"   # 43-char URL-safe base64
     ```
  5. Restart the Streamlit app so the new env values are picked up.
  6. Update `.env.example` with the new bcrypt hash (the committed placeholder mirrors the deployed hash during the spike, so the public placeholder always points at the current cycle).
  7. Confirm the prior cycle's password no longer authenticates.

- **MBTA feeds**: no rotation needed; the feeds are public and unauthenticated.

## Auth event logging

The `gtfs_demo.auth` module emits structured records via the stdlib logger named `gtfs_demo.auth`. Three events at INFO:

- `auth.login.success` — `username`, plus stdlib's auto-attached timestamp.
- `auth.login.failure` — `username`, `reason` (one of `unknown_user`, `wrong_password`, `invalid_hash`).
- `auth.logout` — emitted by the Streamlit page (#11) on the logout button.

**The password is never written to any log record.** :func:`gtfs_demo.auth.log_auth_event` raises `ValueError` if a caller passes `password=` as an extra; the test `test_failure_log_does_not_contain_password` is a backstop that scans every produced record for the password substring. A durable audit log (post-demo #38) replaces the stdout sink with a database table.

## Public-repo posture

This repository is public. Before opening every PR:

- Run `git diff main...HEAD` and skim for secrets, PII, internal references.
- Sensitive demo values (the live password, real personal data) never enter the diff.
- The bcrypt hash in `.env.example` is intentionally committed: it is one-way and the underlying plaintext is short-lived.

See [docs/AI-COLLABORATION-CONVENTIONS.md §6](AI-COLLABORATION-CONVENTIONS.md) for the full diff-scan checklist.
