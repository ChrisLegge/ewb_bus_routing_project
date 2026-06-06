"""
build_road_geometry.py
======================
Precompute real road-following polylines between every pair of the 15 Ladywood
stops using the public OSRM routing service, and cache them to
data/gtfs/road_paths.json.

The dashboard uses these so route lines and buses follow actual streets instead
of straight-line hops. Run once (or after stop coordinates change):

    python scripts/build_road_geometry.py

Output keys are "S01|S07" (sorted stop-id pair) -> [[lng, lat], ...].
Reverse direction is the same polyline reversed (handled by the consumer).
"""

import json
import sys
import time
import urllib.request
from itertools import combinations
from pathlib import Path

_REPO = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO / "dashboard"))

from ladywood_display import STOPS_DISPLAY  # noqa: E402

OUT = _REPO / "data" / "gtfs" / "road_paths.json"
OSRM = "http://router.project-osrm.org/route/v1/driving"


def fetch_path(a: dict, b: dict) -> list[list[float]]:
    url = (
        f"{OSRM}/{a['lng']},{a['lat']};{b['lng']},{b['lat']}"
        "?overview=full&geometries=geojson"
    )
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read())
    if data.get("code") != "Ok":
        raise RuntimeError(data.get("code", "unknown OSRM error"))
    return [[round(x, 6), round(y, 6)] for x, y in data["routes"][0]["geometry"]["coordinates"]]


def main() -> None:
    ids = list(STOPS_DISPLAY.keys())
    paths: dict[str, list[list[float]]] = {}
    pairs = list(combinations(ids, 2))
    print(f"Fetching {len(pairs)} road paths from OSRM ...")

    for n, (i, j) in enumerate(pairs, 1):
        key = f"{i}|{j}"
        try:
            paths[key] = fetch_path(STOPS_DISPLAY[i], STOPS_DISPLAY[j])
        except Exception as e:  # noqa: BLE001
            print(f"  ! {key}: {e} — falling back to straight line")
            a, b = STOPS_DISPLAY[i], STOPS_DISPLAY[j]
            paths[key] = [[a["lng"], a["lat"]], [b["lng"], b["lat"]]]
        if n % 20 == 0:
            print(f"  {n}/{len(pairs)}")
        time.sleep(0.12)  # be polite to the public server

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(paths), encoding="utf-8")
    print(f"Wrote {len(paths)} road paths -> {OUT}")


if __name__ == "__main__":
    main()
