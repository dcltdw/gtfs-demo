"""Build the minimal GTFS-static test fixture used by ``tests/fixtures/mbta-mini.zip``.

Run from a directory that contains a freshly-unzipped real MBTA GTFS feed:

    mkdir -p /tmp/mbta && cd /tmp/mbta && \
        curl -sSL -A 'gtfs-dleung/0.0.1 (https://github.com/dcltdw/gtfs-dleung)' \
            -o MBTA_GTFS.zip https://cdn.mbta.com/MBTA_GTFS.zip && \
        unzip -q MBTA_GTFS.zip
    cd /Users/dcltdw/Github/gtfs-dleung
    uv run python scripts/build_test_fixture.py /tmp/mbta

The script writes ``tests/fixtures/mbta-mini.zip`` and is safe to re-run.

The fixture intentionally includes a small number of trips from one out-of-scope
route (``39`` — the 39 bus) so the filter can be exercised both ways: kept
entities for Red + Green-E, dropped entities for everything else.
"""

from __future__ import annotations

import csv
import sys
import zipfile
from pathlib import Path

# Routes the fixture keeps: the demo scope plus one out-of-scope route to test filtering.
SCOPE_ROUTES = {"Red", "Green-E"}
OUT_OF_SCOPE_BUS = "39"
KEEP_ROUTES = SCOPE_ROUTES | {OUT_OF_SCOPE_BUS}

# Maximum trips kept per route. Keeps the fixture under ~50 KB.
TRIPS_PER_ROUTE = 2

# All corridor parent station IDs — see gtfs_dleung/scope.py for the authoritative list.
ALL_CORRIDOR_PARENT_STATIONS = {
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


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    return fields, rows


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main(source: Path, dest_zip: Path) -> None:
    print(f"Source feed: {source}")
    print(f"Writing fixture: {dest_zip}")

    routes_fields, routes_rows = read_csv(source / "routes.txt")
    trips_fields, trips_rows = read_csv(source / "trips.txt")
    stops_fields, stops_rows = read_csv(source / "stops.txt")
    stop_times_fields, stop_times_rows = read_csv(source / "stop_times.txt")
    shapes_fields, shapes_rows = read_csv(source / "shapes.txt")

    # Keep routes
    keep_routes = [r for r in routes_rows if r["route_id"] in KEEP_ROUTES]
    print(f"  routes: {len(keep_routes)} of {len(routes_rows)}")

    # For each kept route, pick the first N trips. The 39 bus contributes trips
    # whose stops include the literal "Park St @ ..." bus stops — useful to
    # prove the filter doesn't keep them just because of name overlap.
    keep_trips: list[dict[str, str]] = []
    for route_id in KEEP_ROUTES:
        route_trips = [t for t in trips_rows if t["route_id"] == route_id]
        keep_trips.extend(route_trips[:TRIPS_PER_ROUTE])
    keep_trip_ids = {t["trip_id"] for t in keep_trips}
    print(f"  trips: {len(keep_trips)}")

    # Stop times for kept trips
    keep_stop_times = [st for st in stop_times_rows if st["trip_id"] in keep_trip_ids]
    print(f"  stop_times: {len(keep_stop_times)}")

    # Stops: every stop referenced by the kept stop_times, plus their parent stations
    referenced_stop_ids = {st["stop_id"] for st in keep_stop_times}
    keep_stop_rows = [s for s in stops_rows if s["stop_id"] in referenced_stop_ids]
    parent_ids = {s.get("parent_station") for s in keep_stop_rows if s.get("parent_station")}
    parent_rows = [s for s in stops_rows if s["stop_id"] in parent_ids]
    # Deduplicate
    seen: set[str] = set()
    keep_stops: list[dict[str, str]] = []
    for s in keep_stop_rows + parent_rows:
        if s["stop_id"] not in seen:
            seen.add(s["stop_id"])
            keep_stops.append(s)
    print(f"  stops: {len(keep_stops)}")

    # Shapes for kept trips
    keep_shape_ids = {t["shape_id"] for t in keep_trips if t.get("shape_id")}
    keep_shapes = [sh for sh in shapes_rows if sh["shape_id"] in keep_shape_ids]
    # Subsample shapes to keep the fixture small (every 20th point per shape).
    by_shape: dict[str, list[dict[str, str]]] = {}
    for sh in keep_shapes:
        by_shape.setdefault(sh["shape_id"], []).append(sh)
    sampled_shapes: list[dict[str, str]] = []
    for points in by_shape.values():
        points.sort(key=lambda p: int(p["shape_pt_sequence"]))
        sampled_shapes.extend(points[::20])
    print(f"  shapes: {len(sampled_shapes)} (subsampled from {len(keep_shapes)})")

    # Minimal agency.txt + calendar.txt for GTFS-validity. Static agency entry
    # plus a single SERVICE_ID covering Mon-Sun avoids having to mine the real
    # calendar.
    agency_fields = ["agency_id", "agency_name", "agency_url", "agency_timezone"]
    agency_rows = [
        {
            "agency_id": "1",
            "agency_name": "MBTA",
            "agency_url": "https://www.mbta.com",
            "agency_timezone": "America/New_York",
        }
    ]
    service_ids = {t["service_id"] for t in keep_trips}
    calendar_fields = [
        "service_id",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "start_date",
        "end_date",
    ]
    calendar_rows = [
        {
            "service_id": sid,
            "monday": "1",
            "tuesday": "1",
            "wednesday": "1",
            "thursday": "1",
            "friday": "1",
            "saturday": "1",
            "sunday": "1",
            "start_date": "20260101",
            "end_date": "20271231",
        }
        for sid in service_ids
    ]

    # Write zip
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    if dest_zip.exists():
        dest_zip.unlink()
    with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, fields, rows in (
            ("routes.txt", routes_fields, keep_routes),
            ("trips.txt", trips_fields, keep_trips),
            ("stops.txt", stops_fields, keep_stops),
            ("stop_times.txt", stop_times_fields, keep_stop_times),
            ("shapes.txt", shapes_fields, sampled_shapes),
            ("agency.txt", agency_fields, agency_rows),
            ("calendar.txt", calendar_fields, calendar_rows),
        ):
            path = dest_zip.parent / name
            write_csv(path, fields, rows)
            zf.write(path, arcname=name)
            path.unlink()

    print(f"Wrote {dest_zip} ({dest_zip.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: build_test_fixture.py <path-to-unzipped-mbta-feed>", file=sys.stderr)
        sys.exit(1)
    source = Path(sys.argv[1])
    dest = Path(__file__).parent.parent / "tests" / "fixtures" / "mbta-mini.zip"
    main(source, dest)
