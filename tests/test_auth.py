"""Tests for ``gtfs_dleung.auth`` and ``gtfs_dleung.validation``."""

from __future__ import annotations

import bcrypt
import pytest

from gtfs_dleung.auth import (
    build_authenticator_config,
    log_auth_event,
    verify_credentials,
)
from gtfs_dleung.config import Settings
from gtfs_dleung.validation import validate_stop_id

# Use cheap bcrypt rounds for test setup (~10ms vs ~250ms at rounds=12).
_TEST_ROUNDS = 4
_TEST_USERNAME = "test-user"
_TEST_PASSWORD = "test-pass-correct-horse-battery-staple"  # pragma: allowlist secret
_WRONG_PASSWORD = "wrong-password-xyzzy"  # pragma: allowlist secret


def _settings_with_password(password: str) -> Settings:
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=_TEST_ROUNDS)).decode()
    return Settings(gtfs_demo_username=_TEST_USERNAME, gtfs_demo_password_bcrypt=hashed)


def test_correct_password_authenticates() -> None:
    """A username + password that bcrypt-matches returns ``True``."""
    settings = _settings_with_password(_TEST_PASSWORD)
    assert verify_credentials(_TEST_USERNAME, _TEST_PASSWORD, settings=settings) is True


def test_wrong_password_rejects() -> None:
    """A wrong password returns ``False``."""
    settings = _settings_with_password(_TEST_PASSWORD)
    assert verify_credentials(_TEST_USERNAME, _WRONG_PASSWORD, settings=settings) is False


def test_unknown_username_rejects() -> None:
    """A username that doesn't match returns ``False``, even with the correct password."""
    settings = _settings_with_password(_TEST_PASSWORD)
    assert verify_credentials("ghost", _TEST_PASSWORD, settings=settings) is False


def test_malformed_hash_rejects_safely() -> None:
    """An invalid bcrypt hash in settings doesn't crash; verify just returns ``False``."""
    settings = Settings(gtfs_demo_username=_TEST_USERNAME, gtfs_demo_password_bcrypt="not-a-hash")
    assert verify_credentials(_TEST_USERNAME, _TEST_PASSWORD, settings=settings) is False


def test_validate_stop_id_accepts_scope_stops() -> None:
    """Every parent-station ID in the corridor is accepted."""
    for stop_id in (
        "place-pktrm",  # Park Street
        "place-davis",  # Davis
        "place-balsq",  # Ball Square
        "place-knncl",  # Kendall/MIT
        "place-lech",  # Lechmere
    ):
        assert validate_stop_id(stop_id) == stop_id


def test_validate_stop_id_rejects_unknown_stop() -> None:
    """Stops outside the corridor raise ``ValueError`` — no enumeration in the message."""
    with pytest.raises(ValueError, match="not in the demo scope"):
        validate_stop_id("place-bowdoin")  # Blue Line; valid MBTA stop, out of scope

    with pytest.raises(ValueError):
        validate_stop_id("70075")  # platform-level ID; we want parent stations only

    with pytest.raises(ValueError):
        validate_stop_id("'; DROP TABLE stops;--")  # injection-style nonsense, defence-in-depth


def test_failure_log_does_not_contain_password(caplog: pytest.LogCaptureFixture) -> None:
    """Every auth-failure log record must be free of the password substring."""
    settings = _settings_with_password(_TEST_PASSWORD)
    sentinel = "totally-real-secret-please-do-not-leak"

    caplog.set_level("INFO", logger="gtfs_dleung.auth")
    verify_credentials(_TEST_USERNAME, sentinel, settings=settings)
    verify_credentials("ghost", sentinel, settings=settings)

    for record in caplog.records:
        rendered = record.getMessage() + " " + str(record.args) + " " + str(record.__dict__)
        assert sentinel not in rendered, f"password leaked in record: {record!r}"


def test_success_log_records_event(caplog: pytest.LogCaptureFixture) -> None:
    """A successful login emits ``auth.login.success`` with the username, no password."""
    settings = _settings_with_password(_TEST_PASSWORD)
    caplog.set_level("INFO", logger="gtfs_dleung.auth")
    verify_credentials(_TEST_USERNAME, _TEST_PASSWORD, settings=settings)

    success_records = [r for r in caplog.records if "auth.login.success" in r.getMessage()]
    assert len(success_records) == 1
    assert _TEST_USERNAME in success_records[0].getMessage()
    assert _TEST_PASSWORD not in success_records[0].getMessage()


def test_log_auth_event_refuses_password_extra() -> None:
    """A caller passing ``password=...`` as an extra raises immediately."""
    with pytest.raises(ValueError, match="must not pass 'password'"):
        log_auth_event(
            "auth.login.success",
            username=_TEST_USERNAME,
            password="this-test-value-is-not-a-real-secret",  # pragma: allowlist secret
        )


def test_build_authenticator_config_shape() -> None:
    """The dict the Streamlit page wires up has the expected top-level keys + nested credential."""
    settings = _settings_with_password(_TEST_PASSWORD)
    config = build_authenticator_config(settings)

    assert set(config.keys()) == {"credentials", "cookie"}
    assert _TEST_USERNAME in config["credentials"]["usernames"]
    user_block = config["credentials"]["usernames"][_TEST_USERNAME]
    assert "name" in user_block
    assert user_block["password"] == settings.gtfs_demo_password_bcrypt
    assert config["cookie"]["expiry_days"] == settings.gtfs_cookie_expiry_days
    assert config["cookie"]["key"] == settings.gtfs_cookie_key
    # The cookie key must NOT be the bcrypt hash — that would let anyone reading
    # the hash forge sessions. We use a separate setting.
    assert config["cookie"]["key"] != settings.gtfs_demo_password_bcrypt
