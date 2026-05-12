"""Tests for ``gtfs_demo.presenter.formatters`` — pure-function display helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from gtfs_demo.models.alert import (
    ActivePeriod,
    Cause,
    Effect,
    InformedEntity,
    ServiceAlert,
)
from gtfs_demo.models.arrival import Arrival, ScheduleRelationship
from gtfs_demo.models.feed_health import FeedHealth, FeedType
from gtfs_demo.presenter.formatters import (
    delay_color_class,
    direction_label,
    feed_health_icon,
    format_alert_row,
    format_arrival_markdown,
    format_arrival_row,
    format_feed_age,
    schedule_relationship_badge,
    should_show_stale_banner,
    show_headsign,
)

TZ = ZoneInfo("America/New_York")


def _arr(
    *,
    delay: int | None = 0,
    sr: ScheduleRelationship = ScheduleRelationship.SCHEDULED,
    is_added: bool = False,
) -> Arrival:
    return Arrival(
        stop_id="place-davis",
        stop_name="Davis",
        route_id="Red",
        trip_id="T1",
        scheduled_at=datetime(2026, 5, 11, 8, 0, tzinfo=TZ),
        predicted_at=datetime(2026, 5, 11, 8, 0, tzinfo=TZ),
        delay_seconds=delay,
        schedule_relationship=sr,
        is_added=is_added,
    )


# ---- delay_color_class --------------------------------------------------------


@pytest.mark.parametrize(
    "delay,expected",
    [
        (None, "neutral"),
        (0, "green"),
        (15, "green"),
        (30, "green"),
        (31, "yellow"),
        (90, "yellow"),
        (120, "yellow"),
        (121, "red"),
        (300, "red"),
        (-15, "green"),  # early counts the same as late
        (-200, "red"),
    ],
)
def test_delay_color_class(delay: int | None, expected: str) -> None:
    assert delay_color_class(delay) == expected


# ---- schedule_relationship_badge ---------------------------------------------


def test_schedule_relationship_badge_returns_none_for_scheduled() -> None:
    assert schedule_relationship_badge(ScheduleRelationship.SCHEDULED) is None


# ---- direction_label ---------------------------------------------------------


@pytest.mark.parametrize(
    "direction_id,expected",
    [
        (0, "Inbound"),
        (1, "Outbound"),
        (None, "Unknown direction"),
        (2, "Unknown direction"),
    ],
)
def test_direction_label(direction_id: int | None, expected: str) -> None:
    assert direction_label(direction_id) == expected


# ---- show_headsign -----------------------------------------------------------


def test_show_headsign_davis_inbound_returns_true() -> None:
    """Red Line south of Davis splits Ashmont/Braintree — headsign is informative."""
    assert show_headsign("place-davis", 0) is True


def test_show_headsign_davis_outbound_returns_false() -> None:
    """Every northbound Red Line train at Davis terminates at Alewife — headsign is redundant."""
    assert show_headsign("place-davis", 1) is False


def test_show_headsign_balsq_either_direction_returns_false() -> None:
    """Green-E from Ball Sq has a single terminus each direction — headsign is redundant both ways."""
    assert show_headsign("place-balsq", 0) is False
    assert show_headsign("place-balsq", 1) is False


def test_show_headsign_unknown_stop_or_direction_returns_false() -> None:
    """Default-False semantics: anything not explicitly in the informative-pairs set is suppressed."""
    assert show_headsign("place-unknown", 0) is False
    assert show_headsign("place-davis", None) is False
    assert show_headsign("place-davis", 99) is False


@pytest.mark.parametrize(
    "sr,expected",
    [
        (ScheduleRelationship.ADDED, "ADDED"),
        (ScheduleRelationship.CANCELED, "CANCELED"),
        (ScheduleRelationship.SKIPPED, "SKIPPED"),
        (ScheduleRelationship.UNSCHEDULED, "UNSCHED"),
    ],
)
def test_schedule_relationship_badge_unusual_states(
    sr: ScheduleRelationship, expected: str
) -> None:
    assert schedule_relationship_badge(sr) == expected


# ---- format_arrival_row ------------------------------------------------------


def test_format_arrival_row_basic() -> None:
    row = format_arrival_row(_arr(delay=60))
    assert row["route"] == "Red"
    assert row["stop"] == "Davis"
    assert row["scheduled"] is not None
    assert row["predicted"] is not None
    assert row["delay"] == "+1m 0s"
    assert row["color"] == "yellow"
    assert row["badge"] is None
    assert row["trip_id"] == "T1"
    assert row["headsign"] is None  # default fixture has no headsign set


def test_format_arrival_row_carries_headsign() -> None:
    """The Arrival's ``trip_headsign`` propagates to the display dict."""
    arrival = _arr(delay=0)
    # Pydantic model is frozen — construct a copy via model_copy.
    arrival_with_headsign = arrival.model_copy(update={"trip_headsign": "Alewife"})
    row = format_arrival_row(arrival_with_headsign)
    assert row["headsign"] == "Alewife"


