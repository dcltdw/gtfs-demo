"""Capture real GTFS-RT feed snapshots into ``examples/``.

Writes two files per feed:

- ``<feed>_<timestamp>.pb`` — the raw protobuf bytes (truncated for size).
- ``<feed>_<timestamp>.json`` — the same message decoded to JSON (browsable).

Invoke via ``just snapshot`` or directly::

    uv run python scripts/capture_snapshots.py

Truncation: real-feed snapshots can be sizeable (TripUpdates.pb ~1 MB),
which would trip pre-commit's ``check-added-large-files`` hook (1024 KB cap).
We keep the first 100 entities of each feed — enough to be representative
without inflating the repo. The committed JSON twin is larger but stays well
under the cap.

The script is the source of truth for the ``examples/`` snapshots; the fallback
loader (``gtfs_dleung.fetcher.fallback.load_snapshot_fallback``) consumes the
files this script writes.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from google.protobuf.json_format import MessageToJson
from google.transit import gtfs_realtime_pb2

from gtfs_dleung.config import get_settings
from gtfs_dleung.feeds import (
    SERVICE_ALERTS_URL,
    TRIP_UPDATES_URL,
    VEHICLE_POSITIONS_URL,
)
from gtfs_dleung.fetcher.realtime import fetch_feed
from gtfs_dleung.models.feed_health import FeedType

_MAX_ENTITIES = 100

_URL_TO_TYPE: dict[str, FeedType] = {
    TRIP_UPDATES_URL: FeedType.TRIP_UPDATES,
    VEHICLE_POSITIONS_URL: FeedType.VEHICLE_POSITIONS,
    SERVICE_ALERTS_URL: FeedType.SERVICE_ALERTS,
}


def _truncate(msg: gtfs_realtime_pb2.FeedMessage, n: int) -> gtfs_realtime_pb2.FeedMessage:
    trimmed = gtfs_realtime_pb2.FeedMessage()
    trimmed.header.CopyFrom(msg.header)
    for entity in list(msg.entity)[:n]:
        new = trimmed.entity.add()
        new.CopyFrom(entity)
    return trimmed


def capture_one(url: str, out_dir: Path) -> tuple[Path, Path]:
    """Fetch ``url`` and write both ``.pb`` and ``.json`` into ``out_dir``.

    Returns ``(pb_path, json_path)``.
    """
    msg = fetch_feed(url, settings=get_settings())
    msg = _truncate(msg, _MAX_ENTITIES)

    feed_type = _URL_TO_TYPE[url].value  # e.g. "trip_updates"
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    base = out_dir / f"{feed_type}_{timestamp}"
    pb_path = base.with_suffix(".pb")
    json_path = base.with_suffix(".json")

    pb_path.write_bytes(msg.SerializeToString())
    json_path.write_text(
        MessageToJson(msg, indent=2, preserving_proto_field_name=True),
        encoding="utf-8",
    )
    print(
        f"  wrote {pb_path.name} ({pb_path.stat().st_size / 1024:.1f} KB)"
        f" + {json_path.name} ({json_path.stat().st_size / 1024:.1f} KB)"
    )
    return pb_path, json_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "examples",
        help="Output directory for snapshot files.",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    print(f"Capturing snapshots into {args.out}")
    for url in (TRIP_UPDATES_URL, VEHICLE_POSITIONS_URL, SERVICE_ALERTS_URL):
        print(f"Fetching {url}")
        try:
            capture_one(url, args.out)
        except Exception as exc:
            print(f"  ! failed: {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
