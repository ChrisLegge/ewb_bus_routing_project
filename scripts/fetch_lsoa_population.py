"""
fetch_lsoa_population.py
========================
Downloads ONS Census 2021 usual resident population for Birmingham LSOAs
from the Nomis bulk download API and extracts counts for the 15 model stops.

Census table: TS001 — Number of usual residents
  Total usual residents per LSOA — the denominator for demand scaling.

Also fetches TS007A (age groups) to get elderly (65+) and young (0-15)
proportions — key indicators of bus dependency.

Output
------
  data/census/ladywood_population_2021.json

Usage
-----
  python scripts/fetch_lsoa_population.py
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import requests

_REPO   = Path(__file__).parent.parent
OUT_DIR = _REPO / "data" / "census"
OUT     = OUT_DIR / "ladywood_population_2021.json"

HEADERS = {"User-Agent": "ewb-bus-routing/1.0 (EWB design challenge; educational use)"}

# Query exactly the 15 stop LSOAs by code — avoids LA filter syntax issues
_LSOA_CODES = ",".join([
    "E01013761", "E01009099", "E01009158", "E01009146", "E01009057",
    "E01009129", "E01009111", "E01009127", "E01009097", "E01009133",
    "E01009063", "E01009119", "E01009121", "E01013524", "E01009117",
])

TS001_URL = (
    f"https://www.nomisweb.co.uk/api/v01/dataset/NM_2002_1.data.csv"
    f"?geography={_LSOA_CODES}"
    f"&date=latest"
    f"&variable=1"
    f"&measures=20100"
    f"&select=geography_code,geography_name,obs_value"
)

TS007_URL = (
    f"https://www.nomisweb.co.uk/api/v01/dataset/NM_2041_1.data.csv"
    f"?geography={_LSOA_CODES}"
    f"&date=latest"
    f"&c2021_age_92=1001,1002,1003,1018,1019,1020,1021"
    f"&measures=20100"
    f"&select=geography_code,c2021_age_92_name,obs_value"
)

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


def fetch_ts001() -> dict[str, int]:
    """Total usual residents per LSOA."""
    print("Fetching TS001 (usual residents) from Nomis...")
    r = requests.get(TS001_URL, headers=HEADERS, timeout=60)
    r.raise_for_status()
    reader = csv.DictReader(io.StringIO(r.text))
    pop: dict[str, int] = {}
    for row in reader:
        code = row.get("GEOGRAPHY_CODE", "").strip()
        val  = row.get("OBS_VALUE", "").strip()
        if code.startswith("E01") and val:
            try:
                pop[code] = int(float(val))
            except ValueError:
                pass
    print(f"  Got {len(pop)} Birmingham LSOAs")
    return pop


def fetch_ts007() -> dict[str, dict]:
    """Age group counts per LSOA — returns dict of lsoa -> {age_group: count}."""
    print("Fetching TS007 (age groups) from Nomis...")
    r = requests.get(TS007_URL, headers=HEADERS, timeout=60)
    r.raise_for_status()
    reader = csv.DictReader(io.StringIO(r.text))

    ages: dict[str, dict] = {}
    for row in reader:
        code  = row.get("GEOGRAPHY_CODE", "").strip()
        label = row.get("C2021_AGE_92_NAME", "").strip().lower()
        val   = row.get("OBS_VALUE", "").strip()
        if not code.startswith("E01") or not val:
            continue
        if code not in ages:
            ages[code] = {}
        try:
            ages[code][label] = int(float(val))
        except ValueError:
            pass

    print(f"  Got age data for {len(ages)} Birmingham LSOAs")
    return ages


def run() -> dict:
    pop   = fetch_ts001()
    ages  = fetch_ts007()

    result = {}
    sep = "-" * 65

    print(f"\n{'Population & Age Structure by Stop':^65}")
    print(sep)
    print(f"  {'Stop':<5} {'Name':<30} {'Pop':>5} {'<16':>5} {'65+':>5}")
    print(f"  {'-'*5} {'-'*30} {'-'*5} {'-'*5} {'-'*5}")

    for sid, info in STOP_LSOA.items():
        lsoa = info["lsoa"]
        total = pop.get(lsoa)
        age_data = ages.get(lsoa, {})

        if total is None:
            result[sid] = {
                "lsoa": lsoa, "stop_name": info["name"],
                "note": "not in Birmingham LA download",
            }
            print(f"  {sid}  {info['name']:<30}  no data")
            continue

        # Sum elderly (65+) and young (0-15) from available age groups
        elderly = sum(v for k, v in age_data.items() if any(
            x in k for x in ["65", "66", "67", "68", "69", "70", "71", "72", "73",
                              "74", "75", "76", "77", "78", "79", "80", "81", "82",
                              "83", "84", "85", "86", "87", "88", "89", "90", "91",
                              "92", "93", "94", "95", "96", "97", "98", "99", "100"]
        ))
        young = sum(v for k, v in age_data.items() if any(
            x in k for x in ["aged 4", "aged 5", "aged 6", "aged 7", "aged 8",
                              "aged 9", "aged 10", "aged 11", "aged 12", "aged 13",
                              "aged 14", "aged 15", "aged 0", "aged 1", "aged 2", "aged 3"]
        ))

        elderly_pct = round(100 * elderly / total, 1) if total else 0
        young_pct   = round(100 * young   / total, 1) if total else 0

        result[sid] = {
            "lsoa":            lsoa,
            "stop_name":       info["name"],
            "total_population": total,
            "elderly_65plus":  elderly,
            "elderly_pct":     elderly_pct,
            "young_0to15":     young,
            "young_pct":       young_pct,
            "age_raw":         age_data,
            "data_source":     "Census 2021 TS001 + TS007 (Nomis)",
        }
        print(f"  {sid}  {info['name']:<30}  {total:>5}  {young_pct:>4.1f}%  {elderly_pct:>4.1f}%")

    print(sep)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")
    return result


if __name__ == "__main__":
    run()
