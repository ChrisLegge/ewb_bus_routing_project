"""
extract_ladywood_stops.py
==========================
From the TfWM GTFS feed, extract the real stops served by the Ladywood
bus routes (8 / 8A / 8C Inner Circle, 80, 126) within the Ladywood area,
and write them to data/gtfs/ladywood_stops.json.

This is the bridge from synthetic geography to real, named, geocoded stops.

Usage:
    python scripts/extract_ladywood_stops.py
"""

import csv
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path

_REPO = Path(__file__).parent.parent
ZIP = _REPO / "data" / "gtfs" / "tfwm_gtfs.zip"
OUT = _REPO / "data" / "gtfs" / "ladywood_stops.json"

# Ladywood + immediate surroundings bounding box (lat/lon)
LAT_MIN, LAT_MAX = 52.462, 52.502
LON_MIN, LON_MAX = -1.960, -1.888

TARGET_ROUTES = {"8", "8A", "8C", "80", "126"}


def _reader(z: zipfile.ZipFile, name: str):
    return csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig"))


def main() -> None:
    z = zipfile.ZipFile(ZIP)

    # 1. route_id -> short name, for our targets
    route_ids: dict[str, str] = {}
    for r in _reader(z, "routes.txt"):
        if r.get("route_short_name", "") in TARGET_ROUTES:
            route_ids[r["route_id"]] = r["route_short_name"]
    print(f"Matched {len(route_ids)} route variants: {sorted(set(route_ids.values()))}")

    # 2. trip_id -> short name (only trips on our routes)
    trip_route: dict[str, str] = {}
    for t in _reader(z, "trips.txt"):
        if t["route_id"] in route_ids:
            trip_route[t["trip_id"]] = route_ids[t["route_id"]]
    print(f"Matched {len(trip_route):,} trips")

    # 3. stop_id -> set of route short names that serve it
    stop_routes: dict[str, set[str]] = defaultdict(set)
    for st in _reader(z, "stop_times.txt"):
        sn = trip_route.get(st["trip_id"])
        if sn:
            stop_routes[st["stop_id"]].add(sn)
    print(f"Stops touched by our routes: {len(stop_routes):,}")

    # 4. join to stop coords/names, filter to Ladywood bbox
    stops_out = []
    for s in _reader(z, "stops.txt"):
        sid = s["stop_id"]
        if sid not in stop_routes:
            continue
        try:
            lat, lon = float(s["stop_lat"]), float(s["stop_lon"])
        except (ValueError, KeyError):
            continue
        if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
            continue
        stops_out.append({
            "stop_id":   sid,
            "name":      s.get("stop_name", sid),
            "lat":       round(lat, 6),
            "lng":       round(lon, 6),
            "routes":    sorted(stop_routes[sid]),
            "n_routes":  len(stop_routes[sid]),
        })

    # Sort: most-served stops first (proxy for importance)
    stops_out.sort(key=lambda s: (-s["n_routes"], s["name"]))

    OUT.write_text(json.dumps(stops_out, indent=2), encoding="utf-8")
    print(f"\nWrote {len(stops_out)} Ladywood-area stops -> {OUT}")
    print("\nTop served stops:")
    for s in stops_out[:20]:
        print(f"  {s['name'][:40]:<40} {'/'.join(s['routes']):<14} ({s['lat']}, {s['lng']})")


if __name__ == "__main__":
    main()