def test_format_arrival_row_canceled_carries_badge() -> None:
    row = format_arrival_row(_arr(sr=ScheduleRelationship.CANCELED))
    assert row["badge"] == "CANCELED"


def test_format_arrival_row_missing_delay() -> None:
    row = format_arrival_row(_arr(delay=None))
    assert row["delay"] == "—"
    assert row["color"] == "neutral"


def test_format_arrival_row_negative_delay_formatted_with_minus() -> None:
    """Use a Unicode minus to make 'early' easy to read at a glance."""
    row = format_arrival_row(_arr(delay=-45))
    delay = row["delay"]
    assert delay is not None
    assert delay.startswith("−")  # noqa: RUF001 — U+2212 MINUS SIGN, not ASCII hyphen


# ---- format_arrival_markdown -------------------------------------------------


def _row(
    *,
    scheduled: str | None = "8:00:00 AM",
    predicted: str | None = "8:01:00 AM",
    delay: str | None = "+1m 0s",
    color: str | None = "yellow",
    badge: str | None = None,
    headsign: str | None = None,
) -> dict[str, str | None]:
    return {
        "scheduled": scheduled,
        "predicted": predicted,
        "delay": delay,
        "color": color,
        "badge": badge,
        "headsign": headsign,
    }


def test_format_arrival_markdown_drops_leading_color_emoji() -> None:
    """The redundant ``:color:`` emoji prefix is dropped — only the colored delay text remains."""
    md = format_arrival_markdown(_row(color="red", delay="+5m 37s"), show_headsign=False)
    assert ":red[+5m 37s]" in md
    # The two-token form ``:red: :red[...]`` must NOT appear.
    assert ":red: :red[" not in md
    # No bare leading colored emoji of any flavor.
    for color_name in ("red", "orange", "green", "gray"):
        assert f":{color_name}: " not in md


@pytest.mark.parametrize(
    "color,expected_token",
    [
        ("green", ":green[+1m 0s]"),
        ("yellow", ":orange[+1m 0s]"),  # yellow → orange in the Streamlit color palette
        ("red", ":red[+1m 0s]"),
        ("neutral", ":gray[+1m 0s]"),
        (None, ":gray[+1m 0s]"),  # missing color falls back to gray
    ],
)
def test_format_arrival_markdown_colors_delay_text(color: str | None, expected_token: str) -> None:
    md = format_arrival_markdown(_row(color=color), show_headsign=False)
    assert expected_token in md


@pytest.mark.parametrize(
    "badge,expected",
    [
        ("CANCELED", "~~CANCELED~~"),
        ("ADDED", ":violet[ADDED]"),
        ("SKIPPED", ":gray[SKIPPED]"),
        ("UNSCHED", ":gray[UNSCHEDULED]"),
        (None, ""),
    ],
)
def test_format_arrival_markdown_renders_badge(badge: str | None, expected: str) -> None:
    md = format_arrival_markdown(_row(badge=badge), show_headsign=False)
    if expected:
        assert expected in md
    else:
        # No badge → none of the badge tokens should appear.
        for token in ("CANCELED", "ADDED", "SKIPPED", "UNSCHEDULED"):
            assert token not in md


def test_format_arrival_markdown_added_uses_em_dash_for_missing_delay() -> None:
    """ADDED trips have no scheduled delay; the em-dash from ``_fmt_delay(None)`` renders gray."""
    md = format_arrival_markdown(
        _row(scheduled=None, delay="—", color="neutral", badge="ADDED"),
        show_headsign=False,
    )
    assert "sched **?**" in md
    assert ":gray[—]" in md
    assert ":violet[ADDED]" in md
    # Critically: no leading gray emoji before the em-dash.
    assert ":gray: " not in md


def test_format_arrival_markdown_includes_headsign_when_flag_true() -> None:
    md = format_arrival_markdown(_row(headsign="Braintree"), show_headsign=True)
    assert "_toward Braintree_" in md


def test_format_arrival_markdown_omits_headsign_when_flag_false() -> None:
    md = format_arrival_markdown(_row(headsign="Braintree"), show_headsign=False)
    assert "Braintree" not in md


def test_format_arrival_markdown_omits_headsign_when_value_missing() -> None:
    md = format_arrival_markdown(_row(headsign=None), show_headsign=True)
    assert "_toward" not in md


