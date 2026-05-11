"""Presenter helpers for the arrivals board.

Pure functions over typed ``Arrival`` rows — no I/O, no Streamlit imports.
The Streamlit page (#11) calls these and renders the result.
"""

from __future__ import annotations

from datetime import datetime

from gtfs_dleung.models.arrival import Arrival, ScheduleRelationship
from gtfs_dleung.parser.tripupdates import MBTA_TZ

_BOARD_VISIBLE = (ScheduleRelationship.SCHEDULED, ScheduleRelationship.ADDED)


def next_n_arrivals(
    arrivals: list[Arrival],
    stop_id: str,
    n: int = 5,
    *,
    now: datetime | None = None,
) -> list[Arrival]:
    """Return the next ``n`` arrivals at ``stop_id``, sorted by predicted time.

    Filters:

    - The stop's ``stop_id`` matches (no parent-station rollup yet — callers
      pass the corridor-platform stop_id).
    - ``predicted_at`` is in the future relative to ``now``.
    - ``schedule_relationship`` is SCHEDULED or ADDED. CANCELED + SKIPPED + UNSCHEDULED
      are returned by the parser but excluded from the default board view (alerts
      panel surfaces them separately in #7).
    """
    if now is None:
        now = datetime.now(tz=MBTA_TZ)

    eligible = [
        a
        for a in arrivals
        if a.stop_id == stop_id
        and a.schedule_relationship in _BOARD_VISIBLE
        and a.predicted_at is not None
        and a.predicted_at >= now
    ]
    eligible.sort(key=lambda a: a.predicted_at or now)
    return eligible[:n]
