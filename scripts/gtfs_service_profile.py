"""
gtfs_service_profile.py
=======================
Mines the TfWM GTFS zip to produce a real service-frequency profile for each
of the 15 model stops — the actual number of bus departures per hour, split by
weekday / Saturday / Sunday, for routes 8/8A/8C/80/126.

This is the ground-truth complement to the synthetic demand dataset. Service
frequency is a strong proxy for actual ridership (more buses → more passengers
can travel) and anchors the synthetic temporal patterns to reality.

Output
------
  data/gtfs/service_profile.json
  {
    "S01": {
      "gtfs_stop_id": "43000...",
      "gtfs_stop_name": "New Street Station",
      "distance_m": 38.2,
      "routes": ["80"],
      "weekday": {"0": 0, "1": 0, ..., "23": 4},   # trips per hour
      "saturday": {...},
      "sunday": {...},
      "time_windows": {
        "weekday": {"AM Peak": 12, "Mid Morning": 8, ...},
        ...
      }
    },
    ...
  }

Usage
-----
  python scripts/gtfs_service_profile.py
"""

from __future__ import annotations

import csv
import io
import json
import math
import zipfile
from collections import defaultdict
from pathlib import Path

_REPO = Path(__file__).parent.parent
ZIP  = _REPO / "data" / "gtfs" / "tfwm_gtfs.zip"
OUT  = _REPO / "data" / "gtfs" / "service_profile.json"

TARGET_ROUTES = {"8", "8A", "8C", "80", "126"}

# Mirror the model's time-window → hour mapping (from api.py / demand_route_optimizer.py)
TIME_WINDOWS: dict[str, list[int]] = {
    "Early Morning": list(range(5,  7)),
    "AM Peak":       list(range(7,  9)),
    "Mid Morning":   list(range(9,  11)),
    "Lunch":         list(range(11, 13)),
    "Afternoon":     list(range(13, 16)),
    "PM Peak":       list(range(16, 18)),
    "Evening":       list(range(18, 21)),
    "Night":         list(range(21, 24)),
}

# Model stop coords from ladywood_display.py
MODEL_STOPS: dict[str, dict] = {
    "S01": {"name": "New Street Station",       "lat": 52.477558, "lng": -1.896240},
    "S02": {"name": "Spring St",                "lat": 52.467575, "lng": -1.904080},
    "S03": {"name": "Jewellery Quarter Station","lat": 52.489780, "lng": -1.912559},
    "S04": {"name": "Soho Hill",                "lat": 52.496273, "lng": -1.915020},
    "S05": {"name": "Five Ways (West Midlands Metro)", "lat": 52.475674, "lng": -1.913573},
    "S06": {"name": "Dudley Rd",                "lat": 52.485722, "lng": -1.936805},
    "S07": {"name": "Five Ways Station",        "lat": 52.472332, "lng": -1.912667},
    "S08": {"name": "Icknield Port Rd",         "lat": 52.478622, "lng": -1.926436},
    "S09": {"name": "Belgrave Interchange",     "lat": 52.466953, "lng": -1.898929},
    "S10": {"name": "Ladywood Fire Station",    "lat": 52.477840, "lng": -1.927453},
    "S11": {"name": "Edgbaston Village (Metro)","lat": 52.472256, "lng": -1.923237},
    "S12": {"name": "Summerfield Park",         "lat": 52.486561, "lng": -1.938601},
    "S13": {"name": "City Rd Medical Centre",   "lat": 52.486130, "lng": -1.940943},
    "S14": {"name": "Mencap Centre",            "lat": 52.493015, "lng": -1.959108},
    "S15": {"name": "Summerfield Crescent",     "lat": 52.482845, "lng": -1.934218},
}


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _reader(z: zipfile.ZipFile, name: str):
    return csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig"))


def _day_types(row: dict) -> set[str]:
    """
    Return the set of day-type buckets a service applies to.
    TfWM uses fragmented service IDs: a single service may run Mon-Sun (all
    three buckets), or only specific days. We accumulate all applicable buckets
    so that all-week services are correctly counted in weekday, saturday, and
    sunday profiles.
    """
    buckets: set[str] = set()
    weekdays = ("monday", "tuesday", "wednesday", "thursday", "friday")
    if any(row.get(d, "0") == "1" for d in weekdays):
        buckets.add("weekday")
    if row.get("saturday", "0") == "1":
        buckets.add("saturday")
    if row.get("sunday", "0") == "1":
        buckets.add("sunday")
    return buckets


