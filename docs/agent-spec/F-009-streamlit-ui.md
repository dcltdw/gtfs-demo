---
id: F-009
title: Streamlit UI — login + arrivals + alerts + feed health
type: functional
status: in-progress
issue: 11
pr: null
depends_on: [F-001, F-002, F-003, F-005, F-006, F-007, F-008]
owner: dcltdw
last_updated: 2026-05-11
---

## Summary

Wire every backend piece — auth (F-007), static loader (F-001), realtime fetcher + health (F-002 / F-006), parsers (F-003 / F-005), inbound rate limiter (F-008) — into a single Streamlit page. The page presents three sections after login: the arrivals board (Davis + Ball Square side-by-side), an active service-alerts panel, and a feed-health panel. Auto-refresh every 15 seconds; inbound rate-limit gate sits in front of the refresh handler so a runaway session falls back to its previously-rendered data without hammering MBTA's CDN.

This spec replaces what the originating issue called `F-005-streamlit-ui`. The `F-005` slot is taken by `ServiceAlerts`; the correct slot for the Streamlit UI is `F-009`, matching `REQUIREMENTS.md`. Same numbering-deviation pattern as F-002 / F-003 / F-006 / F-007 / F-008.

## Inputs

- All upstream settings from F-001 through F-008. The Streamlit page is a thin composition layer; no new env variables.
- The static GTFS bundle at process-start (cached by `@st.cache_resource`; first load is ~200ms).
- The three GTFS-RT feeds, refreshed every 15 seconds (driven by `streamlit-autorefresh`).

## Properties

