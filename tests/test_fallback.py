"""Tests for the hard-snapshot fallback (#13).

Covers two layers:

1. :func:`gtfs_demo.fetcher.fallback.load_snapshot_fallback` — the function
   that scans ``examples/`` for the most recent committed snapshot.
2. The integration with :class:`HealthTrackedFetcher` — when a live fetch
   fails AND no in-memory cache exists, the snapshot is loaded and ``is_snapshot``
   is reported on the returned :class:`FeedHealth`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from google.transit import gtfs_realtime_pb2

from gtfs_demo.config import Settings
from gtfs_demo.feeds import TRIP_UPDATES_URL, VEHICLE_POSITIONS_URL
from gtfs_demo.fetcher.fallback import load_snapshot_fallback
from gtfs_demo.fetcher.health import HealthTrackedFetcher
from gtfs_demo.fetcher.realtime import TransientFeedError
from gtfs_demo.models.feed_health import FeedType


def _write_snapshot(
    path: Path, *, timestamp: int, n_entities: int = 1
) -> gtfs_realtime_pb2.FeedMessage:
    """Write a minimal valid FeedMessage to ``path``; return the message for assertions."""
    msg = gtfs_realtime_pb2.FeedMessage()
    msg.header.gtfs_realtime_version = "2.0"
    msg.header.incrementality = 0
    msg.header.timestamp = timestamp
    for i in range(n_entities):
        e = msg.entity.add()
        e.id = f"entity-{i}"
    path.write_bytes(msg.SerializeToString())
    return msg


def test_loads_snapshot_when_live_unavailable(tmp_path: Path) -> None:
    """No in-memory cache + live failure → fall back to committed snapshot + is_snapshot=True."""
    examples = tmp_path / "examples"
    examples.mkdir()
    snapshot_ts = int(datetime(2026, 5, 11, 12, 0, tzinfo=UTC).timestamp())
    expected = _write_snapshot(
        examples / "trip_updates_20260511T120000Z.pb",
        timestamp=snapshot_ts,
        n_entities=3,
    )

    def boom(*_a: object, **_k: object) -> gtfs_realtime_pb2.FeedMessage:
        raise TransientFeedError("network is unreachable")

    fetcher = HealthTrackedFetcher(
        settings=Settings(),
        fetch_fn=boom,
        snapshot_loader=lambda url: load_snapshot_fallback(url, examples_dir=examples),
        now_fn=lambda: datetime(2026, 5, 11, 12, 1, tzinfo=UTC),
    )

    msg, health = fetcher.fetch(TRIP_UPDATES_URL)

    assert len(msg.entity) == len(expected.entity)
    assert health.feed_type == FeedType.TRIP_UPDATES
    assert health.is_snapshot is True
    assert health.is_degraded is True, "snapshot fallback always implies degraded"
    # age_seconds reflects the snapshot's header.timestamp, not the file mtime.
    assert health.age_seconds == pytest.approx(60.0)


def test_uses_most_recent_snapshot_per_type(tmp_path: Path) -> None:
    """When multiple snapshots exist for the same feed, the most recent timestamp wins."""
    examples = tmp_path / "examples"
    examples.mkdir()
    older = int(datetime(2026, 5, 1, 12, 0, tzinfo=UTC).timestamp())
    newer = int(datetime(2026, 5, 10, 12, 0, tzinfo=UTC).timestamp())

    _write_snapshot(examples / "trip_updates_20260501T120000Z.pb", timestamp=older, n_entities=2)
    _write_snapshot(examples / "trip_updates_20260510T120000Z.pb", timestamp=newer, n_entities=7)

    chosen = load_snapshot_fallback(TRIP_UPDATES_URL, examples_dir=examples)

    assert chosen is not None
    assert chosen.header.timestamp == newer
    assert len(chosen.entity) == 7, "newer snapshot's entity count should be served"


def test_no_snapshot_when_examples_dir_missing(tmp_path: Path) -> None:
    """A non-existent examples dir → ``None`` (don't crash)."""
    missing = tmp_path / "no-such-dir"
    assert load_snapshot_fallback(TRIP_UPDATES_URL, examples_dir=missing) is None


def test_no_snapshot_when_feed_url_unmapped(tmp_path: Path) -> None:
    """An unrecognised feed URL → ``None`` (the loader doesn't guess prefixes)."""
    examples = tmp_path / "examples"
    examples.mkdir()
    _write_snapshot(examples / "trip_updates_20260511T120000Z.pb", timestamp=0)
    assert (
        load_snapshot_fallback("https://example.invalid/something.pb", examples_dir=examples)
        is None
    )


def test_corrupt_snapshot_is_ignored(tmp_path: Path) -> None:
    """A garbage `.pb` file → ``None``, doesn't crash the loader."""
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / "trip_updates_20260511T120000Z.pb").write_bytes(b"not a valid protobuf")
    assert load_snapshot_fallback(TRIP_UPDATES_URL, examples_dir=examples) is None


def test_snapshot_cleared_on_subsequent_successful_fetch(tmp_path: Path) -> None:
    """A successful fetch after a snapshot fallback clears ``is_snapshot``."""
    examples = tmp_path / "examples"
    examples.mkdir()
    _write_snapshot(
        examples / "trip_updates_20260511T120000Z.pb",
        timestamp=int(datetime(2026, 5, 11, 12, 0, tzinfo=UTC).timestamp()),
    )

    plan = ["fail", "ok"]

    def planned_fetch(*_a: object, **_k: object) -> gtfs_realtime_pb2.FeedMessage:
        action = plan.pop(0)
        if action == "fail":
            raise TransientFeedError("temporary network down")
        # Success case — return a fresh message.
        msg = gtfs_realtime_pb2.FeedMessage()
        msg.header.gtfs_realtime_version = "2.0"
        msg.header.incrementality = 0
        msg.header.timestamp = int(datetime(2026, 5, 11, 12, 30, tzinfo=UTC).timestamp())
        e = msg.entity.add()
        e.id = "live"
        return msg

    fetcher = HealthTrackedFetcher(
        settings=Settings(),
        fetch_fn=planned_fetch,
        snapshot_loader=lambda url: load_snapshot_fallback(url, examples_dir=examples),
        now_fn=lambda: datetime(2026, 5, 11, 12, 30, tzinfo=UTC),
    )

    # First call falls back to snapshot.
    _, health1 = fetcher.fetch(TRIP_UPDATES_URL)
    assert health1.is_snapshot is True

    # Second call succeeds — flag should clear.
    _, health2 = fetcher.fetch(TRIP_UPDATES_URL)
    assert health2.is_snapshot is False
    assert health2.is_degraded is False


def test_snapshot_disabled_via_explicit_no_op_loader(tmp_path: Path) -> None:
    """Passing a no-op loader disables hard-snapshot fallback entirely."""

    def boom(*_a: object, **_k: object) -> gtfs_realtime_pb2.FeedMessage:
        raise TransientFeedError("down")

    fetcher = HealthTrackedFetcher(
        settings=Settings(),
        fetch_fn=boom,
        snapshot_loader=lambda _url: None,  # explicit no-op
    )
    with pytest.raises(TransientFeedError):
        fetcher.fetch(VEHICLE_POSITIONS_URL)
