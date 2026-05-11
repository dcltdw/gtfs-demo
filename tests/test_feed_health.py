"""Tests for ``gtfs_dleung.fetcher.health.HealthTrackedFetcher``."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta

import pytest
from google.transit import gtfs_realtime_pb2

from gtfs_dleung.config import Settings
from gtfs_dleung.feeds import TRIP_UPDATES_URL
from gtfs_dleung.fetcher.health import HealthTrackedFetcher
from gtfs_dleung.fetcher.realtime import TransientFeedError
from gtfs_dleung.models.feed_health import FeedType


def _settings(threshold: int = 30) -> Settings:
    return Settings(gtfs_stale_threshold_s=threshold)


def _message_with_timestamp(unix_seconds: int) -> gtfs_realtime_pb2.FeedMessage:
    msg = gtfs_realtime_pb2.FeedMessage()
    msg.header.gtfs_realtime_version = "2.0"
    msg.header.incrementality = 0
    msg.header.timestamp = unix_seconds
    return msg


class _ClockStub:
    def __init__(self, start: datetime) -> None:
        self._t = start

    def now(self) -> datetime:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += timedelta(seconds=seconds)


def test_stale_when_timestamp_older_than_threshold() -> None:
    """If the feed's header.timestamp is older than the threshold, ``is_stale`` flips True."""
    clock = _ClockStub(datetime(2026, 5, 11, 12, 0, tzinfo=UTC))
    fetch_calls: list[str] = []

    def fake_fetch(url: str, **_: object) -> gtfs_realtime_pb2.FeedMessage:
        fetch_calls.append(url)
        return _message_with_timestamp(int(clock.now().timestamp()) - 60)  # 60s old

    tracker = HealthTrackedFetcher(
        settings=_settings(threshold=30), fetch_fn=fake_fetch, now_fn=clock.now
    )

    _, health = tracker.fetch(TRIP_UPDATES_URL)

    assert health.feed_type == FeedType.TRIP_UPDATES
    assert health.age_seconds == pytest.approx(60.0)
    assert health.is_stale is True
    assert health.is_degraded is False
    assert health.last_success_at == clock.now()
    assert len(fetch_calls) == 1


def test_fresh_when_timestamp_within_threshold() -> None:
    """A timestamp well inside the threshold reports ``is_stale=False``."""
    clock = _ClockStub(datetime(2026, 5, 11, 12, 0, tzinfo=UTC))

    def fake_fetch(url: str, **_: object) -> gtfs_realtime_pb2.FeedMessage:
        return _message_with_timestamp(int(clock.now().timestamp()) - 5)  # 5s old

    tracker = HealthTrackedFetcher(settings=_settings(30), fetch_fn=fake_fetch, now_fn=clock.now)

    _, health = tracker.fetch(TRIP_UPDATES_URL)

    assert health.age_seconds == pytest.approx(5.0)
    assert health.is_stale is False
    assert health.is_degraded is False


def test_falls_back_to_cache_on_fetch_failure() -> None:
    """A successful fetch primes the cache; a subsequent failure returns the cache + degraded."""
    clock = _ClockStub(datetime(2026, 5, 11, 12, 0, tzinfo=UTC))
    behaviour: list[str] = ["ok", "fail"]
    primed_msg = _message_with_timestamp(int(clock.now().timestamp()))

    def fake_fetch(url: str, **_: object) -> gtfs_realtime_pb2.FeedMessage:
        action = behaviour.pop(0)
        if action == "fail":
            raise TransientFeedError("simulated network down")
        return primed_msg

    tracker = HealthTrackedFetcher(settings=_settings(30), fetch_fn=fake_fetch, now_fn=clock.now)

    msg1, health1 = tracker.fetch(TRIP_UPDATES_URL)
    assert msg1 is primed_msg
    assert health1.is_degraded is False

    clock.advance(45)  # data is now 45s old in addition to the failure
    msg2, health2 = tracker.fetch(TRIP_UPDATES_URL)

    assert msg2 is primed_msg, "must return the cached message on fetch failure"
    assert health2.is_degraded is True
    assert health2.is_stale is True  # data is 45s old now
    assert health2.last_success_at == datetime(2026, 5, 11, 12, 0, tzinfo=UTC)


