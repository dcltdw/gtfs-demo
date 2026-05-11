"""Demo scope constants — Red Line (Park ↔ Davis) and Green Line E (Park ↔ Ball Sq).

Parent station IDs (``place-*``) define the corridor membership. A stop is in scope
if its ``stop_id`` is one of these IDs OR its ``parent_station`` is one of these
IDs (platform-level stops live under their parent station).

**Trunk-overlap concern**: Park Street's Green Line platforms are shared by
the B / C / D / E branches; route filtering — not just stop filtering — is required
to keep only the E branch.
"""

from __future__ import annotations

from typing import Final

RED_LINE_CORRIDOR: Final[frozenset[str]] = frozenset(
    {
        "place-pktrm",  # Park Street
        "place-chmnl",  # Charles/MGH
        "place-knncl",  # Kendall/MIT
        "place-cntsq",  # Central
        "place-harsq",  # Harvard
        "place-portr",  # Porter
        "place-davis",  # Davis
    }
)

GREEN_E_CORRIDOR: Final[frozenset[str]] = frozenset(
    {
        "place-pktrm",  # Park Street
        "place-gover",  # Government Center
        "place-haecl",  # Haymarket
        "place-north",  # North Station
        "place-spmnl",  # Science Park/West End
        "place-lech",  # Lechmere
        "place-esomr",  # East Somerville
        "place-gilmn",  # Gilman Square
        "place-mgngl",  # Magoun Square
        "place-balsq",  # Ball Square
    }
)

SCOPE_ROUTES: Final[frozenset[str]] = frozenset({"Red", "Green-E"})

ALL_CORRIDOR_PARENT_STATIONS: Final[frozenset[str]] = RED_LINE_CORRIDOR | GREEN_E_CORRIDOR
