"""Tests for ``gtfs_demo.fetcher.realtime.fetch_feed``."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, cast

import pytest
import requests

from gtfs_demo.config import Settings
from gtfs_demo.fetcher.rate_limit import OutboundRateLimiter
from gtfs_demo.fetcher.realtime import (
    PermanentFeedError,
    TransientFeedError,
    fetch_feed,
)

FIXTURE_URL = "https://example.invalid/realtime/TripUpdates.pb"


def _settings() -> Settings:
    return Settings(
        gtfs_user_agent="gtfs-demo-test/0.0.1 (David Leung; claude.unraveled663@simplelogin.com)",
        gtfs_rt_fetch_interval_seconds=10,
    )


class _Resp:
    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class _SessionStub:
    """Mock ``requests.Session`` capturing every ``.get(...)`` call."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, *, headers: dict[str, str], timeout: int) -> Any:
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        if not self._responses:
            raise AssertionError("No mocked response left")
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


@pytest.fixture
def tripupdates_pb() -> bytes:
    return (Path(__file__).parent / "fixtures" / "tripupdates_sample.pb").read_bytes()


def test_user_agent_header_present(tripupdates_pb: bytes) -> None:
    """Every outgoing request carries the configured ``User-Agent``."""
    settings = _settings()
    session = _SessionStub([_Resp(tripupdates_pb)])
    limiter = OutboundRateLimiter(interval_seconds=10)

    fetch_feed(
        FIXTURE_URL,
        settings=settings,
        rate_limiter=limiter,
        session=cast(requests.Session, session),
    )

    assert len(session.calls) == 1
    assert session.calls[0]["headers"]["User-Agent"] == settings.gtfs_user_agent


def test_outbound_rate_limit_blocks_second_call(
    tripupdates_pb: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second fetch within the interval must wait."""
    settings = _settings()
    limiter = OutboundRateLimiter(interval_seconds=10)
    session = _SessionStub([_Resp(tripupdates_pb), _Resp(tripupdates_pb)])

    slept: list[float] = []
    monkeypatch.setattr("gtfs_demo.fetcher.rate_limit.time.sleep", slept.append)

    fetch_feed(
        FIXTURE_URL,
        settings=settings,
        rate_limiter=limiter,
        session=cast(requests.Session, session),
    )
    fetch_feed(
        FIXTURE_URL,
        settings=settings,
        rate_limiter=limiter,
        session=cast(requests.Session, session),
    )

    assert len(slept) == 1
    # The second call should be asked to sleep something close to the full interval
    # (allowing tiny wall-clock between the two acquire calls).
    assert slept[0] > 9.0
    assert slept[0] <= 10.0


def test_retry_on_5xx_then_success(
    tripupdates_pb: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 502 is retried; the second attempt's 200 is returned."""
    settings = _settings()
    limiter = OutboundRateLimiter(interval_seconds=0.001)
    session = _SessionStub([_Resp(b"", status_code=502), _Resp(tripupdates_pb)])
    # Skip tenacity's exponential sleep
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda _s: None)

    feed = fetch_feed(
        FIXTURE_URL,
        settings=settings,
        rate_limiter=limiter,
        session=cast(requests.Session, session),
    )

    assert len(session.calls) == 2
    assert len(feed.entity) > 0


def test_no_retry_on_4xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """4xx is permanent — no retry, ``PermanentFeedError`` raised."""
    settings = _settings()
    limiter = OutboundRateLimiter(interval_seconds=0.001)
    session = _SessionStub([_Resp(b"", status_code=400)])
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda _s: None)

    with pytest.raises(PermanentFeedError, match="400"):
        fetch_feed(
            FIXTURE_URL,
            settings=settings,
            rate_limiter=limiter,
            session=cast(requests.Session, session),
        )

    assert len(session.calls) == 1


def test_parses_protobuf_from_fixture(tripupdates_pb: bytes) -> None:
    """Decoding the committed fixture into a ``FeedMessage`` works end-to-end."""
    settings = _settings()
    limiter = OutboundRateLimiter(interval_seconds=0.001)
    session = _SessionStub([_Resp(tripupdates_pb)])

    feed = fetch_feed(
        FIXTURE_URL,
        settings=settings,
        rate_limiter=limiter,
        session=cast(requests.Session, session),
    )

    assert feed.header.gtfs_realtime_version == "2.0"
    assert len(feed.entity) == 20  # see scripts that built the fixture


def test_transient_after_max_retries_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All three 5xx attempts → ``TransientFeedError``."""
    settings = _settings()
    limiter = OutboundRateLimiter(interval_seconds=0.001)
    session = _SessionStub(
        [_Resp(b"", status_code=503), _Resp(b"", status_code=503), _Resp(b"", status_code=503)]
    )
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda _s: None)

    with pytest.raises(TransientFeedError):
        fetch_feed(
            FIXTURE_URL,
            settings=settings,
            rate_limiter=limiter,
            session=cast(requests.Session, session),
        )

    assert len(session.calls) == 3


def test_timeout_is_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    """``requests.Timeout`` is retried (transient)."""
    settings = _settings()
    limiter = OutboundRateLimiter(interval_seconds=0.001)
    session = _SessionStub(
        [
            requests.Timeout("read timeout"),
            requests.Timeout("read timeout"),
            requests.Timeout("read timeout"),
        ]
    )
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda _s: None)

    with pytest.raises(TransientFeedError):
        fetch_feed(
            FIXTURE_URL,
            settings=settings,
            rate_limiter=limiter,
            session=cast(requests.Session, session),
        )

    assert len(session.calls) == 3


def test_rate_limiter_per_url_independence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two distinct URLs share no quota."""
    monkeypatch.setattr("gtfs_demo.fetcher.rate_limit.time.sleep", lambda _s: None)
    limiter = OutboundRateLimiter(interval_seconds=10)

    base = time.monotonic()
    assert limiter.acquire("https://a.example/A.pb", now=base) == 0.0
    assert limiter.acquire("https://b.example/B.pb", now=base) == 0.0
