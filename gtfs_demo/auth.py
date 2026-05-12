"""Authentication primitives for the Streamlit demo app.

This module is the **testable surface** for the auth path:

- :func:`verify_credentials` — pure function, accepts ``username`` + ``password``
  and the project's ``Settings``, returns ``True`` on a bcrypt match. Used by
  unit tests and by the Streamlit page's login handler.
- :func:`build_authenticator_config` — produces the credentials/cookie config
  dict that ``streamlit-authenticator`` wants. The Streamlit page (#11) wires
  this into the actual login widget; nothing in this module imports Streamlit.
- :func:`log_auth_event` — emits structured records via the stdlib logger.
  **Never logs passwords.** The companion test
  ``test_failure_log_does_not_contain_password`` scans every produced record
  for the password substring as a backstop.

Out-of-scope today (deferred to the post-demo issues called out below) and
documented inline so the demo's threat model is honest about what it's NOT
doing:

- Real user DB (post-demo #35): every demo cycle ships with one seeded user.
- OAuth / SSO (#36): assumed cycle-attached, not productionised.
- MFA + account lockout (#37): no second factor, no rate-limiting on failed
  attempts beyond the per-session inbound limiter (#10).
- Audit log table (#38): structured logs here, but no durable audit trail.
- Password rotation procedure: documented in ``docs/SECURITY.md``.
"""

from __future__ import annotations

import logging
from typing import Any

import bcrypt

from gtfs_demo.config import Settings, get_settings

logger = logging.getLogger("gtfs_demo.auth")


def verify_credentials(
    username: str,
    password: str,
    *,
    settings: Settings | None = None,
) -> bool:
    """Return ``True`` iff ``(username, password)`` matches the configured demo credential.

    Emits one of three structured log events:

    - ``auth.login.success`` when the username + password match.
    - ``auth.login.failure`` with ``reason="unknown_user"`` when the username
      doesn't match (timing leak is acceptable for the spike's single-user setup).
    - ``auth.login.failure`` with ``reason="wrong_password"`` when bcrypt rejects.

    **The password is never written to any log record** — verified by
    :func:`tests.test_auth.test_failure_log_does_not_contain_password`.
    """
    settings = settings or get_settings()

    if username != settings.gtfs_demo_username:
        log_auth_event("auth.login.failure", username=username, reason="unknown_user")
        return False

    try:
        ok = bcrypt.checkpw(password.encode("utf-8"), settings.gtfs_demo_password_bcrypt.encode())
    except ValueError:
        # Malformed hash — should never happen in production but defends against
        # an operator-error .env file.
        log_auth_event("auth.login.failure", username=username, reason="invalid_hash")
        return False

    if not ok:
        log_auth_event("auth.login.failure", username=username, reason="wrong_password")
        return False

    log_auth_event("auth.login.success", username=username)
    return True


def build_authenticator_config(settings: Settings | None = None) -> dict[str, Any]:
    """Build the credentials/cookie config dict that ``streamlit-authenticator`` consumes.

    Returns the structure documented at
    https://github.com/mkhorasani/Streamlit-Authenticator#configuration. The
    Streamlit page (#11) imports streamlit_authenticator and constructs the
    widget; nothing in this module imports Streamlit.

    Why pull this out: tests can assert the shape without spinning up Streamlit;
    keeps the auth surface unit-testable.
    """
    settings = settings or get_settings()
    return {
        "credentials": {
            "usernames": {
                settings.gtfs_demo_username: {
                    "name": "Demo User",
                    "password": settings.gtfs_demo_password_bcrypt,
                }
            }
        },
        "cookie": {
            "name": "gtfs_demo_auth",
            "key": settings.gtfs_cookie_key,
            "expiry_days": settings.gtfs_cookie_expiry_days,
        },
    }


def log_auth_event(event: str, *, username: str, **extras: object) -> None:
    """Emit a structured auth log record.

    ``event`` is one of:
    ``auth.login.success``, ``auth.login.failure``, ``auth.logout``.

    Records carry ``event`` + ``username`` + any ``extras``; the stdlib logging
    module attaches ``timestamp`` and other metadata automatically. **Never log
    the password.** Callers must not pass a ``password=...`` extra.
    """
    if "password" in extras:
        # Defensive: refuse to log a record that names a password field.
        raise ValueError("log_auth_event: callers must not pass 'password' as an extra")
    logger.info(
        "%s username=%s %s",
        event,
        username,
        " ".join(f"{k}={v}" for k, v in extras.items()),
        extra={"event": event, "username": username, **extras},
    )


__all__ = (
    "build_authenticator_config",
    "log_auth_event",
    "verify_credentials",
)
