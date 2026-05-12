"""Static GTFS feed fetcher.

Downloads the MBTA static GTFS zip to a cache directory and unzips it. Subsequent
calls within the TTL skip the network and return the cached directory.

Graceful degradation (stale-cache fallback on network failure) is intentionally
out of scope here — that lands in #8.
"""

from __future__ import annotations

import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import requests

from gtfs_demo.config import Settings, get_settings


class StaticFeedError(Exception):
    """Raised when the static feed cannot be fetched or unzipped."""


def fetch_static_feed(
    *,
    settings: Settings | None = None,
    force_refresh: bool = False,
) -> Path:
    """Ensure a fresh GTFS feed is unzipped under the cache directory.

    Returns the directory containing the unzipped CSVs. The directory is reused
    across calls while it is younger than ``settings.gtfs_static_ttl_days``.

    Raises ``StaticFeedError`` on any network or zip-corruption failure when no
    fresh cache is available. Stale-cache fallback is deliberately out of scope —
    feed-staleness handling lands in #8.
    """
    settings = settings or get_settings()
    cache_dir = settings.gtfs_cache_dir
    unzipped_dir = cache_dir / "current"

    if not force_refresh and _is_fresh(unzipped_dir, settings.gtfs_static_ttl_days):
        return unzipped_dir

    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_path = cache_dir / "MBTA_GTFS.zip"

    try:
        response = requests.get(
            settings.gtfs_static_feed_url,
            headers={"User-Agent": settings.gtfs_user_agent},
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise StaticFeedError(
            f"Failed to fetch GTFS feed from {settings.gtfs_static_feed_url}: {exc}"
        ) from exc

    zip_path.write_bytes(response.content)

    try:
        if unzipped_dir.exists():
            shutil.rmtree(unzipped_dir)
        unzipped_dir.mkdir(parents=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(unzipped_dir)
    except zipfile.BadZipFile as exc:
        raise StaticFeedError(f"Downloaded file at {zip_path} is not a valid zip: {exc}") from exc

    return unzipped_dir


def _is_fresh(dir_path: Path, ttl_days: int) -> bool:
    if not dir_path.exists():
        return False
    mtime = datetime.fromtimestamp(dir_path.stat().st_mtime)
    return datetime.now() - mtime < timedelta(days=ttl_days)
