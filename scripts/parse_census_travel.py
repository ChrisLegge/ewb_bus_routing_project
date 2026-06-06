"""
parse_census_travel.py
======================
Parses ONS Census 2021 TS061 (Method used to travel to work) for Birmingham
LSOAs and extracts bus usage rates for the 15 Ladywood model stops.

Each model stop is mapped to its IMD 2019 LSOA (from equity.py). The bus
usage rate (bus commuters / total employed residents) is a real observed
signal of transit dependency at each stop -- a ground-truth complement to
the synthetic demand model.

Source
------
  ONS Census 2021, Table TS061 -- Method used to travel to work
  Downloaded from Nomis (nomisweb.co.uk), LSOA level, Birmingham LA
  File: data/census/ts061_travel_to_work_birmingham_lsoa_2021.xlsx

Output
------
  data/census/ladywood_bus_dependency.json
  {
    "S01": {
      "lsoa": "E01013761",
      "stop_name": "New Street Station",
      "total_employed": 1234,
      "bus_count": 56,
      "bus_pct": 4.5,
      "metro_count": 12,
      "car_count": 600,
      "foot_count": 80,
      "data_source": "Census 2021 TS061"
    },
    ...
  }

Usage
-----
  python scripts/parse_census_travel.py
"""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl

_REPO = Path(__file__).parent.parent

XLSX = _REPO / "data" / "census" / "ts061_travel_to_work_birmingham_lsoa_2021.xlsx"
OUT  = _REPO / "data" / "census" / "ladywood_bus_dependency.json"

# Model stop -> LSOA mapping (from equity.py)
STOP_LSOA: dict[str, dict] = {
    "S01": {"lsoa": "E01013761", "name": "New Street Station"},
    "S02": {"lsoa": "E01009099", "name": "Spring St"},
    "S03": {"lsoa": "E01009158", "name": "Jewellery Quarter Station"},
    "S04": {"lsoa": "E01009146", "name": "Soho Hill"},
    "S05": {"lsoa": "E01009057", "name": "Five Ways (Metro)"},
    "S06": {"lsoa": "E01009129", "name": "Dudley Rd"},
    "S07": {"lsoa": "E01009111", "name": "Five Ways Station"},
    "S08": {"lsoa": "E01009127", "name": "Icknield Port Rd"},
    "S09": {"lsoa": "E01009097", "name": "Belgrave Interchange"},
    "S10": {"lsoa": "E01009133", "name": "Ladywood Fire Station"},
    "S11": {"lsoa": "E01009063", "name": "Edgbaston Village Metro"},
    "S12": {"lsoa": "E01009119", "name": "Summerfield Park"},
    "S13": {"lsoa": "E01009121", "name": "City Rd Medical Centre"},
    "S14": {"lsoa": "E01013524", "name": "Mencap Centre"},
    "S15": {"lsoa": "E01009117", "name": "Summerfield Crescent"},
}


def parse_xlsx() -> dict[str, dict]:
    """Read the Nomis XLSX and return lsoa_code -> row data."""
    wb = openpyxl.load_workbook(XLSX)
    ws = wb.active

    lsoa_data: dict[str, dict] = {}
    for row in ws.iter_rows(values_only=True):
        if not row[0] or not isinstance(row[0], str):
            continue
        code = row[0].split(" : ")[0].strip()
        if not code.startswith("E"):
            continue
        try:
            lsoa_data[code] = {
                "total":  int(row[1]) if row[1] else 0,
                "metro":  int(row[2]) if row[2] else 0,
                "bus":    int(row[3]) if row[3] else 0,
                "car":    int(row[4]) if row[4] else 0,
                "foot":   int(row[5]) if row[5] else 0,
            }
        except (TypeError, ValueError):
            continue
    return lsoa_data


def run() -> dict:
    lsoa_data = parse_xlsx()
    print(f"Loaded {len(lsoa_data)} Birmingham LSOAs from Census 2021 TS061")

    result: dict[str, dict] = {}
    matched = 0
    missing = []

    for sid, info in STOP_LSOA.items():
        lsoa = info["lsoa"]
        row  = lsoa_data.get(lsoa)

        if row is None:
            missing.append((sid, lsoa, info["name"]))
            result[sid] = {
                "lsoa":        lsoa,
                "stop_name":   info["name"],
                "data_source": "Census 2021 TS061",
                "note":        "LSOA not in Birmingham LA boundary -- outside download scope",
            }
            continue

        total = row["total"] or 1
        bus_pct   = round(100 * row["bus"]   / total, 1)
        metro_pct = round(100 * row["metro"] / total, 1)
        car_pct   = round(100 * row["car"]   / total, 1)
        foot_pct  = round(100 * row["foot"]  / total, 1)
        transit_pct = round(bus_pct + metro_pct, 1)

        result[sid] = {
            "lsoa":            lsoa,
            "stop_name":       info["name"],
            "total_employed":  row["total"],
            "bus_count":       row["bus"],
            "bus_pct":         bus_pct,
            "metro_count":     row["metro"],
            "metro_pct":       metro_pct,
            "car_count":       row["car"],
            "car_pct":         car_pct,
            "foot_count":      row["foot"],
            "foot_pct":        foot_pct,
            "transit_pct":     transit_pct,
            "data_source":     "Census 2021 TS061",
        }
        matched += 1

    print(f"\nMatched {matched}/15 Ladywood stops to Census data")
    if missing:
        print("Not in Birmingham LA boundary (Smethwick / City Centre):")
        for sid, lsoa, name in missing:
            print(f"  {sid}  {lsoa}  {name}")

    print("\nBus commuter rates per stop (highest to lowest):")
    sep = "-" * 60
    print(sep)
    for sid in sorted(result, key=lambda s: result[s].get("bus_pct", 0), reverse=True):
        r = result[sid]
        if "bus_pct" not in r:
            print(f"  {sid}  {r['stop_name']:<30}  no data")
        else:
            print(f"  {sid}  {r['stop_name']:<30}  {r['bus_pct']:>5.1f}% bus  "
                  f"{r['transit_pct']:>5.1f}% transit  {r['car_pct']:>5.1f}% car")
    print(sep)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")

    return result


if __name__ == "__main__":
    run()
