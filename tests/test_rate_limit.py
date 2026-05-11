"""Tests for ``gtfs_dleung.security.rate_limit.SessionRateLimiter``."""

from __future__ import annotations

import pytest

from gtfs_dleung.security.rate_limit import SessionRateLimiter


def test_under_limit_allows() -> None:
    """N-1 acquires under the limit all return ``True``."""
    limiter = SessionRateLimiter(limit=5, window_s=60)
    for i in range(4):
        assert limiter.acquire("session-A", now=i) is True


def test_over_limit_blocks() -> None:
    """The (limit+1)-th acquire within a window returns ``False``."""
    limiter = SessionRateLimiter(limit=3, window_s=60)
    assert limiter.acquire("session-A", now=0.0) is True
    assert limiter.acquire("session-A", now=1.0) is True
    assert limiter.acquire("session-A", now=2.0) is True
    assert limiter.acquire("session-A", now=3.0) is False, "fourth call exceeds limit=3"
    assert limiter.acquire("session-A", now=4.0) is False, "subsequent calls still blocked"


def test_window_slides() -> None:
    """When the oldest event leaves the window, budget is replenished."""
    limiter = SessionRateLimiter(limit=2, window_s=10)
    assert limiter.acquire("session-A", now=0.0) is True
    assert limiter.acquire("session-A", now=1.0) is True
    assert limiter.acquire("session-A", now=2.0) is False
    # Advance past the window; the events at t=0 and t=1 fall off.
    assert limiter.acquire("session-A", now=12.0) is True
    assert limiter.acquire("session-A", now=12.5) is True
    assert limiter.acquire("session-A", now=13.0) is False, "limit applies in the new window too"


def test_independent_sessions_independent_counters() -> None:
    """Per-session counters don't interfere with each other."""
    limiter = SessionRateLimiter(limit=2, window_s=60)
    # Session A: fully consumes its budget.
    assert limiter.acquire("session-A", now=0.0) is True
    assert limiter.acquire("session-A", now=1.0) is True
    assert limiter.acquire("session-A", now=2.0) is False
    # Session B: untouched; still has full budget.
    assert limiter.acquire("session-B", now=2.0) is True
    assert limiter.acquire("session-B", now=3.0) is True
    assert limiter.acquire("session-B", now=4.0) is False


def test_eviction_after_idle() -> None:
    """A session idle longer than ``idle_evict_s`` is dropped from the limiter's memory."""
    limiter = SessionRateLimiter(limit=5, window_s=60, idle_evict_s=300)
    limiter.acquire("session-A", now=0.0)
    limiter.acquire("session-B", now=0.0)
    assert limiter.session_count() == 2

    # Advance long past idle eviction; another session's acquire triggers the sweep.
    limiter.acquire("session-C", now=10_000.0)

    assert limiter.session_count() == 1, "stale sessions A + B should have been evicted"


def test_remaining_reports_budget() -> None:
    """``remaining`` returns the budget left without consuming any."""
    limiter = SessionRateLimiter(limit=3, window_s=60)
    assert limiter.remaining("session-A", now=0.0) == 3
    limiter.acquire("session-A", now=0.0)
    assert limiter.remaining("session-A", now=0.0) == 2
    limiter.acquire("session-A", now=1.0)
    assert limiter.remaining("session-A", now=1.0) == 1
    limiter.acquire("session-A", now=2.0)
    assert limiter.remaining("session-A", now=2.0) == 0
    # Calling remaining doesn't consume — repeated calls give the same value.
    assert limiter.remaining("session-A", now=2.0) == 0


def test_remaining_for_unknown_session() -> None:
    """A never-seen session has the full limit available."""
    limiter = SessionRateLimiter(limit=7, window_s=60)
    assert limiter.remaining("never-seen", now=0.0) == 7


def test_throttle_emits_structured_log(caplog: pytest.LogCaptureFixture) -> None:
    """A throttled call emits a structured INFO record naming session + limit."""
    limiter = SessionRateLimiter(limit=1, window_s=60)
    caplog.set_level("INFO", logger="gtfs_dleung.security.rate_limit")
    limiter.acquire("session-A", now=0.0)
    limiter.acquire("session-A", now=1.0)  # over limit

    throttle_records = [
        r for r in caplog.records if "inbound rate-limit throttle" in r.getMessage()
    ]
    assert len(throttle_records) == 1
    assert "session-A" in throttle_records[0].getMessage()


def test_constructor_validates_arguments() -> None:
    """Invalid limits / windows raise immediately."""
    with pytest.raises(ValueError, match="limit"):
        SessionRateLimiter(limit=0, window_s=60)
    with pytest.raises(ValueError, match="window_s"):
        SessionRateLimiter(limit=5, window_s=0)
    with pytest.raises(ValueError, match="idle_evict_s must exceed window_s"):
        SessionRateLimiter(limit=5, window_s=60, idle_evict_s=30)