def main() -> None:
    z = zipfile.ZipFile(ZIP)

    # ── 1. Match model stops to nearest real GTFS stop ────────────────────────
    ladywood_stops = json.loads(
        (_REPO / "data" / "gtfs" / "ladywood_stops.json").read_text()
    )
    model_to_gtfs: dict[str, dict] = {}
    for sid, ms in MODEL_STOPS.items():
        best, best_d = None, float("inf")
        for rs in ladywood_stops:
            d = _haversine_m(ms["lat"], ms["lng"], rs["lat"], rs["lng"])
            if d < best_d:
                best_d, best = d, rs
        if best and best_d < 600:   # accept match within 600 m
            model_to_gtfs[sid] = {
                "gtfs_stop_id":   best["stop_id"],
                "gtfs_stop_name": best["name"],
                "distance_m":     round(best_d, 1),
                "routes":         best["routes"],
            }
            print(f"  {sid} {ms['name']:<35} -> {best['name']:<35} ({best_d:.0f} m)")
        else:
            print(f"  {sid} {ms['name']:<35} -> NO MATCH within 600 m")

    target_gtfs_ids: set[str] = {v["gtfs_stop_id"] for v in model_to_gtfs.values()}

    # ── 2. Routes → route_ids ─────────────────────────────────────────────────
    route_ids: dict[str, str] = {}   # route_id → short_name
    for r in _reader(z, "routes.txt"):
        if r.get("route_short_name", "") in TARGET_ROUTES:
            route_ids[r["route_id"]] = r["route_short_name"]
    print(f"\nMatched {len(route_ids)} route records for {sorted(set(route_ids.values()))}")

    # ── 3. Calendar → service_id → set of day_type buckets ───────────────────
    service_days: dict[str, set[str]] = {}
    for row in _reader(z, "calendar.txt"):
        buckets = _day_types(row)
        if buckets:
            service_days[row["service_id"]] = buckets

    # ── 4. Trips → trip_id → (route short name, set of day_types) ────────────
    target_trips: dict[str, tuple[str, set[str]]] = {}
    for t in _reader(z, "trips.txt"):
        if t["route_id"] not in route_ids:
            continue
        buckets = service_days.get(t["service_id"])
        if buckets:
            target_trips[t["trip_id"]] = (route_ids[t["route_id"]], buckets)

    print(f"Relevant trips (Ladywood routes × Mon–Sun service): {len(target_trips):,}")

    # ── 5. Stream stop_times → count departures per (model_stop, day_type, hour) ─
    # Build gtfs_id → model stop_id reverse map (one-to-many is fine)
    gtfs_to_model: dict[str, list[str]] = defaultdict(list)
    for sid, info in model_to_gtfs.items():
        gtfs_to_model[info["gtfs_stop_id"]].append(sid)

    # counts[model_stop_id][day_type][hour] = trip count
    counts: dict[str, dict[str, dict[int, int]]] = {
        sid: {"weekday": defaultdict(int), "saturday": defaultdict(int), "sunday": defaultdict(int)}
        for sid in MODEL_STOPS
    }

    print("Streaming stop_times.txt …")
    total_matched = 0
    for row in _reader(z, "stop_times.txt"):
        trip_id = row["trip_id"]
        stop_id = row["stop_id"]
        if trip_id not in target_trips or stop_id not in gtfs_to_model:
            continue
        _, day_types = target_trips[trip_id]
        dep = row["departure_time"]
        try:
            h = int(dep.split(":")[0]) % 24   # GTFS allows hours >23 for overnight
        except (ValueError, IndexError):
            continue
        for model_sid in gtfs_to_model[stop_id]:
            for day_type in day_types:
                counts[model_sid][day_type][h] += 1
            total_matched += 1

    print(f"Matched {total_matched:,} stop_time records to model stops")

    # ── 6. Aggregate into time windows + build output ─────────────────────────
    def _window_counts(hourly: dict[int, int]) -> dict[str, int]:
        return {
            name: sum(hourly.get(h, 0) for h in hours)
            for name, hours in TIME_WINDOWS.items()
        }

    out: dict[str, dict] = {}
    for sid in MODEL_STOPS:
        info = model_to_gtfs.get(sid, {})
        wkd  = counts[sid]["weekday"]
        sat  = counts[sid]["saturday"]
        sun  = counts[sid]["sunday"]
        out[sid] = {
            **info,
            "weekday":  {str(h): wkd.get(h, 0)  for h in range(24)},
            "saturday": {str(h): sat.get(h, 0) for h in range(24)},
            "sunday":   {str(h): sun.get(h, 0) for h in range(24)},
            "time_windows": {
                "weekday":  _window_counts(wkd),
                "saturday": _window_counts(sat),
                "sunday":   _window_counts(sun),
            },
        }

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote service profile -> {OUT}")

    # ── 7. Quick summary ──────────────────────────────────────────────────────
    print("\nWeekday AM Peak trip counts per model stop:")
    for sid in sorted(out):
        am = out[sid]["time_windows"]["weekday"].get("AM Peak", 0)
        name = MODEL_STOPS[sid]["name"]
        print(f"  {sid}  {name:<35}  {am:>3} trips/window")


if __name__ == "__main__":
    main()
