"""
derive_empirical_weekend_curve.py
=================================
Fixes assumption A12 with evidence instead of a flattened guess.

The repo's weekend curves are the weekday commuter curve flattened
(Sat: x0.75 + midday boost, floor 0.30; Sun: x0.50, floor 0.15) and correlate
with observed UK weekend boardings at only r = 0.677 / 0.549. Three years of
TfL BUSTO show the real weekend shape is a single broad midday peak, stable
across years (r >= 0.998). So: derive the empirical curve from the data, and
propose it as the PROFILE_FN weekend replacement for the Ladywood model.

Outputs: empirical_weekend_curve.json (drop-in hourly factors),
         empirical_weekend_curve.png, validation numbers printed.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
BUSTO = HERE.parent / "tfl_busto_full"
YEARS = {"2023_24": "2023-2024", "2024_25": "2024-2025", "2025_26": "2025-2026"}

# Repo's current weekend derivation (from generate_map_dataset.py): weekday
# major curve, flattened + floored
WD_MAJOR = np.array([0.04, 0.02, 0.01, 0.01, 0.05, 0.18, 0.42, 0.85, 1.00,
                     0.70, 0.48, 0.50, 0.55, 0.52, 0.50, 0.62, 0.88, 0.95,
                     0.72, 0.50, 0.35, 0.28, 0.20, 0.10])
sat_old = WD_MAJOR * 0.75
sat_old[10:17] *= 1.30
REPO_OLD = {"Saturday": np.maximum(0.30, sat_old),
            "Sunday":   np.maximum(0.15, WD_MAJOR * 0.50)}

def norm(v):
    v = np.asarray(v, dtype=float)
    return v / v.max() if v.max() > 0 else v

def hourly(year_key, day):
    f = BUSTO / (f"{YEARS[year_key]}_{year_key}_{day}_TOTAL_DEMAND_BY_ROUTE_"
                 f"BY_QUARTER_HOUR_Routes_1-149.csv")
    df = pd.read_csv(f, usecols=["QHr", "Boardings"])
    df["hour"] = df["QHr"].str.slice(0, 2).astype(int)
    return df.groupby("hour")["Boardings"].sum().reindex(range(24), fill_value=0).values

def pearson(a, b):
    return float(np.corrcoef(a, b)[0, 1])

results = {}
curves = {}
for day in ["Saturday", "Sunday"]:
    per_year = {y: norm(hourly(y, day)) for y in YEARS}
    # Empirical curve = mean of the three observed years, renormalised,
    # rounded to 2 dp to match PROFILE_FN house style
    emp = norm(np.mean(list(per_year.values()), axis=0))
    emp = np.round(emp, 2)
    curves[day] = emp
    results[day.lower()] = {
        "old_flattened_curve_r_per_year":
            {y: round(pearson(REPO_OLD[day], s), 3) for y, s in per_year.items()},
        "empirical_curve_r_per_year":
            {y: round(pearson(emp, s), 3) for y, s in per_year.items()},
        "proposed_hourly_factors": [float(x) for x in emp],
    }
    old_min = min(results[day.lower()]["old_flattened_curve_r_per_year"].values())
    new_min = min(results[day.lower()]["empirical_curve_r_per_year"].values())
    print(f"{day}: flattened-weekday curve r(min) = {old_min:.3f}  ->  "
          f"empirical curve r(min) = {new_min:.3f}")

# Chart: old vs empirical vs observed years
fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), facecolor="#F5F4F0")
for ax, day in zip(axes, ["Saturday", "Sunday"]):
    ax.set_facecolor("#F5F4F0")
    for y in YEARS:
        ax.plot(range(24), norm(hourly(y, day)), color="#CCCCCC", lw=1.4)
    ax.plot(range(24), norm(REPO_OLD[day]), color="#B33A3A", lw=2.2, ls="--",
            label="current (flattened weekday)")
    ax.plot(range(24), curves[day], color="#0E7C7B", lw=2.6,
            label="proposed (empirical, 3-yr mean)")
    ax.set_title(day, fontsize=12, color="#1A1A1A", fontweight="bold")
    ax.set_xticks(range(0, 24, 4))
    ax.tick_params(colors="#6B6B6B", labelsize=8)
    for s in ax.spines.values():
        s.set_color("#CCCCCC")
    ax.legend(fontsize=8, frameon=False)
fig.suptitle("Weekend demand shape: current synthetic vs proposed empirical curve "
             "(grey = observed TfL years)", fontsize=12, color="#1A1A1A",
             fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.92])
fig.savefig(HERE / "empirical_weekend_curve.png", dpi=200)

(HERE / "empirical_weekend_curve.json").write_text(json.dumps(results, indent=2))
print("Wrote empirical_weekend_curve.json / .png")
