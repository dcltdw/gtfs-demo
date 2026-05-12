# `examples/` — committed GTFS-RT snapshots

Each file in this directory is a real capture of one of MBTA's three GTFS-RT feeds, truncated to ~100 entities and committed for two purposes:

1. **Browseable data shape.** A reader who wants to know "what does a TripUpdate actually look like?" can open the `.json` twin in their editor — no Python, no protoc, no running server. The `.json` is the same protobuf message decoded via `google.protobuf.json_format.MessageToJson`.
2. **Hard-snapshot fallback.** When the live MBTA CDN is unreachable AND the in-memory cache is empty (process just started during a network outage), [gtfs_demo/fetcher/fallback.py](../gtfs_demo/fetcher/fallback.py) loads the most recent `.pb` for each feed type from here. The Streamlit demo stays usable on a cold-start outage instead of going blank. See [docs/agent-spec/F-006-feed-staleness.md](../docs/agent-spec/F-006-feed-staleness.md) for the three-tier data path.

## Files

Filename convention: `<feed_type>_<YYYYMMDDTHHMMSSZ>.{pb,json}`, where `feed_type` is one of:

- `trip_updates`
- `vehicle_positions`
- `service_alerts`

`.pb` is the truncated protobuf message (binary, ~10–400 KB depending on feed). `.json` is the same message decoded to a human-readable JSON tree (~80–800 KB; protoc enum names are preserved).

Only the most recent timestamp per feed is consulted by the fallback loader; older snapshots are kept as historical reference but don't affect runtime.

## Regenerating

```bash
just snapshot
# or directly:
uv run python scripts/capture_snapshots.py
```

The script fetches all three feeds via `gtfs_demo.fetcher.realtime.fetch_feed` (so the same `User-Agent` + outbound rate limit apply), truncates each to 100 entities, and writes the `.pb` + `.json` pair into this directory.

**When to regenerate:**

- Before a demo cycle, so the fallback shows fresh-ish data if the live feeds fail mid-call.
- After a GTFS-RT spec update that changes the wire format (rare).
- When debugging a specific data shape — capture a real-world example, commit it, write a test that pins the parser's behaviour against it.

**Don't regenerate** in the same PR as parser or feed-health logic changes — the snapshots become noise in the diff. Land code changes first, then refresh snapshots in a follow-up if needed.

## Storage budget

The pre-commit hook `check-added-large-files` caps individual files at 1024 KB. The script's 100-entity truncation keeps every committed file under that limit (the largest committed file today is ~750 KB for Alerts JSON, which includes long human-readable advisory text in multiple translations).

If a future feed exceeds the cap, lower the `_MAX_ENTITIES` constant in `scripts/capture_snapshots.py` rather than raising the cap — the cap exists to keep clone sizes bounded.

## What's NOT committed here

- **Test fixtures** for the parser tests live under [tests/fixtures/](../tests/fixtures/). Those are intentionally tinier (~5–40 KB) and shaped to cover specific parser edge cases. The examples here are for general browsing + production fallback; the test fixtures are for unit tests.
- **The static GTFS bundle** is downloaded into `~/.cache/gtfs-demo/` on first run; it's not committed (~17 MB unzipped).
