"""
recalibrate_base_demand.py
==========================
Uses the real GTFS service profile to recalibrate the base demand values in
generate_map_dataset.py, anchoring the synthetic dataset to actual bus service
frequencies.

Method
------
For each model stop, the GTFS service profile gives the total weekly trip count
(weekday×5 + saturday + sunday) as a measure of revealed service need. The
ratio of GTFS weekly trips across stops is used to rescale the existing `base`
demand values while preserving their relative ordering (major > medium > minor).
The rescaling is additive-then-multiplicative to prevent the minor stops from
collapsing to zero.

The script prints a diff of old vs new base values, then optionally writes the
change directly into generate_map_dataset.py.

Usage
-----
  python scripts/recalibrate_base_demand.py           # dry-run: print only
  python scripts/recalibrate_base_demand.py --apply   # patch generate_map_dataset.py

Pre-requisites
--------------
  python scripts/gtfs_service_profile.py
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_REPO = Path(__file__).parent.parent

# Current base demand values from generate_map_dataset.py (kept here for reference)
CURRENT_BASE: dict[str, int] = {
    "S01": 90, "S03": 78, "S07": 82, "S09": 67,   # major
    "S04": 44, "S08": 42, "S11": 36, "S12": 30,   # medium
    "S02": 14, "S05": 11, "S06":  9, "S10":  8,   # minor
    "S13": 17, "S14":  7, "S15":  9,
}

# Importance tier — preserve relative ordering within tiers
IMPORTANCE: dict[str, str] = {
    "S01": "major",  "S03": "major",  "S07": "major",  "S09": "major",
    "S04": "medium", "S08": "medium", "S11": "medium", "S12": "medium",
    "S02": "minor",  "S05": "minor",  "S06": "minor",  "S10": "minor",
    "S13": "minor",  "S14": "minor",  "S15": "minor",
}

# Tier ranges for clamping (from original dataset docstring)
TIER_RANGE: dict[str, tuple[int, int]] = {
    "major":  (60, 100),
    "medium": (25,  55),
    "minor":  ( 5,  22),
}


def _weekly_trips(profile: dict, sid: str) -> float:
    tw = profile.get(sid, {}).get("time_windows", {})
    wd = sum(tw.get("weekday",  {}).values()) * 5
    sa = sum(tw.get("saturday", {}).values())
    su = sum(tw.get("sunday",   {}).values())
    return wd + sa + su


def compute_new_bases(profile: dict) -> dict[str, int]:
    weekly = {sid: _weekly_trips(profile, sid) for sid in CURRENT_BASE}
    max_weekly = max(weekly.values()) or 1.0

    # GTFS-derived target ratio for each stop (0-1 scale)
    gtfs_ratio = {sid: weekly[sid] / max_weekly for sid in CURRENT_BASE}

    # Blend: 60% anchored to GTFS ratio, 40% preserve original base
    # This avoids over-correcting for stops where GTFS match is approximate
    orig_max = max(CURRENT_BASE.values())
    new_bases: dict[str, int] = {}
    for sid in CURRENT_BASE:
        orig_norm = CURRENT_BASE[sid] / orig_max
        blended   = 0.60 * gtfs_ratio[sid] + 0.40 * orig_norm
        tier      = IMPORTANCE[sid]
        lo, hi    = TIER_RANGE[tier]
        raw       = lo + blended * (hi - lo)
        new_bases[sid] = max(lo, min(hi, round(raw)))

    return new_bases


def print_diff(new_bases: dict[str, int], profile: dict) -> None:
    sep = "-" * 65
    print(f"\n{'Base Demand Recalibration (GTFS-anchored)':^65}")
    print(sep)
    print(f"  {'Stop':<6} {'Name':<28} {'Old':>5} {'New':>5} {'Diff':>5}  {'GTFS wkly trips':>15}")
    print(f"  {'-'*6} {'-'*28} {'-'*5} {'-'*5} {'-'*5}  {'-'*15}")

    names = {
        "S01": "New Street Station",     "S02": "Spring St",
        "S03": "Jewellery Quarter Stn",  "S04": "Soho Hill",
        "S05": "Five Ways (Metro)",      "S06": "Dudley Rd",
        "S07": "Five Ways Station",      "S08": "Icknield Port Rd",
        "S09": "Belgrave Interchange",   "S10": "Ladywood Fire Station",
        "S11": "Edgbaston Village Metro","S12": "Summerfield Park",
        "S13": "City Rd Medical Centre", "S14": "Mencap Centre",
        "S15": "Summerfield Crescent",
    }
    total_delta = 0
    for sid in sorted(CURRENT_BASE):
        old  = CURRENT_BASE[sid]
        new  = new_bases[sid]
        wkly = _weekly_trips(profile, sid)
        delta = new - old
        total_delta += abs(delta)
        arrow = "+" if delta > 0 else ("-" if delta < 0 else " ")
        print(f"  {sid:<6} {names[sid]:<28} {old:>5} {new:>5} {arrow}{abs(delta):>4}  {wkly:>15.0f}")
    print(f"\n  Total absolute change: {total_delta} boardings across 15 stops")
    print(sep)


def _patch_generate_map_dataset(new_bases: dict[str, int]) -> None:
    """Rewrite the STOPS list in generate_map_dataset.py with updated base values."""
    target = _REPO / "prediction model" / "generate_map_dataset.py"
    src = target.read_text(encoding="utf-8")

    def replacer(m: re.Match) -> str:
        sid = m.group(1)
        if sid in new_bases:
            return m.group(0).replace(
                f'"base": {int(m.group(2))}',
                f'"base": {new_bases[sid]}',
            )
        return m.group(0)

    # Match lines like: {"id": "S01", ..., "base": 90}
    patched = re.sub(
        r'"id":\s*"(S\d+)".*?"base":\s*(\d+)',
        replacer,
        src,
        flags=re.DOTALL,
    )

    if patched == src:
        print("No changes made — pattern not matched. Edit generate_map_dataset.py manually.")
        return

    target.write_text(patched, encoding="utf-8")
    print(f"Patched {target}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Write changes to generate_map_dataset.py (default: dry-run only)")
    args = parser.parse_args()

    profile_path = _REPO / "data" / "gtfs" / "service_profile.json"
    if not profile_path.exists():
        raise FileNotFoundError(
            "data/gtfs/service_profile.json not found. "
            "Run 'python scripts/gtfs_service_profile.py' first."
        )
    profile = json.loads(profile_path.read_text())

    new_bases = compute_new_bases(profile)
    print_diff(new_bases, profile)

    if args.apply:
        _patch_generate_map_dataset(new_bases)
        print("\nRerun 'python prediction model/generate_map_dataset.py' to regenerate the dataset.")
    else:
        print("\nDry run — pass --apply to patch generate_map_dataset.py.")