1. **Login gate.** The page renders the auth widget first; the data sections are only reachable after `st.session_state["authentication_status"]` is `True`. Implemented via `streamlit_authenticator.Authenticate(...)` constructed from F-007's `build_authenticator_config`.
2. **Sidebar logout.** The authenticated user sees their display name in the sidebar plus a logout button (provided by `streamlit-authenticator`). A `Refresh now` button lives there too as a fallback when the user wants to bypass the 15s timer.
3. **Two-column arrivals board, each station split by direction.** `next_n_arrivals` (F-003) picks five upcoming arrivals at `place-davis` and `place-balsq`. Each station column renders **two subsections** — Inbound (toward downtown) first, then Outbound (away from downtown) — with the direction label **center-aligned** in the column (the only `unsafe_allow_html=True` surface in the page; the label text is a constant `Inbound` / `Outbound` / `Unknown direction`). Each subsection shows the first **3 arrivals inline**; any remaining arrivals (4th and 5th, up to whatever `next_n_arrivals` returns) sit inside a single collapsed `st.expander` labelled `More arrivals (N)`, omitted entirely when ≤3 are available. Per-row, the renderer shows scheduled time, predicted time, color-coded delay magnitude (`green` ≤ 30 s, `yellow`/orange ≤ 120 s, `red` > 120 s, `neutral` if unknown) — **both the leading dot emoji and the delay text** are wrapped in the same color (`:green[…]` / `:orange[…]` / `:red[…]`) so the visual signal isn't reliant on a single dot. The trip's headsign (e.g. `toward Ashmont`) is rendered **only when informative for the row's (stop_id, direction_id)** — for the demo's two stations that means Davis inbound only (Red Line splits Ashmont/Braintree south of JFK); Davis outbound (single Alewife terminus) and both Ball Sq directions (Green-E single terminus each way) suppress the suffix. Governed by `gtfs_demo.presenter.formatters.show_headsign`, which defaults to False so a station/direction pair without an explicit entry is silent rather than noisy. The `**Route** —` prefix is intentionally **not** rendered: every row in a column shares a single route (Davis = Red, Ball Sq = Green-E), so suppressing it lets the times line up across rows. Unusual `schedule_relationship` values render badges — `CANCELED` strikes through, `ADDED` is purple, `SKIPPED`/`UNSCHEDULED` are gray.
4. **Service-alerts panel.** Each in-scope, currently-active alert renders as a Streamlit `expander` titled with the alert's header + a short effect label. Expanded view shows the description, cause, effect, and the active-period window.
5. **Feed-health panel.** One row per feed (TripUpdates, ServiceAlerts; VehiclePositions when fetched). Each row shows an icon — ✅ fresh, 🟡 stale, 🟠 degraded, 🔴 both, ⚪ no data yet — plus the feed's age and any flag labels (`stale`, `degraded`).
6. **Auto-refresh every 15 s.** `streamlit_autorefresh.st_autorefresh(interval=15_000)` triggers a rerun. The fetcher path is gated by the inbound RL so a single session can't dominate. The component's outer wrapper (`.st-key-data-refresh`) — and the equivalent wrapper around the cookie manager (`.st-key-init`, used internally by streamlit-authenticator) — is hidden via a one-shot `<style>` block at the top of `main()`. Both wrap hidden iframes that render no visible UI; without the hide, each takes a block-level slice of vertical space between the title and the data panels.
7. **Stale/degraded banner.** When any feed reports `is_stale=True` or `is_degraded=True`, a top-of-page warning fires telling the user which panel to consult. Built on `should_show_stale_banner` (F-008's siblings module).

   **Scope header banner.** Above the stale/degraded warning, a persistent `st.info` block names the demo's scope (Davis + Ball Sq arrivals, Park St ↔ Alewife and Park St ↔ Medford/Tufts alert corridors) and prints the one-line delay color legend. Rendered by `_render_scope_header` at the top of `_render_data_app`.
8. **Inbound RL wrapper.** Before every refresh-driven fetch, `SessionRateLimiter.acquire(session_id)` is called. On `False`, the page shows a throttle banner and reuses the previous cycle's `arrivals` + `alerts` from `st.session_state` — no new fetch is issued. On the very first cycle this displays empty panels with a hint that more data is on the way.
9. **Pure helpers stay pure.** Everything except `gtfs_demo.app` itself is unit-testable without Streamlit. `gtfs_demo.presenter.formatters` carries the per-row display logic; the corresponding test file (`tests/test_formatters.py`, 41 tests) is the bulk of this PR's verification.
10. **`@pytest.mark.live` marker established.** The first opt-in test (`tests/test_app_smoke.py::test_streamlit_app_starts_cleanly`) spawns the real `streamlit run` subprocess for ~8 s and asserts no startup crash. The marker is registered in `pyproject.toml`; the PR CI's `test` job excludes it via `pytest -m 'not live'`. The nightly job from #49 picks these up.

## Outputs

- `gtfs_demo/app.py` — Streamlit entrypoint. Run with `uv run streamlit run gtfs_demo/app.py` (or `just demo`).
- `gtfs_demo/presenter/formatters.py` — pure display helpers (`format_arrival_row`, `format_alert_row`, `format_feed_age`, `delay_color_class`, `schedule_relationship_badge`, `feed_health_icon`, `should_show_stale_banner`).

## Edge cases

- **First load with empty `st.session_state`**: the inbound RL allows the request, fetches normally, and stores `last_arrivals` / `last_alerts` for the next throttle. Rate-limited on the very first call would render empty panels.
- **`fetch_static_feed` fails on cold start** (e.g. no network on first run): the `@st.cache_resource` call raises, Streamlit shows the exception. Reload after the network is back. Could be hardened post-demo with a friendlier error UI.
- **TripUpdates fetch fails with no cache**: `FeedFetchError` propagates from `HealthTrackedFetcher.fetch` (F-006); the page catches and renders an `st.error` banner. Subsequent successful fetches recover automatically.
- **A trip running through Park St → Davis but only with stops downtown**: `next_n_arrivals` filters by `stop_id == place-davis` and `predicted_at >= now`, so we don't show arrivals that don't actually reach the target stop.
- **`schedule_relationship=CANCELED`**: returned by the parser but excluded from the default board view by `next_n_arrivals` (F-003); CANCELED trips surface only in the alerts panel via the service alert that announced them.
- **Long alert description text**: Streamlit's `st.expander` handles arbitrary length gracefully; no truncation.
- **Authentication cookie expires mid-session**: `streamlit-authenticator` flips `authentication_status` to `None`; the page re-renders the login widget.

## Out of scope

- **Live vehicle map** — post-demo #15.
- **Real user accounts, OAuth, MFA, audit log** — post-demo #35–#38 (the auth surface from F-007 already documents these).
- **Per-IP rate limiting** — post-demo #40.
- **Streamlit page deploy to Streamlit Cloud** — post-demo #17. The spike runs the app locally for the screen-share.
- **WebSocket push** — post-demo #29.
- **Delay distribution + schedule-vs-actual charts** — post-demo #27 / #34.
- **Streamlit fragment-level partial reruns** — not used; the whole page reruns on every 15 s tick. Cheap at this scale.

## Verification

**Unit (in PR CI):**

- `tests/test_formatters.py` — 41 tests covering `delay_color_class` thresholds, badge mapping, arrival-row formatting, feed-age formatting (incl. `>1h`), feed-health icon truth table, alert-row formatting (with + without active_period), and the stale-banner aggregator (dict + list inputs).
- `tests/test_app_smoke.py::test_app_imports` — the entrypoint imports cleanly without invoking `main()`.
- `tests/test_app_smoke.py::test_main_function_exists_and_callable` — `main` is a callable, matching what `streamlit run` expects.

**Live (excluded from PR CI; runs nightly via #49 once filed):**

- `tests/test_app_smoke.py::test_streamlit_app_starts_cleanly` — `@pytest.mark.live`. Spawns `streamlit run gtfs_demo/app.py --server.headless=true` for ~8 s; asserts no startup crash by checking for `Traceback` in captured output.

**Manual (the demo's golden path):**

1. `just install`
2. `cp .env.example .env` (or rely on defaults)
3. `just demo`
4. Open the URL Streamlit prints; log in with `demo` / `gtfs-demo-2026`.
5. Verify the three panels render; watch the timestamps tick every 15 s.
6. Click `Refresh now` — banner does *not* appear (under the limit).
7. Rapidly refresh ~30 times — throttle banner appears; the page keeps rendering the last good data.

## Open questions

_None._
