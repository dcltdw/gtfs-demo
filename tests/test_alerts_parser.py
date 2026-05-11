"""Tests for ``gtfs_dleung.parser.alerts.parse``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from google.transit import gtfs_realtime_pb2

from gtfs_dleung.models.alert import Cause, Effect
from gtfs_dleung.parser.alerts import parse
from tests.helpers import make_alerts_feed

NOW = datetime(2026, 5, 11, 14, 0, tzinfo=UTC)


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


def test_basic_parse() -> None:
    """Header / description / cause / effect / period / informed entity all populate."""
    feed = make_alerts_feed(
        alerts=[
            {
                "header_text": "Red Line: Significant delays",
                "description_text": "Disabled train at Park Street; expect 15-minute delays.",
                "cause": "TECHNICAL_PROBLEM",
                "effect": "SIGNIFICANT_DELAYS",
                "active_periods": [
                    {"start": _ts(NOW - timedelta(hours=1)), "end": _ts(NOW + timedelta(hours=2))}
                ],
                "informed_entities": [{"route_id": "Red"}],
            }
        ]
    )

    alerts = parse(feed, now=NOW)

    assert len(alerts) == 1
    a = alerts[0]
    assert a.header_text == "Red Line: Significant delays"
    assert a.description_text == "Disabled train at Park Street; expect 15-minute delays."
    assert a.cause == Cause.TECHNICAL_PROBLEM
    assert a.effect == Effect.SIGNIFICANT_DELAYS
    assert len(a.active_period) == 1
    assert len(a.informed_entity) == 1
    assert a.informed_entity[0].route_id == "Red"


def test_filters_by_informed_route() -> None:
    """An alert is kept iff at least one informed_entity targets a scope route or stop."""
    feed = make_alerts_feed(
        alerts=[
            {
                "header_text": "Red Line delays",
                "informed_entities": [{"route_id": "Red"}],
                "active_periods": [{"start": _ts(NOW - timedelta(hours=1))}],
            },
            {
                "header_text": "Green-E elevator outage at Ball Sq",
                "informed_entities": [{"stop_id": "place-balsq"}],
                "active_periods": [{"start": _ts(NOW - timedelta(hours=1))}],
            },
            {
                "header_text": "Green-D weekend shuttle",
                "informed_entities": [{"route_id": "Green-D"}],
                "active_periods": [{"start": _ts(NOW - timedelta(hours=1))}],
            },
            {
                "header_text": "Commuter rail delay",
                "informed_entities": [{"route_id": "CR-Worcester"}],
                "active_periods": [{"start": _ts(NOW - timedelta(hours=1))}],
            },
            {
                "header_text": "Alert with no informed_entity at all",
                "active_periods": [{"start": _ts(NOW - timedelta(hours=1))}],
            },
        ]
    )

    alerts = parse(feed, now=NOW)
    headers = {a.header_text for a in alerts}

    assert headers == {"Red Line delays", "Green-E elevator outage at Ball Sq"}


def test_excludes_expired_alerts() -> None:
    """Alerts whose ``active_period`` doesn't overlap ``now`` are dropped."""
    feed = make_alerts_feed(
        alerts=[
            {
                "header_text": "Last week's shuttle",
                "informed_entities": [{"route_id": "Red"}],
                "active_periods": [
                    {
                        "start": _ts(NOW - timedelta(days=7)),
                        "end": _ts(NOW - timedelta(days=5)),
                    }
                ],
            },
            {
                "header_text": "Active now",
                "informed_entities": [{"route_id": "Red"}],
                "active_periods": [
                    {
                        "start": _ts(NOW - timedelta(hours=1)),
                        "end": _ts(NOW + timedelta(hours=1)),
                    }
                ],
            },
            {
                "header_text": "Future weekend closure",
                "informed_entities": [{"route_id": "Red"}],
                "active_periods": [
                    {
                        "start": _ts(NOW + timedelta(days=3)),
                        "end": _ts(NOW + timedelta(days=5)),
                    }
                ],
            },
        ]
    )

    alerts = parse(feed, now=NOW)
    headers = {a.header_text for a in alerts}

    assert headers == {"Active now"}


