"""
fetch_imd_scores.py
===================
Downloads IMD 2019 File 7 (all scores, ranks, deciles) from MHCLG and
extracts sub-domain scores for the 15 Ladywood model stop LSOAs.

IMD 2019 sub-domains
--------------------
  IMD_score           — overall Index of Multiple Deprivation
  income_score        — income deprivation
  employment_score    — employment deprivation
  education_score     — education, skills & training
  health_score        — health deprivation & disability
  crime_score         — crime
  housing_score       — barriers to housing & services
  living_env_score    — living environment deprivation
  idaci_score         — income deprivation affecting children
  idaopi_score        — income deprivation affecting older people

Output
------
  data/imd/ladywood_imd_2019.json

Usage
-----
  python scripts/fetch_imd_scores.py
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import requests

_REPO   = Path(__file__).parent.parent
OUT_DIR = _REPO / "data" / "imd"
OUT     = OUT_DIR / "ladywood_imd_2019.json"

# Direct CSV download — File 7, all IoD2019 scores, ranks, deciles
IMD_CSV_URL = (
    "https://assets.publishing.service.gov.uk/media/5dc407b440f0b6379a7acc8d/"
    "File_7_-_All_IoD2019_Scores__Ranks__Deciles_and_Population_Denominators_3.csv"
)

HEADERS = {
    "User-Agent": "ewb-bus-routing/1.0 (EWB design challenge; educational use)",
    "Accept": "text/csv,*/*",
}

# Stop -> LSOA mapping
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

# Map CSV column name fragments to clean keys
COL_MAP = {
    "Index of Multiple Deprivation (IMD) Score":        "imd_score",
    "Index of Multiple Deprivation (IMD) Rank":         "imd_rank",
    "Index of Multiple Deprivation (IMD) Decile":       "imd_decile",
    "Income Score":                                      "income_score",
    "Income Rank":                                       "income_rank",
    "Employment Score":                                  "employment_score",
    "Employment Rank":                                   "employment_rank",
    "Education, Skills and Training Score":              "education_score",
    "Education, Skills and Training Rank":               "education_rank",
    "Health Deprivation and Disability Score":           "health_score",
    "Health Deprivation and Disability Rank":            "health_rank",
    "Crime Score":                                       "crime_score",
    "Crime Rank":                                        "crime_rank",
    "Barriers to Housing and Services Score":            "housing_score",
    "Barriers to Housing and Services Rank":             "housing_rank",
    "Living Environment Score":                          "living_env_score",
    "Living Environment Rank":                           "living_env_rank",
    "Income Deprivation Affecting Children Index (IDACI) Score":         "idaci_score",
    "Income Deprivation Affecting Children Index (IDACI) Rank":          "idaci_rank",
    "Income Deprivation Affecting Older People Index (IDAOPI) Score":    "idaopi_score",
    "Income Deprivation Affecting Older People Index (IDAOPI) Rank":     "idaopi_rank",
    "Total population: mid 2015":                        "population_2015",
}


def _match_col(header: str) -> str | None:
    for fragment, key in COL_MAP.items():
        if fragment.lower() in header.lower():
            return key
    return None


def download_imd() -> dict[str, dict]:
    """Download File 7 CSV and index by LSOA code."""
    print(f"Downloading IMD 2019 File 7 from MHCLG...")
    r = requests.get(IMD_CSV_URL, headers=HEADERS, timeout=120)
    r.raise_for_status()
    print(f"  Downloaded {len(r.content) / 1024:.0f} KB")

    reader = csv.DictReader(io.StringIO(r.text))
    raw_headers = reader.fieldnames or []

    # Build column mapping from actual headers
    col_index: dict[str, str] = {}
    for h in raw_headers:
        key = _match_col(h)
        if key:
            col_index[h] = key

    lsoa_data: dict[str, dict] = {}
    for row in reader:
        lsoa_code = row.get("LSOA code (2011)", "").strip()
        if not lsoa_code:
            continue
        parsed = {"lsoa_name": row.get("LSOA name (2011)", "").strip()}
        for raw_h, clean_key in col_index.items():
            v = row.get(raw_h, "").strip()
            try:
                parsed[clean_key] = float(v)
            except ValueError:
                parsed[clean_key] = None
        lsoa_data[lsoa_code] = parsed

    print(f"  Parsed {len(lsoa_data):,} England LSOAs")
    return lsoa_data


def run() -> dict:
    lsoa_data = download_imd()

    result = {}
    matched = 0

    for sid, info in STOP_LSOA.items():
        lsoa = info["lsoa"]
        row  = lsoa_data.get(lsoa)

        if row is None:
            result[sid] = {
                "lsoa": lsoa, "stop_name": info["name"],
                "note": "LSOA not found in IMD 2019",
            }
            continue

        entry = {
            "lsoa":       lsoa,
            "stop_name":  info["name"],
            "lsoa_name":  row.get("lsoa_name"),
            "data_source": "IMD 2019 (MHCLG File 7)",
        }
        for key in [
            "imd_score", "imd_rank", "imd_decile",
            "income_score", "income_rank",
            "employment_score", "employment_rank",
            "education_score", "education_rank",
            "health_score", "health_rank",
            "crime_score", "crime_rank",
            "housing_score", "housing_rank",
            "living_env_score", "living_env_rank",
            "idaci_score", "idaci_rank",
            "idaopi_score", "idaopi_rank",
            "population_2015",
        ]:
            entry[key] = row.get(key)
        result[sid] = entry
        matched += 1

    # Print summary table
    sep = "-" * 70
    print(f"\n{'IMD 2019 — Ladywood Stop Deprivation':^70}")
    print(sep)
    print(f"  {'Stop':<5} {'Name':<30} {'IMD':>6} {'Decile':>7} {'Health':>8} {'Crime':>7}")
    print(f"  {'-'*5} {'-'*30} {'-'*6} {'-'*7} {'-'*8} {'-'*7}")
    for sid in sorted(result, key=lambda s: result[s].get("imd_score") or 0, reverse=True):
        r = result[sid]
        if "imd_score" not in r or r["imd_score"] is None:
            print(f"  {sid}  {r['stop_name']:<30}  no data")
        else:
            print(
                f"  {sid}  {r['stop_name']:<30}"
                f"  {r['imd_score']:>6.1f}"
                f"  {int(r['imd_decile'] or 0):>6}d"
                f"  {r['health_score']:>8.3f}"
                f"  {r['crime_score']:>7.3f}"
            )
    print(sep)
    print(f"\nMatched {matched}/15 stops")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    return result


if __name__ == "__main__":
    run()