def test_raises_when_first_fetch_fails_with_no_cache() -> None:
    """No cache + fetch failure → the error propagates."""
    clock = _ClockStub(datetime(2026, 5, 11, 12, 0, tzinfo=UTC))

    def fake_fetch(url: str, **_: object) -> gtfs_realtime_pb2.FeedMessage:
        raise TransientFeedError("no cache, no data")

    tracker = HealthTrackedFetcher(settings=_settings(30), fetch_fn=fake_fetch, now_fn=clock.now)

    with pytest.raises(TransientFeedError):
        tracker.fetch(TRIP_UPDATES_URL)


def test_metrics_counters_increment() -> None:
    """``fetches_total`` increments on every attempt; ``fetch_errors_total`` only on failure."""
    clock = _ClockStub(datetime(2026, 5, 11, 12, 0, tzinfo=UTC))
    plan = ["ok", "fail", "ok", "fail"]
    primed = _message_with_timestamp(int(clock.now().timestamp()))

    def fake_fetch(url: str, **_: object) -> gtfs_realtime_pb2.FeedMessage:
        action = plan.pop(0)
        if action == "fail":
            raise TransientFeedError("simulated")
        return primed

    tracker = HealthTrackedFetcher(settings=_settings(30), fetch_fn=fake_fetch, now_fn=clock.now)

    for _ in range(4):
        with contextlib.suppress(TransientFeedError):
            tracker.fetch(TRIP_UPDATES_URL)

    metrics = tracker.get_metrics()[TRIP_UPDATES_URL]
    assert metrics["fetches_total"] == 4
    assert metrics["fetch_errors_total"] == 2
    assert metrics["feed_age_seconds"] == pytest.approx(0.0, abs=1.0)


def test_staleness_transition_logs_once(caplog: pytest.LogCaptureFixture) -> None:
    """``fresh → stale`` and ``stale → fresh`` each emit exactly one structured log line."""
    clock = _ClockStub(datetime(2026, 5, 11, 12, 0, tzinfo=UTC))
    ts_offsets = [5, 5, 60, 60, 5]  # fresh, fresh, stale, stale, fresh

    def fake_fetch(url: str, **_: object) -> gtfs_realtime_pb2.FeedMessage:
        offset = ts_offsets.pop(0)
        return _message_with_timestamp(int(clock.now().timestamp()) - offset)

    tracker = HealthTrackedFetcher(settings=_settings(30), fetch_fn=fake_fetch, now_fn=clock.now)

    caplog.set_level("INFO", logger="gtfs_dleung.fetcher.health")
    for _ in range(5):
        tracker.fetch(TRIP_UPDATES_URL)

    transitions = [r.message for r in caplog.records if "transition" in r.message]
    assert len(transitions) == 2, f"expected 2 transitions, got {transitions}"
    assert "direction=stale" in transitions[0]
    assert "direction=fresh" in transitions[1]


def test_get_health_aggregates_across_feeds() -> None:
    """A tracker that's fetched both trip_updates and vehicle_positions reports both keys."""
    from gtfs_dleung.feeds import VEHICLE_POSITIONS_URL

    clock = _ClockStub(datetime(2026, 5, 11, 12, 0, tzinfo=UTC))

    def fake_fetch(url: str, **_: object) -> gtfs_realtime_pb2.FeedMessage:
        return _message_with_timestamp(int(clock.now().timestamp()) - 3)

    tracker = HealthTrackedFetcher(settings=_settings(30), fetch_fn=fake_fetch, now_fn=clock.now)

    tracker.fetch(TRIP_UPDATES_URL)
    tracker.fetch(VEHICLE_POSITIONS_URL)

    health = tracker.get_health()
    assert set(health.keys()) == {FeedType.TRIP_UPDATES, FeedType.VEHICLE_POSITIONS}


def test_feed_message_without_header_timestamp_reports_none_age() -> None:
    """A feed message lacking ``header.timestamp`` reports ``age_seconds=None``, not crashes."""
    clock = _ClockStub(datetime(2026, 5, 11, 12, 0, tzinfo=UTC))

    def fake_fetch(url: str, **_: object) -> gtfs_realtime_pb2.FeedMessage:
        msg = gtfs_realtime_pb2.FeedMessage()
        msg.header.gtfs_realtime_version = "2.0"
        msg.header.incrementality = 0
        # Note: no timestamp set.
        return msg

    tracker = HealthTrackedFetcher(settings=_settings(30), fetch_fn=fake_fetch, now_fn=clock.now)

    _, health = tracker.fetch(TRIP_UPDATES_URL)
    assert health.age_seconds is None
    assert health.is_stale is False
