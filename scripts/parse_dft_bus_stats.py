"""
parse_dft_bus_stats.py
======================
Parses DfT bus statistics ODS files for West Midlands context data.

Files used
----------
  bus01.ods    — BUS01a (passenger journeys by metro area, years as rows)
                 BUS01e (passenger journeys by LA, years as columns)
  bus02_km.ods — BUS02d_km (vehicle-km by LA, years as columns)
  bus09.ods    — BUS09a (punctuality % on time by LA)
                 BUS09b (excess waiting time by LA)

Output
------
  data/dft/west_midlands_bus_stats.json

Usage
-----
  python scripts/parse_dft_bus_stats.py
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from odf.opendocument import load
from odf import table, text

_REPO   = Path(__file__).parent.parent
DFT_DIR = _REPO / "data" / "dft"
OUT     = DFT_DIR / "west_midlands_bus_stats.json"

_DOCS        = Path(os.path.expanduser("~")) / "Documents"
BUS01_PATH   = _DOCS / "bus01.ods"
BUS02KM_PATH = _DOCS / "bus02_km.ods"
BUS09_PATH   = _DOCS / "bus09.ods"

XML_NS = {
    'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
    'text':  'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _odf_sheet(path: Path, sheet_name: str, max_rows: int = 300) -> list[list[str]]:
    """Read an ODS sheet via odfpy. Returns list of rows (each a list of str)."""
    doc = load(path)
    for s in doc.spreadsheet.getElementsByType(table.Table):
        if s.getAttribute("name") != sheet_name:
            continue
        result = []
        for row in s.getElementsByType(table.TableRow)[:max_rows]:
            cells = row.getElementsByType(table.TableCell)
            vals = ["".join(str(p) for p in cell.getElementsByType(text.P)) for cell in cells]
            result.append(vals)
        return result
    return []


_REPEAT_ATTR = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}number-columns-repeated"
_MAX_EXPAND  = 50  # cap expansion so trailing blank cells don't bloat rows


def _expand_cells(row_el: ET.Element) -> list[str]:
    """Expand ODS table-row cells respecting number-columns-repeated."""
    vals: list[str] = []
    for cell in row_el.findall("table:table-cell", XML_NS):
        ps = cell.findall(".//text:p", XML_NS)
        v = " ".join(p.text or "" for p in ps if p.text)
        repeat = int(cell.get(_REPEAT_ATTR, "1"))
        if not v and repeat > _MAX_EXPAND:
            repeat = 1  # trailing blank padding — collapse
        vals.extend([v] * repeat)
    return vals


def _xml_sheet(path: Path, sheet_name: str, max_rows: int = 300) -> list[list[str]]:
    """Read an ODS sheet via content.xml — for oddly packaged files like bus09."""
    with zipfile.ZipFile(path) as z:
        xml_content = z.read("content.xml").decode("utf-8")
    root = ET.fromstring(xml_content)
    for sheet in root.findall(".//table:table", XML_NS):
        name = sheet.get("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}name", "")
        if name != sheet_name:
            continue
        result = []
        for row in sheet.findall("table:table-row", XML_NS)[:max_rows]:
            result.append(_expand_cells(row))
        return result
    return []


def _to_float(v: str) -> float | None:
    v = str(v).strip().replace(",", "").replace("[r]", "").replace("[p]", "").strip()
    try:
        return float(v)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# BUS01a — years as rows, regions as columns
# ---------------------------------------------------------------------------

def parse_bus01a_west_midlands() -> dict[str, float | None]:
    """West Midlands passenger journeys (millions) — years ending March."""
    rows = _odf_sheet(BUS01_PATH, "BUS01a")
    # Find header row: contains "West Midlands"
    header_idx = None
    for i, row in enumerate(rows):
        if any("West Midlands" in str(v) for v in row):
            header_idx = i
            break
    if header_idx is None:
        return {}
    header = rows[header_idx]
    wm_col = next((j for j, v in enumerate(header) if "West Midlands" in str(v)), None)
    if wm_col is None:
        return {}

    result = {}
    for row in rows[header_idx + 1:]:
        year_val = str(row[0]).strip() if row else ""
        if len(year_val) == 4 and year_val.isdigit():
            val = _to_float(row[wm_col]) if len(row) > wm_col else None
            result[year_val] = val
    return result


# ---------------------------------------------------------------------------
# BUS01e — LA code col 0, LA name col 1, year headers in row 8
# ---------------------------------------------------------------------------

def _parse_la_table(rows: list[list[str]], la_name_keyword: str) -> dict[str, float | None]:
    """
    Layout: row 8 = ['LA Code', 'LA or Region', '2010', '2011', ...]
            row 9+ = data
    """
    # Find header row (has years in columns 2+)
    header_row = None
    header_idx = 0
    for i, row in enumerate(rows):
        if len(row) > 2 and str(row[2]).strip()[:4].startswith("20") and str(row[2]).strip()[:4].isdigit():
            header_row = row
            header_idx = i
            break
    if header_row is None:
        return {}

    years = []
    year_cols = []
    for j, v in enumerate(header_row):
        s = str(v).strip()[:4]  # "2019 [r]..." -> "2019"
        if s.startswith("20") and len(s) == 4 and s.isdigit():
            years.append(s)
            year_cols.append(j)

    for row in rows[header_idx + 1:]:
        flat = " ".join(str(v) for v in row)
        if la_name_keyword.lower() in flat.lower():
            result = {}
            for yr, col in zip(years, year_cols):
                result[yr] = _to_float(row[col]) if len(row) > col else None
            return result
    return {}


def parse_bus01e_west_midlands_ca() -> dict[str, float | None]:
    """Birmingham is not a separate row; West Midlands CA is the finest granularity."""
    rows = _odf_sheet(BUS01_PATH, "BUS01e")
    return _parse_la_table(rows, "West Midlands CA")


def parse_bus02d_km_west_midlands_ca() -> dict[str, float | None]:
    """
    BUS02d_km has 3 row types per area: Commercial, Local authority support, Total.
    Col 0=code, Col 1=region, Col 2=type, Col 3+=years.
    Header row: ['LA Code', 'LA or Region', 'Type', '2010', '2011', ...]
    We want the 'Total' row for West Midlands CA (E11000005).
    """
    rows = _odf_sheet(BUS02KM_PATH, "BUS02d_km")
    # Find header: contains year columns starting at col 3
    header_row = None
    for row in rows:
        if len(row) > 3 and str(row[3]).strip()[:4].startswith("20") and str(row[3]).strip()[:4].isdigit():
            header_row = row
            break
    if header_row is None:
        return {}

    years = []
    year_cols = []
    for j, v in enumerate(header_row):
        s = str(v).strip()
        if s.startswith("20") and len(s) == 4 and s.isdigit():
            years.append(s)
            year_cols.append(j)

    for row in rows:
        flat = " ".join(str(v) for v in row)
        if "E11000005" in flat and "Total" in flat:
            result = {}
            for yr, col in zip(years, year_cols):
                result[yr] = _to_float(row[col]) if len(row) > col else None
            return result
    return {}


# ---------------------------------------------------------------------------
# BUS09 — parsed via content.xml (embedded file format)
# ---------------------------------------------------------------------------

def parse_bus09a_west_midlands() -> dict[str, float | None]:
    """BUS09a: 2 cols (code, LA name) then years. Use West Midlands CA."""
    rows = _xml_sheet(BUS09_PATH, "BUS09a")
    return _parse_la_table(rows, "West Midlands CA")


def parse_bus09b_west_midlands() -> dict[str, float | None]:
    """
    BUS09b: 3 cols (code, region, LA name) then years.
    Find the West Midlands CA row (E11000005) and parse years starting at col 3.
    """
    rows = _xml_sheet(BUS09_PATH, "BUS09b")
    # Find header row: col 3 starts with "20"
    header_row = None
    for row in rows:
        if len(row) > 3 and str(row[3]).strip()[:4].startswith("20") and str(row[3]).strip()[:4].isdigit():
            header_row = row
            break
    if header_row is None:
        return {}

    years = []
    year_cols = []
    for j, v in enumerate(header_row):
        s = str(v).strip()[:4]
        if s.startswith("20") and s.isdigit():
            years.append(s)
            year_cols.append(j)

    for row in rows:
        flat = " ".join(str(v) for v in row)
        if "E11000005" in flat or "West Midlands CA" in flat:
            result = {}
            for yr, col in zip(years, year_cols):
                result[yr] = _to_float(row[col]) if len(row) > col else None
            return result
    return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> dict:
    print("Parsing DfT bus statistics...")

    wm_journeys    = parse_bus01a_west_midlands()
    wmca_journeys  = parse_bus01e_west_midlands_ca()
    wmca_vkm       = parse_bus02d_km_west_midlands_ca()
    wm_punctuality = parse_bus09a_west_midlands()
    wm_waiting     = parse_bus09b_west_midlands()

    result = {
        "west_midlands_region_passenger_journeys_millions": wm_journeys,
        "west_midlands_ca_passenger_journeys_millions":     wmca_journeys,
        "west_midlands_ca_vehicle_km_millions":             wmca_vkm,
        "west_midlands_ca_punctuality_pct_on_time":         wm_punctuality,
        "west_midlands_ca_excess_wait_minutes":             wm_waiting,
        "data_sources": {
            "BUS01a": "DfT — Passenger journeys by metropolitan area, Great Britain, annual",
            "BUS01e": "DfT — Passenger journeys by local authority, England, annual",
            "BUS02d_km": "DfT — Vehicle kilometres by local authority, England, annual",
            "BUS09a": "DfT — Non-frequent bus services running on time by LA, England, annual",
            "BUS09b": "DfT — Average excess waiting time for frequent services by LA, England, annual",
        },
    }

    sep = "-" * 65
    recent = ["2019", "2020", "2021", "2022", "2023", "2024", "2025"]

    print(f"\n{'West Midlands Bus Statistics (DfT)':^65}")
    print(sep)

    print("\nWest Midlands passenger journeys (millions):")
    for yr in recent:
        v = wm_journeys.get(yr)
        print(f"  {yr}: {v}M" if v is not None else f"  {yr}: n/a")

    print("\nWest Midlands CA passenger journeys (millions):")
    for yr in recent:
        v = wmca_journeys.get(yr)
        print(f"  {yr}: {v}M" if v is not None else f"  {yr}: n/a")

    print("\nWest Midlands CA vehicle-km total (millions):")
    for yr in recent:
        v = wmca_vkm.get(yr)
        print(f"  {yr}: {v}M km" if v is not None else f"  {yr}: n/a")

    print("\nWest Midlands CA punctuality (% on time):")
    for yr in recent:
        v = wm_punctuality.get(yr)
        print(f"  {yr}: {v}%" if v is not None else f"  {yr}: n/a")

    print("\nWest Midlands CA excess waiting time (minutes):")
    for yr in recent:
        v = wm_waiting.get(yr)
        print(f"  {yr}: {v} min" if v is not None else f"  {yr}: n/a")

    print(sep)

    DFT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")
    return result


if __name__ == "__main__":
    run()
