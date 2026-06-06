"""
fetch_elevation.py
==================
Fetches elevation (metres above sea level) for each Ladywood model stop
using the Open-Meteo Elevation API (free, no auth required).

Elevation is a proxy for walking difficulty to stops — steeper terrain
reduces effective catchment radius and suppresses demand.

Output
------
  data/elevation/ladywood_stop_elevation.json

Usage
-----
  python scripts/fetch_elevation.py
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

_REPO   = Path(__file__).parent.parent
OUT_DIR = _REPO / "data" / "elevation"
OUT     = OUT_DIR / "ladywood_stop_elevation.json"

API_URL = "https://api.open-meteo.com/v1/elevation"
HEADERS = {"User-Agent": "ewb-bus-routing/1.0 (EWB design challenge; educational use)"}

STOPS: dict[str, dict] = {
    "S01": {"name": "New Street Station",        "lat": 52.4778, "lon": -1.8990},
    "S02": {"name": "Spring St",                 "lat": 52.4868, "lon": -1.9101},
    "S03": {"name": "Jewellery Quarter Station", "lat": 52.4868, "lon": -1.9101},
    "S04": {"name": "Soho Hill",                 "lat": 52.5012, "lon": -1.9178},
    "S05": {"name": "Five Ways (Metro)",         "lat": 52.4737, "lon": -1.9102},
    "S06": {"name": "Dudley Rd",                 "lat": 52.4887, "lon": -1.9302},
    "S07": {"name": "Five Ways Station",         "lat": 52.4737, "lon": -1.9102},
    "S08": {"name": "Icknield Port Rd",          "lat": 52.4914, "lon": -1.9267},
    "S09": {"name": "Belgrave Interchange",      "lat": 52.4820, "lon": -1.8960},
    "S10": {"name": "Ladywood Fire Station",     "lat": 52.4820, "lon": -1.9200},
    "S11": {"name": "Edgbaston Village Metro",   "lat": 52.4680, "lon": -1.9170},
    "S12": {"name": "Summerfield Park",          "lat": 52.4940, "lon": -1.9200},
    "S13": {"name": "City Rd Medical Centre",    "lat": 52.4880, "lon": -1.9350},
    "S14": {"name": "Mencap Centre",             "lat": 52.5020, "lon": -1.9430},
    "S15": {"name": "Summerfield Crescent",      "lat": 52.4930, "lon": -1.9230},
}


def run() -> dict:
    # Batch all stops in one request
    lats = [str(s["lat"]) for s in STOPS.values()]
    lons = [str(s["lon"]) for s in STOPS.values()]

    print(f"Fetching elevation for {len(STOPS)} stops via Open-Meteo...")
    params = {
        "latitude":  ",".join(lats),
        "longitude": ",".join(lons),
    }
    r = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    elevations = r.json().get("elevation", [])
    print(f"  Got {len(elevations)} elevation values")

    result = {}
    sep = "-" * 55
    print(f"\n{'Stop Elevations (m above sea level)':^55}")
    print(sep)

    for (sid, stop), elev in zip(STOPS.items(), elevations):
        result[sid] = {
            "stop_name":    stop["name"],
            "lat":          stop["lat"],
            "lon":          stop["lon"],
            "elevation_m":  round(elev, 1),
            "data_source":  "Open-Meteo Elevation API (SRTM 90m)",
        }
        bar = "#" * int(elev / 5)
        print(f"  {sid}  {stop['name']:<30}  {elev:>6.1f}m  {bar}")

    print(sep)

    # Summary stats
    elevs = [v["elevation_m"] for v in result.values()]
    print(f"\n  Min: {min(elevs):.1f}m  Max: {max(elevs):.1f}m  Range: {max(elevs)-min(elevs):.1f}m")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    return result


if __name__ == "__main__":
    run()
