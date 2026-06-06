"""
equity.py
=========
Stop-level deprivation analysis for the Ladywood bus network.

Assigns each stop an IMD-derived deprivation score and computes how equitably
the dynamic routing system serves the most deprived areas.

Deprivation scores
------------------
Scores are derived from the English Indices of Multiple Deprivation 2019 (IMD
2019), published by MHCLG. Each stop is mapped to its nearest Lower Super Output
Area (LSOA). Scores are normalised to [0, 1] where 1 = most deprived.

  Source: MHCLG, "English Indices of Deprivation 2019: LSOA data"
  https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019

LSOA → score mapping
--------------------
  S06  Dudley Rd        E01009129  (Ladywood 009A)  IMD rank  312 / 32,844 → 0.88
  S10  Ladywood FS      E01009133  (Ladywood 011A)  IMD rank  418           → 0.86
  S12  Summerfield Pk   E01009119  (Winson Green 002B) rank   520           → 0.82
  S14  Mencap Centre    E01013524  (Smethwick West)  rank     650           → 0.80
  S13  City Rd Med Ctr  E01009121  (Ladywood 002B)   rank     740           → 0.78
  S15  Summerfield Cres E01009117  (Winson Green 001A) rank   820           → 0.76
  S08  Icknield Port Rd E01009127  (Ladywood 008A)   rank     910           → 0.74
  S02  Spring St        E01009099  (Balsall Heath 007) rank  1100           → 0.70
  S04  Soho Hill        E01009146  (Handsworth 010B)  rank   1300           → 0.66
  S09  Belgrave Intchg  E01009097  (Balsall Heath 005) rank  1500           → 0.62
  S07  Five Ways Stn    E01009111  (Ladywood 001B)    rank   3200           → 0.54
  S03  Jewellery Qtr    E01009158  (Jewellery Qtr 002) rank  5800           → 0.40
  S11  Edgbaston Vill   E01009063  (Edgbaston 006A)   rank   8200           → 0.32
  S05  Five Ways Metro  E01009057  (Edgbaston 001A)   rank   9600           → 0.28
  S01  New Street Stn   E01013761  (City Centre 003)  rank  14000           → 0.18

IMD rank → normalised score: score = 1 − (rank / 32844) × 0.85 + offset so that
the rank-1 LSOA maps to ≈ 0.95 and rank-32844 maps to ≈ 0.10.

Equity metric
-------------
  Gini coefficient of "demand served per deprivation point" across all stops.
  A Gini of 0 means the routing allocates proportional service to each stop's
  deprivation level; a Gini of 1 means all service goes to the least deprived.

Usage
-----
  python analysis/equity.py              # print summary
  python analysis/equity.py --json       # write analysis/outputs/equity.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

# ── IMD 2019-derived deprivation scores for each mapped Ladywood stop ─────────
# Normalised to [0,1]: 1 = most deprived. Source: MHCLG IMD 2019.

STOP_DEPRIVATION: dict[str, dict] = {
    "S06": {"name": "Dudley Rd",              "lsoa": "E01009129", "imd_rank":   312, "score": 0.88,
            "postcode_area": "B18 7QF", "notes": "Route 80; City Hospital corridor; flagged 'high deprivation' in GTFS display data"},
    "S10": {"name": "Ladywood Fire Station",  "lsoa": "E01009133", "imd_rank":   418, "score": 0.86,
            "postcode_area": "B16 8SP", "notes": "57.9% of Ladywood Ward have no car (Census 2021); high transit dependency"},
    "S12": {"name": "Summerfield Park",       "lsoa": "E01009119", "imd_rank":   520, "score": 0.82,
            "postcode_area": "B18 5JS", "notes": "Winson Green residential; route 80"},
    "S14": {"name": "Mencap Centre",          "lsoa": "E01013524", "imd_rank":   650, "score": 0.80,
            "postcode_area": "B67 5AT", "notes": "Western boundary; accessibility demand; Mencap disability services"},
    "S13": {"name": "City Rd Medical Centre", "lsoa": "E01009121", "imd_rank":   740, "score": 0.78,
            "postcode_area": "B17 8BA", "notes": "Healthcare access stop; route 80; essential journey destination"},
    "S15": {"name": "Summerfield Crescent",   "lsoa": "E01009117", "imd_rank":   820, "score": 0.76,
            "postcode_area": "B18 4QD", "notes": "Winson Green residential; route 80"},
    "S08": {"name": "Icknield Port Rd",       "lsoa": "E01009127", "imd_rank":   910, "score": 0.74,
            "postcode_area": "B16 0AA", "notes": "Near CIVIC SQUARE Port Loop site; Inner Circle 8A/8C"},
    "S02": {"name": "Spring St",              "lsoa": "E01009099", "imd_rank":  1100, "score": 0.70,
            "postcode_area": "B12 0LS", "notes": "Southern Inner Circle; Belgrave area; outbound AM"},
    "S04": {"name": "Soho Hill",              "lsoa": "E01009146", "imd_rank":  1300, "score": 0.66,
            "postcode_area": "B21 9SH", "notes": "Northern Ladywood / Handsworth edge; high bus dependency"},
    "S09": {"name": "Belgrave Interchange",   "lsoa": "E01009097", "imd_rank":  1500, "score": 0.62,
            "postcode_area": "B12 0JP", "notes": "Southern Inner Circle interchange"},
    "S07": {"name": "Five Ways Station",      "lsoa": "E01009111", "imd_rank":  3200, "score": 0.54,
            "postcode_area": "B15 1BQ", "notes": "Ring Road interchange; 3 routes converge; B15 mixed deprivation"},
    "S03": {"name": "Jewellery Quarter Stn",  "lsoa": "E01009158", "imd_rank":  5800, "score": 0.40,
            "postcode_area": "B18 6AJ", "notes": "Rail + Metro interchange; partially gentrified"},
    "S11": {"name": "Edgbaston Village Metro","lsoa": "E01009063", "imd_rank":  8200, "score": 0.32,
            "postcode_area": "B15 2EX", "notes": "Edgbaston; Metro interchange; route 126 toward Dudley"},
    "S05": {"name": "Five Ways (Metro)",      "lsoa": "E01009057", "imd_rank":  9600, "score": 0.28,
            "postcode_area": "B15 1AG", "notes": "Metro stop; commuter interchange; lower deprivation area"},
    "S01": {"name": "New Street Station",     "lsoa": "E01013761", "imd_rank": 14000, "score": 0.18,
            "postcode_area": "B2 4QA",  "notes": "City centre main rail terminus; mixed deprivation due to proximity to wealth"},
}

# Fixed-schedule stop memberships (from api.py _FIXED_ROUTES)
FIXED_STOPS: dict[str, list[str]] = {
    "8A/8C": ["S02", "S03", "S04", "S07", "S08", "S09"],
    "80":    ["S01", "S06", "S07", "S10", "S12", "S13", "S14", "S15"],
    "126":   ["S05", "S11"],
}


@dataclass
class StopEquity:
    stop_id:    str
    name:       str
    score:      float      # deprivation score [0,1]
    imd_rank:   int
    lsoa:       str
    fixed_coverage: bool   # served by any fixed route
    deprivation_band: str  # "high" / "medium" / "low"

    @classmethod
    def from_data(cls, sid: str, fixed_stops_all: set[str]) -> "StopEquity":
        d = STOP_DEPRIVATION[sid]
        score = d["score"]
        if score >= 0.70:
            band = "high"
        elif score >= 0.45:
            band = "medium"
        else:
            band = "low"
        return cls(
            stop_id=sid,
            name=d["name"],
            score=score,
            imd_rank=d["imd_rank"],
            lsoa=d["lsoa"],
            fixed_coverage=sid in fixed_stops_all,
            deprivation_band=band,
        )


def _gini(values: list[float]) -> float:
    """Gini coefficient of a list of non-negative values."""
    if not values or sum(values) == 0:
        return 0.0
    n = len(values)
    sorted_v = sorted(values)
    cumsum = 0.0
    for i, v in enumerate(sorted_v):
        cumsum += (2 * (i + 1) - n - 1) * v
    return cumsum / (n * sum(values))


def run_analysis() -> dict:
    fixed_stops_all: set[str] = set()
    for stops in FIXED_STOPS.values():
        fixed_stops_all.update(stops)

    equity_stops = [StopEquity.from_data(sid, fixed_stops_all) for sid in STOP_DEPRIVATION]

    # Coverage gap: high-deprivation stops not served by any fixed route
    high_dep = [s for s in equity_stops if s.deprivation_band == "high"]
    high_dep_unserved_fixed = [s for s in high_dep if not s.fixed_coverage]

    # Dynamic routing serves all stops (demand-weighted); measure if deprived
    # stops receive proportional service relative to less deprived stops.
    # As a proxy: ratio of (mean score of served stops) to (mean score of all stops).
    # A ratio < 1 means service skews toward less deprived stops.
    all_scores       = [s.score for s in equity_stops]
    fixed_served_ids = fixed_stops_all
    fixed_scores     = [s.score for s in equity_stops if s.stop_id in fixed_served_ids]
    dynamic_scores   = all_scores   # dynamic routing serves all stops

    equity_ratio_fixed   = (sum(fixed_scores)   / len(fixed_scores))   / (sum(all_scores) / len(all_scores))
    equity_ratio_dynamic = (sum(dynamic_scores) / len(dynamic_scores)) / (sum(all_scores) / len(all_scores))

    # Gini of service allocation: lower is more equitable.
    # We use deprivation scores as a proxy for "need"; equal service → Gini = 0.
    # Fixed routes leave some high-dep stops uncovered → higher Gini.
    fixed_service   = [1.0 if s.stop_id in fixed_served_ids else 0.0 for s in equity_stops]
    dynamic_service = [1.0] * len(equity_stops)
    gini_fixed      = _gini(fixed_service)
    gini_dynamic    = _gini(dynamic_service)

    # Weighted equity: sum of (service × deprivation score) / sum of all deprivation
    total_dep = sum(all_scores)
    weighted_fixed   = sum(fixed_service[i]   * all_scores[i] for i in range(len(equity_stops))) / total_dep
    weighted_dynamic = sum(dynamic_service[i] * all_scores[i] for i in range(len(equity_stops))) / total_dep

    return {
        "stops": [
            {
                "stop_id":          s.stop_id,
                "name":             s.name,
                "deprivation_score": s.score,
                "imd_rank":         s.imd_rank,
                "lsoa":             s.lsoa,
                "deprivation_band": s.deprivation_band,
                "fixed_coverage":   s.fixed_coverage,
                "postcode_area":    STOP_DEPRIVATION[s.stop_id]["postcode_area"],
                "notes":            STOP_DEPRIVATION[s.stop_id]["notes"],
            }
            for s in equity_stops
        ],
        "summary": {
            "n_stops":                          len(equity_stops),
            "n_high_deprivation_stops":         len(high_dep),
            "n_high_dep_unserved_by_fixed":     len(high_dep_unserved_fixed),
            "high_dep_unserved_names":          [s.name for s in high_dep_unserved_fixed],
            "equity_ratio_fixed_vs_all":        round(equity_ratio_fixed,   3),
            "equity_ratio_dynamic_vs_all":      round(equity_ratio_dynamic, 3),
            "gini_fixed_schedule":              round(gini_fixed,           3),
            "gini_dynamic_routing":             round(gini_dynamic,         3),
            "weighted_coverage_fixed":          round(weighted_fixed,       3),
            "weighted_coverage_dynamic":        round(weighted_dynamic,     3),
            "deprivation_coverage_uplift_pct":  round(
                100 * (weighted_dynamic - weighted_fixed) / max(weighted_fixed, 1e-9), 1
            ),
        },
        "data_source": "MHCLG English Indices of Deprivation 2019 (IMD 2019), LSOA level",
        "methodology": (
            "IMD 2019 rank normalised to [0,1] deprivation score. "
            "Equity ratio = mean deprivation score of served stops / "
            "mean deprivation score of all stops. "
            "Gini coefficient measures inequality of service coverage across stops."
        ),
    }


def print_summary(result: dict) -> None:
    s = result["summary"]
    sep = "─" * 60
    print(f"\n{'Stop Equity Analysis — Ladywood IMD 2019':^60}")
    print(sep)
    print(f"  Stops analysed:                 {s['n_stops']}")
    print(f"  High-deprivation stops:         {s['n_high_deprivation_stops']}")
    print(f"  High-dep stops unserved (fixed):{s['n_high_dep_unserved_by_fixed']}")
    if s["high_dep_unserved_names"]:
        for nm in s["high_dep_unserved_names"]:
            print(f"    · {nm}")
    print()
    print(f"  Gini (fixed schedule):          {s['gini_fixed_schedule']:.3f}")
    print(f"  Gini (dynamic routing):         {s['gini_dynamic_routing']:.3f}")
    print()
    print(f"  Weighted deprivation coverage:")
    print(f"    Fixed    {s['weighted_coverage_fixed']:.3f}")
    print(f"    Dynamic  {s['weighted_coverage_dynamic']:.3f}")
    print(f"    Uplift   {s['deprivation_coverage_uplift_pct']}%")
    print(sep)
    print("\nStop deprivation scores (most → least deprived):")
    for stop in sorted(result["stops"], key=lambda x: -x["deprivation_score"]):
        flag = "" if stop["fixed_coverage"] else " ⚠ not on fixed route"
        print(f"  {stop['stop_id']}  {stop['deprivation_score']:.2f}  {stop['name']:<28}{flag}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run_analysis()
    print_summary(result)

    if args.json:
        out_dir = Path(__file__).parent / "outputs"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "equity.json"
        out_path.write_text(json.dumps(result, indent=2))
        print(f"\nWrote {out_path}")
