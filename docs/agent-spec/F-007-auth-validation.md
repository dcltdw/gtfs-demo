---
id: F-007
title: Authentication + input validation + structured auth logging
type: functional
status: in-progress
issue: 9
pr: null
depends_on: []
owner: dcltdw
last_updated: 2026-05-11
---

## Summary

Ship the **testable surface** for the Streamlit app's login gate, scope-aware input validation, and structured auth-event logging. The Streamlit page (#11) wires `streamlit-authenticator` into the actual login widget using the config produced by :func:`build_authenticator_config`; nothing in F-007 imports Streamlit, so every assertion here is reachable without spinning up a real session.

This spec absorbs what the originating issue (#9) called `NF-003-auth`, `NF-004-input-validation`, and `NF-005-structured-auth-logging`. Those numbers were already taken in `REQUIREMENTS.md` (`Lint cleanliness`, `Test cadence`, `Public-repo posture`). The three concerns are folded into F-007 as Properties — same pattern used for F-002 / F-003 / F-005 / F-006.

## Inputs

- `Settings.gtfs_demo_username` (env: `GTFS_DEMO_USERNAME`; default `demo`).
- `Settings.gtfs_demo_password_bcrypt` (env: `GTFS_DEMO_PASSWORD_BCRYPT`; bcrypt hash, cost 12 in production).
- `Settings.gtfs_cookie_key` (env: `GTFS_COOKIE_KEY`; HMAC key for the session cookie — **rotate alongside the password**).
- `Settings.gtfs_cookie_expiry_days` (env: `GTFS_COOKIE_EXPIRY_DAYS`; default 1).

## Properties

1. **Single seeded user, bcrypt-checked.** `verify_credentials(username, password, *, settings)` returns `True` iff the username matches the configured demo username **and** `bcrypt.checkpw(password, settings.gtfs_demo_password_bcrypt)` succeeds. A malformed hash (operator-error `.env`) is caught and reported as a failure rather than crashing.
2. **Three distinct failure reasons, all logged.** Unknown user, wrong password, and malformed hash each emit a structured `auth.login.failure` record with a different `reason=`. A successful login emits `auth.login.success`. The `auth.logout` event is reserved for the Streamlit page (#11).
3. **Password never leaves the call site.** :func:`log_auth_event` raises immediately if a caller passes `password=` in `**extras` — defensive, asymmetric: easy to add a `password=` kwarg accidentally, hard to leak one through this surface once the guard is in place. The companion test `test_failure_log_does_not_contain_password` is a backstop that scans every record produced during a sample of verify calls for the password substring.
4. **Streamlit-authenticator config shape.** :func:`build_authenticator_config` returns the credentials/cookie dict the library expects. The cookie key is a **separate setting** from the password hash — keeps "someone read the hash file" and "someone can forge sessions" as different threats. Test asserts this separation.
5. **Defence-in-depth stop-id validation.** :func:`validate_stop_id` accepts only the 16 parent-station IDs in `ALL_CORRIDOR_PARENT_STATIONS`. Platform-level IDs (e.g. `70075`) are intentionally rejected — callers resolve to the parent first. The error message does **not** enumerate valid IDs (enumeration belongs in docs, not error responses).
6. **Pure functions, no Streamlit import.** `gtfs_dleung.auth` and `gtfs_dleung.validation` are importable in test contexts without `streamlit` even being installed; the Streamlit page in #11 is responsible for the widget glue.

## Outputs

- `verify_credentials(username, password, *, settings=None) -> bool`
- `build_authenticator_config(settings=None) -> dict[str, Any]`
- `log_auth_event(event, *, username, **extras) -> None` — emits via `logging.getLogger("gtfs_dleung.auth")`
- `validate_stop_id(stop_id) -> str` — returns unchanged or raises `ValueError`

## Edge cases

- **Username matches but password doesn't**: returns `False` with `reason=wrong_password`.
- **Username doesn't match**: returns `False` with `reason=unknown_user`. The timing leak (we don't bcrypt against a dummy hash) is acceptable for the spike's single-user setup — production would compare against a real-or-dummy hash regardless of username match.
- **Bcrypt hash in settings is malformed**: returns `False` with `reason=invalid_hash` — protects against operator error.
- **Logger called with `password=` extra**: `ValueError` is raised immediately; no record is emitted.
- **Empty / whitespace-only `stop_id`**: rejected (not in the allow-list).
- **`stop_id` of `'; DROP TABLE stops;--`**: rejected. We aren't using SQL here, but defence-in-depth means rejecting anything outside the allow-list regardless of *why* it might be dangerous.

## Out of scope (post-demo follow-ons)

- **Real user DB** (post-demo #35) — the spike has one seeded credential.
- **OAuth / SSO** (post-demo #36) — no third-party identity provider.
- **MFA + account lockout** (post-demo #37) — no second factor; no per-username rate limiting on failed attempts beyond the per-session inbound limiter that lands in #10.
- **Audit log table** (post-demo #38) — structured logs go to stdout/stderr; no durable storage.
- **Per-IP rate limiting** (post-demo #40) — only per-Streamlit-session, landing in #10.
- **Password rotation automation** — operator-driven, documented in `docs/SECURITY.md`.

## Verification

- `tests/test_auth.py::test_correct_password_authenticates` — happy path.
- `tests/test_auth.py::test_wrong_password_rejects` — wrong password → False.
- `tests/test_auth.py::test_unknown_username_rejects` — unknown username → False, even with correct password.
- `tests/test_auth.py::test_malformed_hash_rejects_safely` — invalid hash doesn't crash.
- `tests/test_auth.py::test_validate_stop_id_accepts_scope_stops` — every parent station in the corridor is accepted.
- `tests/test_auth.py::test_validate_stop_id_rejects_unknown_stop` — Blue Line stop, platform-level ID, and injection-style nonsense all rejected.
- `tests/test_auth.py::test_failure_log_does_not_contain_password` — the backstop scan: produce records via failed verify, assert sentinel password absent from every rendered record.
- `tests/test_auth.py::test_success_log_records_event` — `auth.login.success` emitted with username, no password.
- `tests/test_auth.py::test_log_auth_event_refuses_password_extra` — explicit guard raises.
- `tests/test_auth.py::test_build_authenticator_config_shape` — top-level keys + credential nesting + cookie-key separation from password hash.

Manual (in #11's Streamlit page, once wired):

```python
import streamlit_authenticator as stauth
from gtfs_dleung.auth import build_authenticator_config
authenticator = stauth.Authenticate(**build_authenticator_config())
name, status, username = authenticator.login("Login", "main")
```

## Open questions

_None._
