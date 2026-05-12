"""Streamlit demo entrypoint: login → arrivals + alerts + feed-health panels.

Run with::

    uv run streamlit run gtfs_dleung/app.py

The module is the **only** spot in the codebase that imports ``streamlit`` and
``streamlit_authenticator``. Every helper this calls into is unit-testable
without spinning up Streamlit:

- Auth checks: :mod:`gtfs_dleung.auth`
- Static feed: :mod:`gtfs_dleung.parser.static` (+ :mod:`gtfs_dleung.fetcher.static`)
- Realtime fetches: :mod:`gtfs_dleung.fetcher.health` (which wraps F-002's
  ``fetch_feed`` with the F-006 health tracker)
- Realtime parses: :mod:`gtfs_dleung.parser.{tripupdates, alerts, vehicles}`
- Per-stop arrival picker: :mod:`gtfs_dleung.presenter.arrivals`
- Display formatting: :mod:`gtfs_dleung.presenter.formatters`
- Inbound rate limit: :mod:`gtfs_dleung.security.rate_limit`

Auto-refresh uses ``streamlit-autorefresh`` (15s by default). The inbound rate
limiter sits *before* the refresh handler: if a session blows past its budget,
we render the previous cycle's data (cached in ``st.session_state``) and show a
banner — no fetch is issued.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import streamlit as st
import streamlit_authenticator as stauth
from streamlit_autorefresh import st_autorefresh

from gtfs_dleung.auth import build_authenticator_config
from gtfs_dleung.config import Settings, get_settings
from gtfs_dleung.feeds import SERVICE_ALERTS_URL, TRIP_UPDATES_URL
from gtfs_dleung.fetcher.health import HealthTrackedFetcher
from gtfs_dleung.fetcher.realtime import FeedFetchError
from gtfs_dleung.fetcher.static import fetch_static_feed
from gtfs_dleung.models.alert import ServiceAlert
from gtfs_dleung.models.arrival import Arrival
from gtfs_dleung.models.feed_health import FeedHealth, FeedType
from gtfs_dleung.parser.alerts import parse as parse_alerts
from gtfs_dleung.parser.static import filter_to_scope, load_feed_from_dir
from gtfs_dleung.parser.tripupdates import parse as parse_tripupdates
from gtfs_dleung.presenter.arrivals import next_n_arrivals
from gtfs_dleung.presenter.formatters import (
    direction_label,
    feed_health_icon,
    format_alert_row,
    format_arrival_row,
    format_feed_age,
    should_show_stale_banner,
)
from gtfs_dleung.security.rate_limit import SessionRateLimiter

# Stops the arrivals board renders. Must match scope (#3); change here if the
# corridor ever extends.
_DAVIS = "place-davis"
_BALL_SQUARE = "place-balsq"
_BOARD_STOPS: tuple[tuple[str, str], ...] = (
    ("Davis", _DAVIS),
    ("Ball Square", _BALL_SQUARE),
)

_REFRESH_INTERVAL_MS = 15_000


# ---- cached resources (one instance per process) ------------------------------


@st.cache_resource
def _settings() -> Settings:
    return get_settings()


@st.cache_resource
def _static_feed() -> Any:
    """Load + scope-filter the static GTFS bundle. Heavy on cold start; cached."""
    feed_dir = fetch_static_feed()
    return filter_to_scope(load_feed_from_dir(feed_dir))


@st.cache_resource
def _health_fetcher() -> HealthTrackedFetcher:
    return HealthTrackedFetcher(settings=_settings())


@st.cache_resource
def _rate_limiter() -> SessionRateLimiter:
    s = _settings()
    return SessionRateLimiter(
        limit=s.gtfs_inbound_limit_per_min,
        window_s=s.gtfs_inbound_window_s,
        idle_evict_s=s.gtfs_inbound_idle_evict_s,
    )


# ---- main app ------------------------------------------------------------------


def main() -> None:
    """Page entrypoint. Streamlit calls this every rerun."""
    st.set_page_config(page_title="gtfs-dleung", page_icon="🚇", layout="wide")
    st.title("🚇 MBTA GTFS-RT")
    st.markdown(
        "_Dave lives between Davis Sq and Ball Sq, and wants to know when trains "
        "are arriving at those stations._"
    )

    config = build_authenticator_config(_settings())
    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )

    # First pass: validate the auth cookie without rendering the form. After the
    # initial login, the cookie keeps the session alive across reruns; calling
    # `login(location="main")` again would render a small "Welcome X" block
    # under the title and waste vertical space above the data panels.
    status = st.session_state.get("authentication_status")
    if status is not True:
        try:
            authenticator.login(location="main")
        except Exception as exc:  # pragma: no cover - streamlit-authenticator may raise on bad config
            st.error(f"Login error: {exc}")
            return
        status = st.session_state.get("authentication_status")

    if status is False:
        st.error("Username or password is incorrect.")
        return
    if status is None:
        st.info("Please log in to view live data.")
        return

    with st.sidebar:
        st.caption(f"Signed in as **{st.session_state.get('name')}**")
        authenticator.logout(location="sidebar")
        st.divider()
        st.caption(f"Auto-refresh every {_REFRESH_INTERVAL_MS // 1000}s.")
        if st.button("Refresh now"):
            st.rerun()

    st_autorefresh(interval=_REFRESH_INTERVAL_MS, key="data-refresh")
    _render_data_app()


def _render_data_app() -> None:
    """Render the three panels (arrivals / alerts / feed health) for an authenticated user."""
    session_id = _stable_session_id()
    limiter = _rate_limiter()

    allowed = limiter.acquire(session_id)
    if not allowed:
        st.warning(
            "⚠️ Inbound rate limit reached for this session — showing the last successful "
            "refresh. The page will resume normal refreshes in under a minute."
        )

    arrivals, alerts, healths = _refresh_data(allowed=allowed)

    _render_scope_header()

    if should_show_stale_banner(healths):
        st.warning(
            "⚠️ At least one upstream feed is stale or degraded — see the **Feed health** "
            "panel below for which one."
        )

    _render_arrivals_board(arrivals)
    st.divider()
    _render_alerts_panel(alerts)
    st.divider()
    _render_feed_health_panel(healths)


def _refresh_data(
    *, allowed: bool
) -> tuple[list[Arrival], list[ServiceAlert], dict[FeedType, FeedHealth]]:
    """Fetch + parse all three RT feeds; cache the latest result on ``st.session_state``.

    When ``allowed=False`` (inbound rate-limited), skip the fetches and return
    the previously-cached values. First-load rate-limit returns empty lists.
    """
    static = _static_feed()
    fetcher = _health_fetcher()

    if not allowed:
        return (
            st.session_state.get("last_arrivals", []),
            st.session_state.get("last_alerts", []),
            fetcher.get_health(),
        )

    now = datetime.now(tz=UTC)

    try:
        trip_msg, _ = fetcher.fetch(TRIP_UPDATES_URL)
        arrivals = parse_tripupdates(trip_msg, static)
    except FeedFetchError as exc:
        st.error(f"TripUpdates fetch failed and no cache is available yet: {exc}")
        arrivals = []

    try:
        alerts_msg, _ = fetcher.fetch(SERVICE_ALERTS_URL)
        alerts = parse_alerts(alerts_msg, now=now)
    except FeedFetchError as exc:
        st.error(f"Alerts fetch failed and no cache is available yet: {exc}")
        alerts = []

    st.session_state["last_arrivals"] = arrivals
    st.session_state["last_alerts"] = alerts
    return arrivals, alerts, fetcher.get_health()


# ---- panels --------------------------------------------------------------------


def _render_scope_header() -> None:
    """Top-of-page banner explaining the demo's scope + the delay-color legend.

    Sits above the stale/degraded warning so a first-time visitor reads it before
    anything else. Phrasing mirrors ``DEMO.md``'s scope talking-point.
    """
    st.info(
        "**Scope** — Arrivals at **Davis** (Red Line) and **Ball Square** (Green-E), "
        "both directions. Service alerts cover the full Park St ↔ Alewife and "
        "Park St ↔ Medford/Tufts corridors so terminus-only alerts still surface.\n\n"
        "**Delay legend** — 🟢 ≤30s on time · 🟠 ≤120s slightly off · "
        "🔴 >120s significantly off (magnitude — early arrivals use the same bands)."
    )


def _render_arrivals_board(arrivals: list[Arrival]) -> None:
    st.subheader("Arrivals")
    columns = st.columns(len(_BOARD_STOPS))
    for col, (label, stop_id) in zip(columns, _BOARD_STOPS, strict=True):
        with col:
            st.markdown(f"**{label}** (`{stop_id}`)")
            # Two subsections per station: Inbound (direction_id=0) and Outbound
            # (direction_id=1) — see `direction_label` for the convention. Both
            # of the demo's stations are north of Park St, so 0 = south = inbound.
            _render_direction_subsection(arrivals, stop_id, direction_id=0)
            _render_direction_subsection(arrivals, stop_id, direction_id=1)


# How many arrivals each direction subsection shows inline before the rest collapse.
# A rider boarding "soon" mostly cares about the next two or three; rows 4+ push
# the second station / alerts panel below the fold. Anything past this goes into
# a single st.expander so the data isn't lost — just out of the way.
#
# NB: do NOT change this to a bare-string docstring (`"""..."""`). Streamlit's
# "magic" feature renders bare top-level expressions as markdown, which would
# dump this text at the top of the page.
_VISIBLE_ARRIVALS = 3


def _render_direction_subsection(
    arrivals: list[Arrival], stop_id: str, *, direction_id: int
) -> None:
    """Render one direction's upcoming arrivals at a station.

    The first ``_VISIBLE_ARRIVALS`` rows render inline; any remainder lives
    inside a single collapsed ``st.expander`` labelled with the hidden count.
    """
    # Streamlit's pure-markdown surface has no center alignment, so a one-line
    # HTML wrapper is the lightest fix. The text is constant (Inbound / Outbound /
    # Unknown), so the unsafe_allow_html surface area is bounded.
    st.markdown(
        f"<div style='text-align: center'><em>{direction_label(direction_id)}</em></div>",
        unsafe_allow_html=True,
    )
    picks = next_n_arrivals(arrivals, stop_id, n=5, direction_id=direction_id)
    if not picks:
        st.caption("No upcoming arrivals in this direction. (Waiting for refresh.)")
        return

    visible = picks[:_VISIBLE_ARRIVALS]
    hidden = picks[_VISIBLE_ARRIVALS:]

    for arr in visible:
        _render_arrival_row(format_arrival_row(arr))

    if hidden:
        with st.expander(f"More arrivals ({len(hidden)})", expanded=False):
            for arr in hidden:
                _render_arrival_row(format_arrival_row(arr))


def _render_arrival_row(row: dict[str, str | None]) -> None:
    color = row["color"]
    badge = row["badge"]
    badge_md = ""
    if badge == "CANCELED":
        badge_md = " ~~CANCELED~~"
    elif badge == "ADDED":
        badge_md = " :violet[ADDED]"
    elif badge == "SKIPPED":
        badge_md = " :gray[SKIPPED]"
    elif badge == "UNSCHED":
        badge_md = " :gray[UNSCHEDULED]"

    text_color = _color_to_emoji(color)
    delay_md = f":{text_color}: :{text_color}[{row['delay']}]"
    headsign_md = f" — _toward {row['headsign']}_" if row.get("headsign") else ""
    # No leading `**Route** —` prefix: every row in a given column is the same
    # route (Davis = Red, Ball Sq = Green-E), so the times line up across rows.
    st.markdown(
        f"sched **{row['scheduled'] or '?'}** → "
        f"pred **{row['predicted'] or '?'}** {delay_md}{badge_md}{headsign_md}"
    )


def _color_to_emoji(color: str | None) -> str:
    return {
        "green": "green",
        "yellow": "orange",
        "red": "red",
        "neutral": "gray",
    }.get(color or "neutral", "gray")


def _render_alerts_panel(alerts: list[ServiceAlert]) -> None:
    st.subheader("Active service alerts")
    if not alerts:
        st.caption("No active in-scope alerts right now.")
        return
    for alert in alerts:
        row = format_alert_row(alert)
        with st.expander(f"⚠️ {row['header']} — {row['effect_label']}"):
            if row["description"]:
                st.write(row["description"])
            st.caption(
                f"Cause: {row['cause']} · Effect: {row['effect']} · "
                f"Window: {row['starts'] or '—'} → {row['ends'] or 'open-ended'}"
            )


def _render_feed_health_panel(healths: dict[FeedType, FeedHealth]) -> None:
    st.subheader("Feed health")
    if not healths:
        st.caption("No feed fetched yet.")
        return
    for ft, health in healths.items():
        icon = feed_health_icon(health)
        age = format_feed_age(health.age_seconds)
        label = ft.value.replace("_", " ").title()
        flags: list[str] = []
        if health.is_snapshot:
            # When serving from the committed snapshot, that's the most useful label —
            # supersedes the "stale" / "degraded" pair (both of which are implied).
            flags.append("from snapshot")
        else:
            if health.is_stale:
                flags.append("stale")
            if health.is_degraded:
                flags.append("degraded")
        flag_str = f" · ({', '.join(flags)})" if flags else ""
        st.markdown(f"{icon} **{label}** — age **{age}**{flag_str}")


# ---- helpers -------------------------------------------------------------------


def _stable_session_id() -> str:
    """Get-or-create a stable session ID stored on ``st.session_state``.

    Streamlit's runtime provides its own per-session ID, but that API isn't
    stable across versions; this keeps the limiter decoupled.
    """
    sid = st.session_state.get("rl_session_id")
    if sid is None:
        sid = str(uuid.uuid4())
        st.session_state["rl_session_id"] = sid
    return str(sid)


if __name__ == "__main__":
    main()
