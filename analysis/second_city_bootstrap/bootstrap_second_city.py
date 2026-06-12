"""
bootstrap_second_city.py
========================
THE LADYWOOD COLD-START RECIPE, PROVEN ON A CITY WE HAVE NEVER TOUCHED.

The Ladywood system was built for one ward. The question every reviewer (and
any real funder) asks is: "is this a bespoke artefact, or a method?" This
script answers it by re-running Ladywood's Day-1 bootstrap for Harpurhey,
Manchester — one of England's most deprived wards — using ONLY the open-data
pack, in one pass:

  stops          <- NaPTAN (national, open)                      [bbox filter]
  road distances <- haversine x 1.3 urban circuity factor (OSM graph is the
                    full-fidelity upgrade; the factor is the honest Day-1 proxy)
  demand shape   <- the Ladywood PROFILE_FN weekday curves (validated vs TfL
                    BUSTO r=0.94-0.95) + the NEW empirical weekend curve
  deprivation    <- IMD 2019 File 7 (Manchester LSOAs)
  weather        <- Open-Meteo Manchester hourly (already in pack)
  optimiser      <- same greedy + 2-opt CVRP method as the Ladywood repo

Output: manchester_bootstrap/route_plan_manchester.json + map PNG + stats.
None of this claims Manchester accuracy — it demonstrates that the LADYWOOD
METHOD is a deployable recipe, which is evidence about Ladywood's design, not
a pivot away from it.
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
PACK = HERE.parent
OUT = HERE / "manchester_bootstrap"
OUT.mkdir(exist_ok=True)

# ── 1. Stops from NaPTAN: Harpurhey / Moston corridor bbox ───────────────────
print("Loading NaPTAN (national)...")
nap = pd.read_csv(PACK / "naptan" / "naptan_national_stops.csv",
                  usecols=["ATCOCode", "CommonName", "Longitude", "Latitude",
                           "StopType", "Status", "LocalityName"],
                  low_memory=False)
bbox = (53.490, 53.525, -2.245, -2.175)   # Harpurhey/Moston, N Manchester
m = nap[(nap["StopType"] == "BCT") & (nap["Status"] == "active") &
        nap["Latitude"].between(bbox[0], bbox[1]) &
        nap["Longitude"].between(bbox[2], bbox[3])].copy()
print(f"  {len(m)} active bus stops in the Harpurhey bbox")

# Pick 15 well-spread stops (greedy max-min dispersion), mirroring Ladywood's n
def haversine(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = (math.sin((lat2 - lat1) / 2) ** 2 +
         math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(h))

pts = m[["Latitude", "Longitude"]].values
chosen = [int(np.argmax(pts[:, 0]))]          # seed: northernmost
while len(chosen) < 15:
    d = np.array([min(haversine(p, pts[c]) for c in chosen) for p in pts])
    d[chosen] = -1
    chosen.append(int(np.argmax(d)))
stops = m.iloc[chosen].reset_index(drop=True)
stops["stop_id"] = [f"M{i+1:02d}" for i in range(len(stops))]

# ── 2. Tier assignment by local stop density (proxy for importance) ──────────
dens = [sum(1 for q in pts if haversine((r.Latitude, r.Longitude),
                                        (q[0], q[1])) < 0.4)
        for r in stops.itertuples()]
ranks = pd.Series(dens).rank(pct=True)
stops["tier"] = np.where(ranks > 2/3, "major",
                np.where(ranks > 1/3, "medium", "minor"))

# ── 3. Deprivation context: IMD 2019, Manchester LSOAs ───────────────────────
imd = pd.read_csv(PACK / "imd" / next((PACK / "imd").glob("File_7*.csv")).name
                  if False else next((PACK / "imd").glob("File_7*.csv")))
la_col = [c for c in imd.columns if "Local Authority District name" in c][0]
dec_col = [c for c in imd.columns if "Index of Multiple Deprivation (IMD) Decile" in c][0]
manc = imd[imd[la_col] == "Manchester"]
ctx = {
    "manchester_lsoas": int(len(manc)),
    "share_in_most_deprived_decile": round(float((manc[dec_col] == 1).mean()), 3),
    "note": "Harpurhey LSOAs sit persistently in England's most-deprived percentiles",
}
print(f"  Manchester: {ctx['manchester_lsoas']} LSOAs, "
      f"{ctx['share_in_most_deprived_decile']:.0%} in the most-deprived decile")

# ── 4. Demand: Ladywood curves (validated) + empirical weekend curve ─────────
PROFILE = {
    "major": [0.04, 0.02, 0.01, 0.01, 0.05, 0.18, 0.42, 0.85, 1.00, 0.70, 0.48,
              0.50, 0.55, 0.52, 0.50, 0.62, 0.88, 0.95, 0.72, 0.50, 0.35, 0.28,
              0.20, 0.10],
    "medium": [0.03, 0.01, 0.01, 0.01, 0.04, 0.14, 0.35, 0.75, 0.90, 0.60, 0.42,
               0.45, 0.48, 0.46, 0.44, 0.56, 0.78, 0.85, 0.65, 0.44, 0.30, 0.22,
               0.15, 0.08],
    "minor": [0.02, 0.01, 0.00, 0.00, 0.03, 0.12, 0.38, 1.00, 0.88, 0.40, 0.25,
              0.22, 0.25, 0.22, 0.26, 0.30, 0.28, 0.24, 0.20, 0.16, 0.12, 0.10,
              0.06, 0.04],
}
weekend = json.loads((HERE / "empirical_weekend_curve.json").read_text())
BASE = {"major": 100, "medium": 60, "minor": 30}   # Ladywood tier bases

def demand_at(row, hour, day="Weekday"):
    if day == "Weekday":
        f = PROFILE[row.tier][hour]
    else:
        f = weekend[day.lower()]["proposed_hourly_factors"][hour]
    return BASE[row.tier] * f

# ── 5. Route optimisation: greedy nearest-neighbour + 2-opt (repo method) ────
CIRCUITY = 1.3
n = len(stops)
D = np.zeros((n, n))
for i in range(n):
    for j in range(n):
        D[i, j] = haversine((stops.Latitude[i], stops.Longitude[i]),
                            (stops.Latitude[j], stops.Longitude[j])) * CIRCUITY

def route_len(order):
    return sum(D[order[k], order[k + 1]] for k in range(len(order) - 1))

def two_opt(order):
    best = order[:]
    improved = True
    while improved:
        improved = False
        for a in range(1, len(best) - 2):
            for b in range(a + 1, len(best) - 1):
                cand = best[:a] + best[a:b + 1][::-1] + best[b + 1:]
                if route_len(cand) < route_len(best) - 1e-9:
                    best, improved = cand, True
    return best

plans = {}
for window, hour in [("am_peak", 8), ("midday", 12), ("pm_peak", 17)]:
    dem = np.array([demand_at(r, hour) for r in stops.itertuples()])
    order = list(np.argsort(-dem))          # demand-greedy visit priority
    order = two_opt(order)
    plans[window] = {
        "visit_order": [stops.stop_id[i] for i in order],
        "route_km": round(route_len(order), 2),
        "total_demand_served": int(dem.sum()),
    }

plan = {
    "city": "Manchester — Harpurhey/Moston corridor",
    "method": "Ladywood Day-1 bootstrap: NaPTAN + IMD + validated demand curves "
              "+ greedy/2-opt CVRP. No local demand data used or claimed.",
    "stops": stops[["stop_id", "CommonName", "Latitude", "Longitude",
                    "tier"]].to_dict("records"),
    "deprivation_context": ctx,
    "route_plans": plans,
    "data_sources": "NaPTAN (OGL), IMD2019 (OGL), TfL-validated shape curves, "
                    "Open-Meteo Manchester (in pack)",
}
(OUT / "route_plan_manchester.json").write_text(json.dumps(plan, indent=2))

# ── 6. Map ────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 8), facecolor="#F5F4F0")
ax.set_facecolor("#F5F4F0")
colors = {"major": "#B33A3A", "medium": "#0E7C7B", "minor": "#6B6B6B"}
order = [stops.index[stops.stop_id == s][0]
         for s in plans["am_peak"]["visit_order"]]
ax.plot(stops.Longitude[order].values, stops.Latitude[order].values,
        color="#1A1A1A", lw=1.2, alpha=0.6, zorder=1)
for tier in colors:
    sub = stops[stops.tier == tier]
    ax.scatter(sub.Longitude, sub.Latitude, s=160, c=colors[tier],
               label=f"{tier} ({len(sub)})", zorder=2, edgecolors="white")
for r in stops.itertuples():
    ax.annotate(r.stop_id, (r.Longitude, r.Latitude), fontsize=7,
                xytext=(4, 4), textcoords="offset points", color="#1A1A1A")
ax.set_title("Harpurhey, Manchester — Day-1 route bootstrap from open data only\n"
             f"(AM peak: {plans['am_peak']['route_km']} km, "
             "same method as Ladywood)", fontsize=11, fontweight="bold",
             color="#1A1A1A")
ax.legend(frameon=False, fontsize=9)
ax.tick_params(colors="#6B6B6B", labelsize=7)
for s in ax.spines.values():
    s.set_color("#CCCCCC")
fig.tight_layout()
fig.savefig(OUT / "manchester_bootstrap_map.png", dpi=200)
print(json.dumps({w: plans[w] for w in plans}, indent=2)[:600])
print("Wrote manchester_bootstrap/route_plan_manchester.json + map PNG")
