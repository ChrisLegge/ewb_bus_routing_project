"""
gtfs_validate.py
================
Validates the synthetic demand model against real TfWM GTFS service frequencies.

Methodology
-----------
Service frequency (trips per time window) from the real GTFS feed is used as
a proxy for actual passenger demand: more frequent service reflects higher
ridership need and correlates with actual boardings. The synthetic model's
predicted demand is compared to this real signal at the time-window level.

Two metrics are computed per stop:
  - Pearson r: correlation between synthetic demand and real frequency profiles
  - Normalised RMSE: root-mean-squared error of the normalised curves

A high Pearson r means the synthetic model correctly predicts WHEN demand peaks;
a low nRMSE means the magnitudes are well-calibrated. Both are reported to
distinguish temporal pattern accuracy from magnitude accuracy.

Usage
-----
  python analysis/gtfs_validate.py              # print summary
  python analysis/gtfs_validate.py --json       # write analysis/outputs/gtfs_validation.json

Pre-requisites
--------------
  1. python scripts/gtfs_service_profile.py   (produces data/gtfs/service_profile.json)
  2. python "prediction model/generate_map_dataset.py"   (produces data/synthetic/map_demand_dataset.csv)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

_REPO = Path(__file__).parent.parent

TIME_WINDOWS = [
    "Early Morning", "AM Peak", "Mid Morning", "Lunch",
    "Afternoon", "PM Peak", "Evening", "Night",
]

MODEL_STOP_NAMES = {
    "S01": "New Street Station",     "S02": "Spring St",
    "S03": "Jewellery Quarter Stn",  "S04": "Soho Hill",
    "S05": "Five Ways (Metro)",      "S06": "Dudley Rd",
    "S07": "Five Ways Station",      "S08": "Icknield Port Rd",
    "S09": "Belgrave Interchange",   "S10": "Ladywood Fire Station",
    "S11": "Edgbaston Village Metro","S12": "Summerfield Park",
    "S13": "City Rd Medical Centre", "S14": "Mencap Centre",
    "S15": "Summerfield Crescent",
}


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    num   = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denom = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / denom if denom else float("nan")


def _nrmse(xs: list[float], ys: list[float]) -> float:
    """Normalised RMSE: RMSE / range(ys).  Lower = better calibrated magnitude."""
    if not xs:
        return float("nan")
    mse  = sum((x - y) ** 2 for x, y in zip(xs, ys)) / len(xs)
    rng  = max(ys) - min(ys)
    return math.sqrt(mse) / rng if rng else float("nan")


def _normalise(vals: list[float]) -> list[float]:
    mx = max(vals) or 1.0
    return [v / mx for v in vals]


def load_service_profile() -> dict:
    path = _REPO / "data" / "gtfs" / "service_profile.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found — run 'python scripts/gtfs_service_profile.py' first."
        )
    return json.loads(path.read_text())


def load_synthetic_demand() -> dict[str, dict[str, dict[str, float]]]:
    """
    Returns: stop_id → day_type → time_window → mean boardings
    Averaged over all rows in the synthetic dataset (ignoring weather/event variation
    to get the underlying temporal signal).
    """
    path = _REPO / "data" / "synthetic" / "map_demand_dataset.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found — run 'python prediction model/generate_map_dataset.py' first."
        )

    time_window_for_hour: dict[int, str] = {}
    for tw, hours in {
        "Early Morning": range(5,  7),  "AM Peak":   range(7,  9),
        "Mid Morning":   range(9,  11), "Lunch":     range(11, 13),
        "Afternoon":     range(13, 16), "PM Peak":   range(16, 18),
        "Evening":       range(18, 21), "Night":     range(21, 24),
    }.items():
        for h in hours:
            time_window_for_hour[h] = tw

    # Accumulate sums and counts
    sums:   dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(float))
    )
    cnts: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )

    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sid  = row["stop_id"]
            dt   = row.get("day_type", "weekday")
            hour = int(float(row.get("hour", 0)))
            tw   = time_window_for_hour.get(hour)
            if tw is None:
                continue
            board = float(row.get("boardings", 0))
            sums[sid][dt][tw]  += board
            cnts[sid][dt][tw]  += 1

    result: dict[str, dict[str, dict[str, float]]] = {}
    for sid, day_map in sums.items():
        result[sid] = {}
        for dt, tw_map in day_map.items():
            result[sid][dt] = {
                tw: sums[sid][dt][tw] / cnts[sid][dt][tw]
                for tw in tw_map
            }
    return result


def run_analysis() -> dict:
    profile  = load_service_profile()
    synth    = load_synthetic_demand()

    results = []
    for sid in sorted(MODEL_STOP_NAMES):
        gtfs_info = profile.get(sid, {})
        if not gtfs_info or "time_windows" not in gtfs_info:
            continue

        for day_type in ("weekday", "saturday", "sunday"):
            gtfs_tw  = gtfs_info["time_windows"].get(day_type, {})
            synth_tw = synth.get(sid, {}).get(day_type, {})

            # Only compare windows present in both
            shared_tw = [tw for tw in TIME_WINDOWS if tw in gtfs_tw and tw in synth_tw]
            if len(shared_tw) < 3:
                continue

            gtfs_vals  = [float(gtfs_tw[tw])  for tw in shared_tw]
            synth_vals = [synth_tw[tw]          for tw in shared_tw]

            if max(gtfs_vals) == 0:
                continue

            gtfs_norm  = _normalise(gtfs_vals)
            synth_norm = _normalise(synth_vals)

            r    = _pearson(synth_norm, gtfs_norm)
            nrms = _nrmse(synth_norm, gtfs_norm)

            # Peak window alignment
            gtfs_peak  = shared_tw[gtfs_norm.index(max(gtfs_norm))]
            synth_peak = shared_tw[synth_norm.index(max(synth_norm))]

            results.append({
                "stop_id":         sid,
                "stop_name":       MODEL_STOP_NAMES[sid],
                "gtfs_stop":       gtfs_info.get("gtfs_stop_name", ""),
                "match_distance_m": gtfs_info.get("distance_m", None),
                "day_type":        day_type,
                "pearson_r":       round(r,    3) if not math.isnan(r)    else None,
                "nrmse":           round(nrms, 3) if not math.isnan(nrms) else None,
                "gtfs_peak_window":  gtfs_peak,
                "synth_peak_window": synth_peak,
                "peak_aligned":    gtfs_peak == synth_peak,
                "gtfs_profile":    {tw: gtfs_tw.get(tw, 0)  for tw in TIME_WINDOWS},
                "synth_profile":   {tw: round(synth_tw.get(tw, 0), 1) for tw in TIME_WINDOWS},
            })

    weekday_results = [r for r in results if r["day_type"] == "weekday"]
    valid_r = [r["pearson_r"] for r in weekday_results if r["pearson_r"] is not None]
    valid_nrmse = [r["nrmse"] for r in weekday_results if r["nrmse"] is not None]
    peak_aligned = [r for r in weekday_results if r["peak_aligned"]]

    return {
        "results":  results,
        "summary": {
            "n_stops_validated":               len(weekday_results),
            "mean_pearson_r_weekday":          round(sum(valid_r) / len(valid_r), 3) if valid_r else None,
            "min_pearson_r_weekday":           round(min(valid_r), 3)                if valid_r else None,
            "mean_nrmse_weekday":              round(sum(valid_nrmse) / len(valid_nrmse), 3) if valid_nrmse else None,
            "peak_window_alignment_pct":       round(100 * len(peak_aligned) / len(weekday_results), 1) if weekday_results else 0,
            "stops_with_strong_correlation":   [r["stop_id"] for r in weekday_results if (r["pearson_r"] or 0) >= 0.8],
            "stops_needing_recalibration":     [r["stop_id"] for r in weekday_results if (r["pearson_r"] or 1) < 0.5],
        },
        "methodology": (
            "GTFS service frequency (trips per time window) used as demand proxy. "
            "Pearson r measures temporal pattern agreement; nRMSE measures magnitude calibration. "
            "Both computed on min-max normalised profiles to separate shape from scale."
        ),
        "data_source": "TfWM GTFS feed (data/gtfs/tfwm_gtfs.zip) — routes 8/8A/8C/80/126",
    }


def print_summary(result: dict) -> None:
    s = result["summary"]
    sep = "-" * 65
    print(f"\n{'GTFS Validation - Synthetic Model vs Real Service Frequency':^65}")
    print(sep)
    print(f"  Stops validated:          {s['n_stops_validated']}")
    print(f"  Mean Pearson r (weekday): {s['mean_pearson_r_weekday']}")
    print(f"  Min  Pearson r (weekday): {s['min_pearson_r_weekday']}")
    print(f"  Mean nRMSE     (weekday): {s['mean_nrmse_weekday']}")
    print(f"  Peak window aligned:      {s['peak_window_alignment_pct']}%")
    if s["stops_needing_recalibration"]:
        print(f"\n  Stops flagged for recalibration: {s['stops_needing_recalibration']}")
    print()

    weekday = [r for r in result["results"] if r["day_type"] == "weekday"]
    weekday.sort(key=lambda x: x["pearson_r"] or 0)
    print(f"  {'Stop':<6} {'Name':<28} {'r':>6}  {'nRMSE':>6}  {'GTFS peak':<14} {'Synth peak':<14} Aligned")
    print(f"  {'-'*6} {'-'*28} {'-'*6}  {'-'*6}  {'-'*14} {'-'*14} -----")
    for r in weekday:
        aligned = "Y" if r["peak_aligned"] else "N"
        print(
            f"  {r['stop_id']:<6} {r['stop_name']:<28} "
            f"{str(r['pearson_r']):>6}  {str(r['nrmse']):>6}  "
            f"{r['gtfs_peak_window']:<14} {r['synth_peak_window']:<14} {aligned}"
        )
    print(sep)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run_analysis()
    print_summary(result)

    if args.json:
        out_dir = Path(__file__).parent / "outputs"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "gtfs_validation.json"
        out_path.write_text(json.dumps(result, indent=2))
        print(f"\nWrote {out_path}")
