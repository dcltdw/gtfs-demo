"""Input-validation helpers.

These exist as a **defence-in-depth** layer: even if the Streamlit page is
strict about only sending in-scope stop IDs, an attacker hitting the Python
surface directly (URL crafting, future API) shouldn't be able to coax the
parsers into querying arbitrary stops.

Today the only function is :func:`validate_stop_id`, which checks against the
demo corridor's parent-station allow-list. As surfaces grow (route IDs, trip
IDs, time ranges), more validators land here.
"""

from __future__ import annotations

from gtfs_dleung.scope import ALL_CORRIDOR_PARENT_STATIONS


def validate_stop_id(stop_id: str) -> str:
    """Return ``stop_id`` unchanged if it's a demo-scope parent station; else raise.

    The accepted set is ``ALL_CORRIDOR_PARENT_STATIONS``: the 16 parent station
    IDs covering Red Line (Park ↔ Davis) and Green Line E (Park ↔ Ball Sq).
    Platform-level stop IDs (e.g. ``70075``) are intentionally **rejected** —
    callers should resolve to the parent station before validating.

    Raises :class:`ValueError` with a message safe to surface to the user (no
    enumeration of valid IDs — that lives in the docs, not in error messages).
    """
    if stop_id in ALL_CORRIDOR_PARENT_STATIONS:
        return stop_id
    raise ValueError(f"stop_id {stop_id!r} is not in the demo scope")


__all__ = ("validate_stop_id",)
