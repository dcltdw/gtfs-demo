"""Tests for ``gtfs_demo.fetcher.static.fetch_static_feed``."""

from __future__ import annotations

import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

import pytest

from gtfs_demo.config import Settings
from gtfs_demo.fetcher.static import StaticFeedError, fetch_static_feed


def _settings_with_cache(cache_dir: Path) -> Settings:
    return Settings(
        gtfs_static_feed_url="https://example.invalid/MBTA_GTFS.zip",
        gtfs_cache_dir=cache_dir,
        gtfs_static_ttl_days=7,
        gtfs_user_agent="gtfs-demo-test/0.0.1",
    )


def test_fetch_uses_cache_when_fresh(
    tmp_path: Path,
    mbta_mini_zip: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh cache short-circuits — no network call."""
    settings = _settings_with_cache(tmp_path / "cache")
    unzipped_dir = settings.gtfs_cache_dir / "current"
    unzipped_dir.mkdir(parents=True)
    with zipfile.ZipFile(mbta_mini_zip) as zf:
        zf.extractall(unzipped_dir)

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("Network call attempted despite fresh cache")

    monkeypatch.setattr("gtfs_demo.fetcher.static.requests.get", boom)

    result = fetch_static_feed(settings=settings)

    assert result == unzipped_dir
    assert (result / "stops.txt").exists()


def test_fetch_force_refresh_bypasses_cache(
    tmp_path: Path,
    mbta_mini_zip: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``force_refresh=True`` triggers a download even when the cache is fresh."""
    settings = _settings_with_cache(tmp_path / "cache")
    unzipped_dir = settings.gtfs_cache_dir / "current"
    unzipped_dir.mkdir(parents=True)
    (unzipped_dir / "stops.txt").write_text("placeholder\n")

    zip_bytes = mbta_mini_zip.read_bytes()

    class FakeResponse:
        content = zip_bytes

        def raise_for_status(self) -> None:
            pass

    def fake_get(url: str, headers: dict[str, str], timeout: int) -> FakeResponse:
        assert "User-Agent" in headers
        assert headers["User-Agent"].startswith("gtfs-demo-test/")
        return FakeResponse()

    monkeypatch.setattr("gtfs_demo.fetcher.static.requests.get", fake_get)

    result = fetch_static_feed(settings=settings, force_refresh=True)

    assert result == unzipped_dir
    # The placeholder file should have been replaced by the actual zip contents.
    assert (result / "routes.txt").exists()
    assert "placeholder" not in (result / "stops.txt").read_text()


def test_fetch_raises_on_stale_cache_and_network_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty cache + network down → ``StaticFeedError``."""
    settings = _settings_with_cache(tmp_path / "cache")

    import requests

    def fake_get(*_args: Any, **_kwargs: Any) -> Any:
        raise requests.ConnectionError("network down")

    monkeypatch.setattr("gtfs_demo.fetcher.static.requests.get", fake_get)

    with pytest.raises(StaticFeedError, match="Failed to fetch"):
        fetch_static_feed(settings=settings)


def test_fetch_raises_on_corrupt_zip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Garbage-bytes response → ``StaticFeedError`` referencing the zip."""
    settings = _settings_with_cache(tmp_path / "cache")

    class CorruptResponse:
        content = b"not a zip"

        def raise_for_status(self) -> None:
            pass

    monkeypatch.setattr(
        "gtfs_demo.fetcher.static.requests.get",
        lambda *_a, **_k: CorruptResponse(),
    )

    with pytest.raises(StaticFeedError, match="not a valid zip"):
        fetch_static_feed(settings=settings)


def test_fetch_redownloads_when_cache_is_stale(
    tmp_path: Path,
    mbta_mini_zip: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cache older than the TTL triggers a redownload."""
    settings = _settings_with_cache(tmp_path / "cache")
    unzipped_dir = settings.gtfs_cache_dir / "current"
    unzipped_dir.mkdir(parents=True)
    (unzipped_dir / "stops.txt").write_text("stale\n")

    # Backdate the cache mtime to 30 days ago.
    stale_mtime = time.time() - 30 * 24 * 3600
    import os

    os.utime(unzipped_dir, (stale_mtime, stale_mtime))

    zip_bytes = mbta_mini_zip.read_bytes()
    call_count = {"n": 0}

    class FreshResponse:
        content = zip_bytes

        def raise_for_status(self) -> None:
            pass

    def fake_get(*_args: Any, **_kwargs: Any) -> FreshResponse:
        call_count["n"] += 1
        return FreshResponse()

    monkeypatch.setattr("gtfs_demo.fetcher.static.requests.get", fake_get)

    fetch_static_feed(settings=settings)

    assert call_count["n"] == 1, "stale cache should have triggered exactly one download"
    # Cache was replaced
    assert "stale" not in (unzipped_dir / "stops.txt").read_text()
    shutil.rmtree(unzipped_dir, ignore_errors=True)