def test_alert_with_no_active_period_is_always_on() -> None:
    """Per the GTFS-RT spec, no active_period means the alert applies indefinitely."""
    feed = make_alerts_feed(
        alerts=[
            {
                "header_text": "Permanent advisory",
                "informed_entities": [{"route_id": "Red"}],
            }
        ]
    )

    alerts = parse(feed, now=NOW)
    assert len(alerts) == 1


def test_alert_with_only_start_is_active_after_start() -> None:
    """Open-ended-on-the-right TimeRange — active forever after ``start``."""
    feed = make_alerts_feed(
        alerts=[
            {
                "header_text": "Started yesterday, no end set",
                "informed_entities": [{"route_id": "Red"}],
                "active_periods": [{"start": _ts(NOW - timedelta(days=1))}],
            }
        ]
    )

    alerts = parse(feed, now=NOW)
    assert len(alerts) == 1


def test_alert_with_only_end_is_active_until_end() -> None:
    """Open-ended-on-the-left TimeRange — active up until ``end``."""
    future_end = _ts(NOW + timedelta(days=1))
    past_end = _ts(NOW - timedelta(days=1))

    feed = make_alerts_feed(
        alerts=[
            {
                "header_text": "Open-start, future end",
                "informed_entities": [{"route_id": "Red"}],
                "active_periods": [{"end": future_end}],
            },
            {
                "header_text": "Open-start, past end",
                "informed_entities": [{"route_id": "Red"}],
                "active_periods": [{"end": past_end}],
            },
        ]
    )

    alerts = parse(feed, now=NOW)
    headers = {a.header_text for a in alerts}
    assert headers == {"Open-start, future end"}


def test_cause_and_effect_enum_mapping() -> None:
    """A spread of cause/effect values map to the right enum members."""
    feed = make_alerts_feed(
        alerts=[
            {
                "header_text": "Weather closure",
                "cause": "WEATHER",
                "effect": "NO_SERVICE",
                "informed_entities": [{"route_id": "Red"}],
            },
            {
                "header_text": "Maintenance shuttle",
                "cause": "MAINTENANCE",
                "effect": "DETOUR",
                "informed_entities": [{"route_id": "Green-E"}],
            },
            {
                "header_text": "Accessibility issue at Ball Sq elevator",
                "cause": "TECHNICAL_PROBLEM",
                "effect": "ACCESSIBILITY_ISSUE",
                "informed_entities": [{"stop_id": "place-balsq"}],
            },
        ]
    )

    alerts = parse(feed, now=NOW)
    by_header = {a.header_text: a for a in alerts}

    assert by_header["Weather closure"].cause == Cause.WEATHER
    assert by_header["Weather closure"].effect == Effect.NO_SERVICE
    assert by_header["Maintenance shuttle"].cause == Cause.MAINTENANCE
    assert by_header["Maintenance shuttle"].effect == Effect.DETOUR
    assert by_header["Accessibility issue at Ball Sq elevator"].effect == Effect.ACCESSIBILITY_ISSUE


def test_parses_real_fixture() -> None:
    """The committed real-feed fixture decodes; all kept alerts touch scope."""
    fixture = Path(__file__).parent / "fixtures" / "alerts_sample.pb"
    msg = gtfs_realtime_pb2.FeedMessage()
    msg.ParseFromString(fixture.read_bytes())

    # The fixture was captured at a specific past time; alerts may not be 'active' at NOW.
    # Use a generous now so active-period filter passes for everything the fixture intended.
    far_future = datetime(2030, 1, 1, tzinfo=UTC)
    alerts = parse(msg, now=far_future)

    # Every kept alert must touch the scope (the parser's first filter).
    for a in alerts:
        routes = {ie.route_id for ie in a.informed_entity if ie.route_id}
        stops = {ie.stop_id for ie in a.informed_entity if ie.stop_id}
        in_scope = (routes & {"Red", "Green-E"}) or (
            stops
            & {
                "place-pktrm",
                "place-chmnl",
                "place-knncl",
                "place-cntsq",
                "place-harsq",
                "place-portr",
                "place-davis",
                "place-gover",
                "place-haecl",
                "place-north",
                "place-spmnl",
                "place-lech",
                "place-esomr",
                "place-gilmn",
                "place-mgngl",
                "place-balsq",
            }
        )
        assert in_scope, f"kept alert {a.header_text!r} did not touch scope"
