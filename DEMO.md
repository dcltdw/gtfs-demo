# Demo runbook

This is the screen-share script for the recruiter call. Reads top-to-bottom; total target time ~15 minutes including Q&A.

**Tiny URL for the project**: <https://dcltdw.github.io/gtfs-dleung/>
**Source repo**: <https://github.com/dcltdw/gtfs-dleung>

## Pre-flight (do before the call, don't show)

```bash
git pull
just install           # installs deps; ~10s on a warm uv cache
just snapshot          # refresh examples/ snapshots — kept fresh so the hard fallback isn't embarrassing if live feeds wobble mid-call
cp .env.example .env   # if you haven't already
```

Confirm the Streamlit app boots:

```bash
just demo              # opens at http://localhost:8501
```

Log in as `demo` / `gtfs-demo-2026` — the seeded credential from `.env.example` (one-way bcrypt'd; see [docs/SECURITY.md](docs/SECURITY.md)).

## Demo sequence

### 1. Open the project page (~1 min)

Open the GitHub Pages URL. Point at:

- The architecture diagram in the README (the Mermaid `flowchart TD`) — "this is the data flow per fetch cycle."
- The three ADRs under [docs/adr/](docs/adr/) — "the three load-bearing decisions."
- The agent specs under [docs/agent-spec/](docs/agent-spec/) — "each functional requirement has a one-page spec; they're how I keep the parser code honest about its contract."

### 2. Live app — the three panels (~5 min)

Switch to the running Streamlit page. Walk through, top to bottom:

- **Scope header**. The blue `st.info` block at the top names the demo's framing: arrivals at Davis (Red) and Ball Sq (Green-E) in both directions; alerts cover the full Park St ↔ Alewife and Park St ↔ Medford/Tufts corridors so a terminus-only alert (e.g. "elevator out at Alewife") still surfaces for a Davis rider. Same block has the **delay color legend**: 🟢 ≤30s on time · 🟠 ≤120s slightly off · 🔴 >120s significantly off — magnitude, so early arrivals use the same bands.
- **Arrivals board** (Davis | Ball Square columns). Each row shows route, scheduled time, predicted time, color-coded delay (both the leading dot and the delay text itself are color-wrapped), and a badge if the trip is `ADDED` (purple) or `CANCELED` (struck through). Mention: this is built on the F-003 parser that handles **partial StopTimeUpdate propagation** — when MBTA sends a delay for stop K, every downstream stop on the same trip inherits that delay until the next explicit update. Without this, half the realtime signal is lost.
- **Active service alerts**. Each is scope-filtered by the `informed_entity` selectors (only alerts that touch Red Line / Green-E / a corridor parent station, which includes the termini). Active-period filter checks the `[start, end)` ranges against `now`. Click an alert to expand — header + description + cause + effect + window.
- **Feed health panel**. Three rows (TripUpdates / VehiclePositions / ServiceAlerts) each showing an icon + age + flag labels. Mention the **two-axis flags** (`is_stale` = data age, `is_degraded` = our-fetch-failing) — they're independent, which matters for the operator.

### 3. Stale / degraded demo (~2 min, optional)

Easiest way to show the failure path:

```bash
# In another terminal:
sudo pfctl -e 2>/dev/null   # or just disconnect WiFi
```

Wait 15s for the next autorefresh tick. The banner appears: **"⚠️ At least one upstream feed is stale or degraded"** — and individual feed-health rows show `🟠 (degraded)`. The app is still rendering data because of the soft cache (F-006) — last-good `FeedMessage` is held in memory.

Re-enable network; the next tick shows ✅ again.

If you want to demonstrate the **hard-snapshot tier** (#13): kill the Streamlit process while the network is still down, then restart it. The soft cache is gone, so the fetcher falls back to the most recent committed `.pb` in `examples/`. The feed-health panel labels it `from snapshot`.

### 4. Code tour — talking points (~5 min)

Open the source in the editor. Hit the four things from [docs/RECRUITER-NOTES.md](docs/RECRUITER-NOTES.md):

1. **Partial-update propagation** — [gtfs_dleung/parser/tripupdates.py](gtfs_dleung/parser/tripupdates.py) `_arrivals_for_scheduled_trip`. The `current_delay_seconds` accumulator walks `static_stop_times` in `stop_sequence` order; an explicit RT update sets it, and downstream stops inherit until the next explicit update appears.
2. **Polite-consumer / dual rate limit** — point at [gtfs_dleung/fetcher/rate_limit.py](gtfs_dleung/fetcher/rate_limit.py) (outbound — protects MBTA's CDN from us) and [gtfs_dleung/security/rate_limit.py](gtfs_dleung/security/rate_limit.py) (inbound — protects us from a misbehaving session). Different threats; different modules.
3. **Three-tier data path** — live fetch (F-002) → soft cache (F-006) → hard snapshot (#13). Show [gtfs_dleung/fetcher/health.py](gtfs_dleung/fetcher/health.py) `fetch()` — the try/except, the `is_degraded` set, the snapshot-loader fallback.
4. **The conventions doc** — [docs/AI-COLLABORATION-CONVENTIONS.md](docs/AI-COLLABORATION-CONVENTIONS.md). Mention: every PR followed §4a–§4e. Same shape across 14 PRs. This is *how* the work landed at this pace, not *what* the work was.

### 5. What I'd build next (~2 min)

The [open issues](https://github.com/dcltdw/gtfs-dleung/issues?q=is%3Aopen+label%3Apost-demo) are the post-demo backlog — 27 tickets, all sized to one PR each. The high-leverage ones to call out:

- **#15 — Live vehicle map** (folium + VehiclePositions). The parser is already shipping typed rows; it's mostly UI work.
- **#26 — DuckDB persistence of RT snapshots** + **#27 / #34 — historical delay analytics**. Unlocks the "what's typical at 8 a.m.?" question riders actually ask.
- **#33 — Prometheus `/metrics`**. The metrics dict in `HealthTrackedFetcher.get_metrics()` is already the right shape; the exporter is a thin layer.
- **#49 — Nightly live-feed CI** (`@pytest.mark.live`). The marker is already established in #11; the workflow file is straightforward.
- **#35–#38 — Real auth** (DB-backed users, OAuth, MFA, audit log). The current auth surface is intentionally a single seeded user with the bcrypt hash committed; production needs all four.

The [docs/UPGRADE-PATH.md](docs/UPGRADE-PATH.md) doc walks through the bigger architecture shift: adopting MBTA's V3 REST API when the project outgrows the spike. Additive — every stage replaces a specific surface without rewriting the parsers.

## Contingencies

| If | Then |
|---|---|
| Live feeds fail mid-call | The soft cache (F-006) keeps the last good data showing. The banner explains. If both cache **and** live fail (cold start during outage), `examples/*.pb` kicks in — the panel labels them `from snapshot`. |
| Login button doesn't work | Reload the page (Streamlit's cookie state can drift on hot edits). Worst case, `git stash && just demo` to restart. |
| Inbound rate-limit fires (rapid manual refresh) | The throttle banner appears; the page keeps showing cached data. Wait 60s for the window to slide. |
| Map / vehicle questions | "That's post-demo #15 — the typed parser is shipping vehicle rows; the rendering layer is what's deferred." |
| "Why no database?" | [docs/adr/0002-no-database.md](docs/adr/0002-no-database.md). Covers in-memory state vs persistence; explicit on what's deferred. |
| "Why Streamlit, not Flask?" | [docs/adr/0001-streamlit-not-flask.md](docs/adr/0001-streamlit-not-flask.md). Trade-off summary fits in two lines. |
| "Why GTFS-RT directly, not V3?" | [docs/adr/0003-strict-gtfs-rt.md](docs/adr/0003-strict-gtfs-rt.md) — direct relevance to the role; the upgrade path is in [docs/UPGRADE-PATH.md](docs/UPGRADE-PATH.md). |

## After the call

- Update [RETROSPECTIVE.md](RETROSPECTIVE.md) with anything the conversation surfaced.
- Rotate the demo credential per [docs/SECURITY.md](docs/SECURITY.md) (regen bcrypt hash + cookie key, update `.env`).
