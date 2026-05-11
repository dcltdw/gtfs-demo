"""GTFS-RT feed URL constants for the MBTA.

Defaults are public, unauthenticated MBTA endpoints. Override via env (see
``.env.example``) to point the realtime fetcher at a mirror or a fixture.
"""

from __future__ import annotations

from typing import Final

TRIP_UPDATES_URL: Final[str] = "https://cdn.mbta.com/realtime/TripUpdates.pb"
VEHICLE_POSITIONS_URL: Final[str] = "https://cdn.mbta.com/realtime/VehiclePositions.pb"
SERVICE_ALERTS_URL: Final[str] = "https://cdn.mbta.com/realtime/Alerts.pb"

ALL_FEED_URLS: Final[tuple[str, ...]] = (
    TRIP_UPDATES_URL,
    VEHICLE_POSITIONS_URL,
    SERVICE_ALERTS_URL,
)
