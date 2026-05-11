---
id: F-001
title: Static GTFS feed loader + scope filter
type: functional
status: in-progress
issue: 3
pr: null
depends_on: [NF-001, NF-002]
owner: dcltdw
last_updated: 2026-05-11
---

## Summary

Download the MBTA static GTFS bundle from `cdn.mbta.com`, cache the unzipped CSVs under a configurable directory (default `~/.cache/gtfs-dleung/`), and parse the rows into Pydantic v2 models. A separate `filter_to_scope` step trims the parsed feed to the demo corridors — Red Line (Park ↔ Davis) and Green Line E (Park ↔ Ball Square) — using both route-id and parent-station membership. The Pydantic models are the canonical typed boundary; CSV/dict shapes live only inside the loader.

## Inputs

- `Settings.gtfs_static_feed_url` (env-backed; default `https://cdn.mbta.com/MBTA_GTFS.zip`).
- `Settings.gtfs_cache_dir` (env-backed; default `~/.cache/gtfs-dleung/`).
- `Settings.gtfs_static_ttl_days` (env-backed; default `7`).
- `Settings.gtfs_user_agent` (env-backed; identifies the app + URL to the project).
- The committed test fixture at `tests/fixtures/mbta-mini.zip` (~7 KB).

## Behaviour

1. `fetch_static_feed(settings=None, force_refresh=False)` returns the path to the unzipped feed directory.
2. If the cache directory exists and its mtime is younger than `gtfs_static_ttl_days`, no network call is made.
3. Otherwise the function downloads the zip to `<cache_dir>/MBTA_GTFS.zip`, then unzips into `<cache_dir>/current/`, replacing any prior unzipped state.
4. The HTTP request sends a `User-Agent` header drawn from settings.
5. Network failures raise `StaticFeedError` (a typed, user-facing exception — no raw `requests` traceback escapes).
6. Non-zip responses (corrupt download, HTML error page, etc.) raise `StaticFeedError`.
7. `load_feed_from_dir(feed_dir)` returns a populated `StaticFeed` with five lists of typed rows: `stops`, `routes`, `trips`, `stop_times`, `shapes`.
8. `filter_to_scope(feed)` returns a new `StaticFeed` containing only Red Line + Green-E entities; stop_times are trimmed to the corridor stop set.

## Outputs

- `Path` returned by `fetch_static_feed` (directory containing the unzipped CSVs).
- `StaticFeed` (Pydantic model) returned by `load_feed_from_dir` and `filter_to_scope`.
- `StaticFeedError` / `StaticParseError` raised on the corresponding failure modes.

## Edge cases

- **Missing required CSV after unzip** (e.g. a malformed feed missing `routes.txt`): `load_feed_from_dir` raises `StaticParseError` naming the missing file.
- **GTFS times exceeding 24h** (e.g. `27:30:00` for the prior service day): `StopTime.arrival_time` and `departure_time` are kept as strings to preserve them; conversion is the consumer's responsibility.
- **Stops with empty `parent_station`**: parsed as `None`, then ignored by the filter's parent-station membership test (so a top-level stop with no parent is only kept if its own `stop_id` is in the corridor).
- **Shared platforms at Park Street** (Green-B/C/D + Green-E + Red): the filter is route-aware (`SCOPE_ROUTES = {Red, Green-E}`), so B/C/D trips are dropped even though their stops overlap with E's.
- **Stale cache + network down**: `StaticFeedError` is raised; stale-cache fallback is intentionally deferred to #8.
- **`force_refresh=True`**: bypass cache freshness check and re-download.

## Out of scope

- Conditional GET via `If-Modified-Since` / `ETag` (post-demo #16).
- Stale-cache graceful degradation (pre-demo #8).
- GTFS-RT (`gtfs_dleung.parser.static` is for the static bundle only).
- Real-time arrival-board logic (#5).
- Anything beyond the Red Line + Green-E corridors.

## Verification

- `tests/test_static_loader.py::test_fetch_uses_cache_when_fresh` — fresh cache short-circuits.
- `tests/test_static_loader.py::test_fetch_force_refresh_bypasses_cache` — `force_refresh=True` always downloads.
- `tests/test_static_loader.py::test_fetch_raises_on_stale_cache_and_network_failure` — empty cache + network down → typed exception.
- `tests/test_static_loader.py::test_fetch_raises_on_corrupt_zip` — non-zip response → typed exception.
- `tests/test_static_loader.py::test_fetch_redownloads_when_cache_is_stale` — TTL expiry triggers exactly one redownload.
- `tests/test_static_filter.py::test_load_fixture_into_pydantic_models` — fixture parses cleanly.
- `tests/test_static_filter.py::test_filter_keeps_only_red_and_green_e` — out-of-scope routes dropped.
- `tests/test_static_filter.py::test_scope_corridor_stop_count` — every kept stop lives inside a corridor parent station.
- `tests/test_static_filter.py::test_filter_trims_stop_times_to_in_scope_trips` — out-of-scope `stop_times` dropped.
- `tests/test_static_filter.py::test_filter_shapes_match_kept_trips` — `shapes` for out-of-scope routes dropped.

Manual:

```bash
uv run python -c "from gtfs_dleung.fetcher.static import fetch_static_feed; \
                  from gtfs_dleung.parser.static import load_feed_from_dir, filter_to_scope; \
                  feed = filter_to_scope(load_feed_from_dir(fetch_static_feed())); \
                  print(len(feed.routes), 'routes,', len(feed.stops), 'stops,', \
                        len(feed.stop_times), 'stop_times,', len(feed.shapes), 'shape points')"
```

## Open questions

_None._