def test_format_arrival_markdown_full_shape() -> None:
    """End-to-end rendering matches the documented row format (no leading emoji)."""
    md = format_arrival_markdown(
        _row(
            scheduled="11:50:00 PM",
            predicted="11:55:37 PM",
            delay="+5m 37s",
            color="red",
            headsign="Braintree",
        ),
        show_headsign=True,
    )
    assert md == ("sched **11:50:00 PM** → pred **11:55:37 PM** :red[+5m 37s] — _toward Braintree_")


# ---- format_feed_age ---------------------------------------------------------


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (None, "unknown"),
        (0, "0s"),
        (8.2, "8s"),
        (59, "59s"),
        (60, "1m 0s"),
        (125, "2m 5s"),
        (3599, "59m 59s"),
        (3600, "1h 0m"),
        (3725, "1h 2m"),
        (-3, "0s"),  # never negative
    ],
)
def test_format_feed_age(seconds: float | None, expected: str) -> None:
    assert format_feed_age(seconds) == expected


# ---- feed_health_icon --------------------------------------------------------


def _health(
    *, age: float | None, is_stale: bool, is_degraded: bool, last_success: datetime | None = None
) -> FeedHealth:
    return FeedHealth(
        feed_type=FeedType.TRIP_UPDATES,
        feed_url="https://example.invalid/x.pb",
        age_seconds=age,
        is_stale=is_stale,
        last_success_at=last_success,
        is_degraded=is_degraded,
    )


def test_feed_health_icon_fresh() -> None:
    assert feed_health_icon(_health(age=5, is_stale=False, is_degraded=False)) == "✅"


def test_feed_health_icon_stale_only() -> None:
    assert feed_health_icon(_health(age=120, is_stale=True, is_degraded=False)) == "🟡"


def test_feed_health_icon_degraded_only() -> None:
    assert feed_health_icon(_health(age=5, is_stale=False, is_degraded=True)) == "🟠"


def test_feed_health_icon_stale_and_degraded() -> None:
    assert feed_health_icon(_health(age=120, is_stale=True, is_degraded=True)) == "🔴"


def test_feed_health_icon_no_data_yet() -> None:
    assert feed_health_icon(_health(age=None, is_stale=False, is_degraded=False)) == "⚪"


# ---- format_alert_row --------------------------------------------------------


def test_format_alert_row_with_full_data() -> None:
    alert = ServiceAlert(
        header_text="Red Line: significant delays",
        description_text="Disabled train at Park Street.",
        cause=Cause.TECHNICAL_PROBLEM,
        effect=Effect.SIGNIFICANT_DELAYS,
        active_period=[
            ActivePeriod(
                start=datetime(2026, 5, 11, 8, 0, tzinfo=UTC),
                end=datetime(2026, 5, 11, 10, 0, tzinfo=UTC),
            )
        ],
        informed_entity=[InformedEntity(route_id="Red")],
    )

    row = format_alert_row(alert)

    assert row["header"] == "Red Line: significant delays"
    assert row["description"] == "Disabled train at Park Street."
    assert row["effect_label"] == "Delays"
    assert row["cause"] == "TECHNICAL_PROBLEM"
    assert row["starts"] is not None
    assert row["ends"] is not None


def test_format_alert_row_handles_missing_period() -> None:
    alert = ServiceAlert(
        header_text="Always-on advisory",
        description_text=None,
        cause=Cause.OTHER_CAUSE,
        effect=Effect.NO_EFFECT,
        active_period=[],
        informed_entity=[InformedEntity(route_id="Red")],
    )

    row = format_alert_row(alert)
    assert row["starts"] is None
    assert row["ends"] is None
    assert row["effect_label"] == "Info"


# ---- should_show_stale_banner -----------------------------------------------


def test_should_show_stale_banner_all_fresh() -> None:
    healths = {
        FeedType.TRIP_UPDATES: _health(age=5, is_stale=False, is_degraded=False),
        FeedType.SERVICE_ALERTS: _health(age=5, is_stale=False, is_degraded=False),
    }
    assert should_show_stale_banner(healths) is False


def test_should_show_stale_banner_one_stale() -> None:
    healths = {
        FeedType.TRIP_UPDATES: _health(age=120, is_stale=True, is_degraded=False),
        FeedType.SERVICE_ALERTS: _health(age=5, is_stale=False, is_degraded=False),
    }
    assert should_show_stale_banner(healths) is True


def test_should_show_stale_banner_one_degraded() -> None:
    healths = [
        _health(age=5, is_stale=False, is_degraded=False),
        _health(age=5, is_stale=False, is_degraded=True),
    ]
    assert should_show_stale_banner(healths) is True


def test_should_show_stale_banner_accepts_dict_or_list() -> None:
    """Both calling conventions work."""
    h = _health(age=5, is_stale=False, is_degraded=False)
    assert should_show_stale_banner({FeedType.TRIP_UPDATES: h}) is False
    assert should_show_stale_banner([h]) is False
