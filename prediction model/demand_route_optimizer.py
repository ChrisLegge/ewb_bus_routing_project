"""
demand_route_optimizer.py
=========================
1. Loads  map_demand_dataset.csv
2. Trains an XGBoost demand-prediction model
3. Evaluates model quality (RMSE, MAE, R²)
4. Simulates four contrasting days (weekday fine / weekday rainy /
   weekend sunny / storm event) predicting demand every 2 hours
5. For each 2-hour window, runs a greedy Vehicle-Routing optimizer
   that re-routes 3 buses along the road network to maximise
   predicted passengers served
6. Outputs
     demand_model.pkl      — trained XGBoost + encoders
     route_plan.json       — complete route plan with demand scores
     route_plan_summary.txt — human-readable summary
"""

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
from xgboost import XGBRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# ─────────────────────────────────────────────────────────────────────────────
# 0.  PATHS
# ─────────────────────────────────────────────────────────────────────────────

BASE = Path(__file__).parent
DATA = BASE / "map_demand_dataset.csv"
OUT_MODEL = BASE / "demand_model.pkl"
OUT_PLAN  = BASE / "route_plan.json"
OUT_TXT   = BASE / "route_plan_summary.txt"

# ─────────────────────────────────────────────────────────────────────────────
# 1.  MAP TOPOLOGY  (must match generate_map_dataset.py)
# ─────────────────────────────────────────────────────────────────────────────

STOPS = [
    {"id": "S01", "name": "North Hub",       "x": 5.8, "y": 0.5,  "importance": "major"},
    {"id": "S03", "name": "Upper Junction",  "x": 3.5, "y": 3.8,  "importance": "major"},
    {"id": "S07", "name": "West Hub",        "x": 3.5, "y": 4.9,  "importance": "major"},
    {"id": "S09", "name": "East Hub",        "x": 7.7, "y": 5.8,  "importance": "major"},
    {"id": "S04", "name": "Northeast Pass",  "x": 5.0, "y": 2.7,  "importance": "medium"},
    {"id": "S08", "name": "City Centre",     "x": 4.5, "y": 5.8,  "importance": "medium"},
    {"id": "S11", "name": "South Junction",  "x": 2.5, "y": 7.5,  "importance": "medium"},
    {"id": "S12", "name": "Southeast Cross", "x": 5.7, "y": 7.7,  "importance": "medium"},
    {"id": "S02", "name": "Northwest End",   "x": 1.4, "y": 1.5,  "importance": "minor"},
    {"id": "S05", "name": "Far East End",    "x": 8.8, "y": 2.8,  "importance": "minor"},
    {"id": "S06", "name": "West End",        "x": 0.4, "y": 4.9,  "importance": "minor"},
    {"id": "S10", "name": "Lower West End",  "x": 0.4, "y": 6.6,  "importance": "minor"},
    {"id": "S13", "name": "South End",       "x": 1.4, "y": 10.3, "importance": "minor"},
    {"id": "S14", "name": "Far South West",  "x": 0.4, "y": 11.5, "importance": "minor"},
    {"id": "S15", "name": "Far South East",  "x": 5.8, "y": 11.5, "importance": "minor"},
]

EDGES = [
    ("S01", "S03",  8), ("S01", "S04",  5), ("S02", "S03",  7),
    ("S03", "S04",  4), ("S03", "S07",  4), ("S04", "S05",  9),
    ("S05", "S09",  8), ("S06", "S07",  5), ("S06", "S10",  4),
    ("S07", "S08",  4), ("S07", "S11",  6), ("S08", "S09",  6),
    ("S08", "S12",  5), ("S09", "S12",  6), ("S10", "S11",  4),
    ("S11", "S12",  5), ("S11", "S13",  7), ("S12", "S15",  8),
    ("S13", "S14",  3), ("S13", "S15",  7),
]

STOP_MAP  = {s["id"]: s for s in STOPS}
STOP_IDS  = [s["id"]   for s in STOPS]

# ─────────────────────────────────────────────────────────────────────────────
# 2.  BUILD ROAD GRAPH
# ─────────────────────────────────────────────────────────────────────────────

G = nx.Graph()
for s in STOPS:
    G.add_node(s["id"], name=s["name"], x=s["x"], y=s["y"],
               importance=s["importance"])
for a, b, t in EDGES:
    G.add_edge(a, b, travel_time=t)

# Pre-compute all-pairs shortest paths (15 stops, trivial)
ALL_PATHS = dict(nx.all_pairs_dijkstra_path_length(G, weight="travel_time"))

# ─────────────────────────────────────────────────────────────────────────────
# 3.  LOAD DATA & FEATURE ENGINEERING
# ─────────────────────────────────────────────────────────────────────────────

print("Loading dataset...")
df = pd.read_csv(DATA)
print(f"  {len(df):,} rows loaded.")

# Categorical columns to label-encode
CAT_COLS = [
    "stop_id", "stop_importance", "day_type",
    "weather_type", "climate_event", "special_event",
]

encoders: dict[str, LabelEncoder] = {}
for col in CAT_COLS:
    le = LabelEncoder()
    df[col + "_enc"] = le.fit_transform(df[col])
    encoders[col] = le

_REAL_STATIC_COLS = ["imd_score", "poi_total", "population", "crime_total_2024", "elevation_m"]

FEATURE_COLS = (
    [c + "_enc" for c in CAT_COLS]
    + ["hour", "month", "temperature_c", "wind_kmh", "precipitation_mm",
       "is_school_term", "is_uni_term", "stop_x", "stop_y"]
    + [c for c in _REAL_STATIC_COLS if c in df.columns]
)

X = df[FEATURE_COLS].values
y = df["boardings"].values

# Temporal split: train on 2023, test on 2024 — a model that only ever sees
# random-shuffled rows can "cheat" by memorising a stop's hourly pattern from
# a row an hour away in the test set. Splitting on real calendar dates means
# the test year is genuinely unseen, which is the honest test of whether the
# model generalises across time (reviewer 2a: sampling/independence concerns).
df["date"] = pd.to_datetime(df["date"])
train_mask = df["date"].dt.year == 2023
test_mask  = df["date"].dt.year == 2024

X_train, y_train = X[train_mask.values], y[train_mask.values]
X_test,  y_test  = X[test_mask.values],  y[test_mask.values]
print(f"\nTemporal split: train on 2023 ({len(X_train):,} rows), "
      f"test on 2024 ({len(X_test):,} rows)")

# ─────────────────────────────────────────────────────────────────────────────
# 4.  TRAIN XGBOOST MODEL
# ─────────────────────────────────────────────────────────────────────────────

print("\nTraining XGBoost demand model...")
model = XGBRegressor(
    n_estimators=400,
    max_depth=7,
    learning_rate=0.07,
    subsample=0.80,
    colsample_bytree=0.80,
    min_child_weight=5,
    reg_alpha=0.1,
    reg_lambda=1.0,
    random_state=42,
    eval_metric="rmse",
    n_jobs=-1,
)
model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=False,
)

y_pred = model.predict(X_test)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
mae  = mean_absolute_error(y_test, y_pred)
r2   = r2_score(y_test, y_pred)

print(f"  RMSE : {rmse:.2f} boardings")
print(f"  MAE  : {mae:.2f} boardings")
print(f"  R2   : {r2:.4f}")

# Feature importance
feat_imp = sorted(
    zip(FEATURE_COLS, model.feature_importances_),
    key=lambda x: x[1], reverse=True,
)
print("\n  Top feature importances:")
for fname, fimp in feat_imp[:8]:
    bar = "#" * int(fimp * 200)
    print(f"    {fname:<25} {fimp:.4f}  {bar}")

# ─────────────────────────────────────────────────────────────────────────────
# 5.  SAVE MODEL
# ─────────────────────────────────────────────────────────────────────────────

with open(OUT_MODEL, "wb") as f:
    pickle.dump({"model": model, "encoders": encoders,
                 "feature_cols": FEATURE_COLS}, f)
print(f"\nModel saved: {OUT_MODEL}")

# ─────────────────────────────────────────────────────────────────────────────
# 6.  PREDICTION HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _safe_encode(enc: LabelEncoder, value: str) -> int:
    """Encode a categorical value; fall back to 'none' if unseen."""
    if value in enc.classes_:
        return int(enc.transform([value])[0])
    # Unseen label — use 'none' if available, otherwise first class
    fallback = "none" if "none" in enc.classes_ else enc.classes_[0]
    return int(enc.transform([fallback])[0])


# Per-stop static real-feature lookup for simulation (mirrors the columns
# appended to map_demand_dataset.csv by generate_real_demand_dataset.py)
_STATIC_COLS = [c for c in
                ["imd_score", "poi_total", "population", "crime_total_2024", "elevation_m"]
                if c in df.columns]
_STATIC_LOOKUP = (
    df.drop_duplicates("stop_id").set_index("stop_id")[_STATIC_COLS].to_dict("index")
    if _STATIC_COLS else {}
)


def predict_stop_demand(
    stop_id, hour, day_type, month,
    weather, climate_event, special_event,
    temperature_c, wind_kmh, precipitation_mm,
    is_school_term, is_uni_term,
) -> float:
    """Return predicted boardings for one stop-hour combination."""
    s = STOP_MAP[stop_id]
    row = [
        _safe_encode(encoders["stop_id"],         stop_id),
        _safe_encode(encoders["stop_importance"],  s["importance"]),
        _safe_encode(encoders["day_type"],         day_type),
        _safe_encode(encoders["weather_type"],     weather),
        _safe_encode(encoders["climate_event"],    climate_event),
        _safe_encode(encoders["special_event"],    special_event),
        hour, month,
        temperature_c, wind_kmh, precipitation_mm,
        is_school_term, is_uni_term,
        s["x"], s["y"],
    ]
    if _STATIC_COLS:
        static = _STATIC_LOOKUP.get(stop_id, {})
        row += [static.get(c) for c in _STATIC_COLS]
    return max(0.0, float(model.predict([row])[0]))


def predict_window_demand(hours: list[int], day_conditions: dict) -> dict[str, float]:
    """Predict total boardings at each stop across a list of hours."""
    demand: dict[str, float] = {}
    for sid in STOP_IDS:
        total = 0.0
        for h in hours:
            total += predict_stop_demand(
                sid, h, **day_conditions,
            )
        demand[sid] = round(total, 1)
    return demand

# ─────────────────────────────────────────────────────────────────────────────
# 7.  GREEDY ROUTE OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────
#
# Algorithm
# ---------
# For each bus B in 1..N_BUSES:
#   1. Start at the unvisited stop with highest demand.
#   2. Greedily extend the route by picking the best reachable unvisited stop
#      scored by   demand / travel_time  (passengers per minute of deadhead).
#   3. Stop when the time budget is exhausted or no unvisited stops remain.
#
# Routes use real shortest-path travel times from the pre-computed ALL_PATHS
# matrix so a bus always takes the fastest road path between stops.

import itertools

N_BUSES          = 3
ROUTE_BUDGET_MIN = 70      # max one-way route time in minutes
MIN_DEMAND_VISIT = 2.0     # don't bother visiting a stop below this threshold
BUS_CAPACITY     = 320.0   # passengers a bus can serve across the window


def path_time(order: list[str]) -> float:
    """Total shortest-path travel time along an ordered open route."""
    return sum(ALL_PATHS[order[i]].get(order[i + 1], float("inf"))
               for i in range(len(order) - 1))


def two_opt(order: list[str]) -> list[str]:
    """2-opt local search minimising open-route travel time (start fixed)."""
    if len(order) < 4:
        return order[:]
    best, best_t, improved = order[:], path_time(order), True
    while improved:
        improved = False
        for i in range(1, len(best) - 1):
            for j in range(i + 1, len(best)):
                cand = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                cand_t = path_time(cand)
                if cand_t < best_t - 1e-9:
                    best, best_t, improved = cand, cand_t, True
    return best


def optimal_path_time(order: list[str]) -> float:
    """Brute-force the minimum open-route time visiting the same stop set with
    the start fixed. Feasible for the small routes here (<= ~9 stops)."""
    if len(order) < 3:
        return path_time(order)
    start, rest = order[0], order[1:]
    if len(rest) > 8:        # keep brute force tractable
        return path_time(two_opt(order))
    best = float("inf")
    for perm in itertools.permutations(rest):
        best = min(best, path_time([start, *perm]))
    return best


def greedy_route(demand: dict[str, float]) -> list[dict]:
    """
    Returns a list of N_BUSES route dicts:
      {bus, route_stops, route_names, stop_demand, total_demand, route_time_min}
    Construction is greedy (demand-per-minute), refined with 2-opt, and capped
    at BUS_CAPACITY passengers per vehicle.
    """
    remaining_demand = dict(demand)   # modifiable copy
    routes = []

    for bus_idx in range(N_BUSES):
        # Pick the unvisited highest-demand stop as start
        candidates = [(sid, d) for sid, d in remaining_demand.items()
                      if d >= MIN_DEMAND_VISIT]
        if not candidates:
            break
        start_sid = max(candidates, key=lambda x: x[1])[0]

        route_stops   = [start_sid]
        route_demand  = {start_sid: remaining_demand.pop(start_sid, 0)}
        route_time    = 0.0
        current       = start_sid

        while True:
            if sum(route_demand.values()) >= BUS_CAPACITY:
                break
            best_sid, best_score, best_tt = None, -1.0, 0
            for sid, dem in remaining_demand.items():
                if dem < MIN_DEMAND_VISIT:
                    continue
                tt = ALL_PATHS[current].get(sid, float("inf"))
                if route_time + tt > ROUTE_BUDGET_MIN:
                    continue
                score = dem / max(1.0, tt)
                if score > best_score:
                    best_score = score
                    best_sid   = sid
                    best_tt    = tt

            if best_sid is None:
                break

            route_stops.append(best_sid)
            route_demand[best_sid] = remaining_demand.pop(best_sid, 0)
            route_time += best_tt
            current     = best_sid

        # Refine visiting order with 2-opt local search.
        route_stops = two_opt(route_stops)
        route_time  = path_time(route_stops)

        raw_demand = sum(route_demand.values())
        routes.append({
            "bus":            bus_idx + 1,
            "route_stops":    route_stops,
            "route_names":    [STOP_MAP[s]["name"] for s in route_stops],
            "stop_demand":    {s: route_demand[s] for s in route_stops},
            "total_demand":   round(min(raw_demand, BUS_CAPACITY), 1),
            "route_time_min": round(route_time, 1),
        })

    return routes


def route_gaps(routes: list[dict]) -> list[float]:
    """Per-route % above optimal of the 2-opt routes' travel time (for routes
    with >= 3 stops). Returns one value per route — including 0.0 for routes
    that 2-opt already solved optimally — so aggregates are unbiased."""
    gaps = []
    for r in routes:
        stops = r["route_stops"]
        if len(stops) < 3:
            continue
        opt = optimal_path_time(stops)
        got = path_time(stops)
        if opt > 0:
            gaps.append(100.0 * (got - opt) / opt)
    return gaps

# ─────────────────────────────────────────────────────────────────────────────
# 8.  SIMULATE FOUR CONTRASTING DAYS
# ─────────────────────────────────────────────────────────────────────────────

TIME_WINDOWS = [
    ("Early Morning", list(range(5,  7))),
    ("AM Peak",       list(range(7,  9))),
    ("Mid Morning",   list(range(9,  11))),
    ("Lunch",         list(range(11, 13))),
    ("Afternoon",     list(range(13, 16))),
    ("PM Peak",       list(range(16, 18))),
    ("Evening",       list(range(18, 21))),
    ("Night",         list(range(21, 24))),
]

SCENARIO_DAYS = [
    {
        "label": "Weekday (Sunny, Sep)",
        "conditions": dict(
            day_type="weekday", month=9, weather="sunny",
            climate_event="none", special_event="none",
            temperature_c=19.0, wind_kmh=10.0, precipitation_mm=0.0,
            is_school_term=1, is_uni_term=0,
        ),
    },
    {
        "label": "Weekday (Heavy Rain, Nov)",
        "conditions": dict(
            day_type="weekday", month=11, weather="heavy_rain",
            climate_event="none", special_event="none",
            temperature_c=9.0, wind_kmh=35.0, precipitation_mm=10.0,
            is_school_term=1, is_uni_term=1,
        ),
    },
    {
        "label": "Saturday (Sunny Summer Festival @ North Hub)",
        "conditions": dict(
            day_type="saturday", month=7, weather="sunny",
            climate_event="none", special_event="festival",
            temperature_c=26.0, wind_kmh=8.0, precipitation_mm=0.0,
            is_school_term=0, is_uni_term=0,
        ),
    },
    {
        "label": "Weekday (Named Storm, Jan)",
        "conditions": dict(
            day_type="weekday", month=1, weather="storm",
            climate_event="named_storm", special_event="none",
            temperature_c=4.0, wind_kmh=75.0, precipitation_mm=15.0,
            is_school_term=1, is_uni_term=1,
        ),
    },
]

print("\n" + "=" * 70)
print("ROUTE OPTIMIZER — SIMULATING 4 SCENARIO DAYS")
print("=" * 70)

full_plan   = {}
summary_lines = []
optimality_gaps: list[float] = []

for scenario in SCENARIO_DAYS:
    label      = scenario["label"]
    conditions = scenario["conditions"]

    print(f"\n{'-'*70}")
    print(f"SCENARIO: {label}")
    print(f"{'-'*70}")
    summary_lines.append(f"\n{'='*70}")
    summary_lines.append(f"SCENARIO: {label}")
    summary_lines.append(f"{'='*70}")

    scenario_plan = {}

    for window_name, hours in TIME_WINDOWS:
        hour_range = f"{hours[0]:02d}:00-{hours[-1]+1:02d}:00"

        # ── Predict demand across the window ──────────────────────────────────
        demand = predict_window_demand(hours, conditions)

        # ── Run optimizer ─────────────────────────────────────────────────────
        routes = greedy_route(demand)
        optimality_gaps.extend(route_gaps(routes))

        # ── Identify any unserved stops ───────────────────────────────────────
        served = {s for r in routes for s in r["route_stops"]}
        unserved = [
            (sid, demand[sid]) for sid in STOP_IDS
            if sid not in served and demand[sid] >= MIN_DEMAND_VISIT
        ]
        unserved.sort(key=lambda x: x[1], reverse=True)

        scenario_plan[window_name] = {
            "hours":           hour_range,
            "demand_per_stop": {sid: demand[sid] for sid in STOP_IDS},
            "routes":          routes,
            "unserved_stops":  [{"stop": STOP_MAP[s]["name"], "demand": d}
                                 for s, d in unserved],
        }

        # ── Console output ────────────────────────────────────────────────────
        total_served   = sum(r["total_demand"] for r in routes)
        total_network  = sum(demand.values())
        coverage_pct   = 100 * total_served / max(total_network, 1)

        print(f"\n  [{hour_range}]  {window_name}")
        print(f"  Network demand: {total_network:.0f} boardings | "
              f"Served: {total_served:.0f} ({coverage_pct:.0f}%)")

        block = []
        for r in routes:
            arrow_route = " -> ".join(r["route_names"])
            line = (f"    Bus {r['bus']}: {arrow_route}  "
                    f"[{r['total_demand']:.0f} pass, "
                    f"{r['route_time_min']} min]")
            print(line)
            block.append(line)

        if unserved:
            us_line = ("  !! Unserved: "
                       + ", ".join(f"{STOP_MAP[s]['name']} ({d:.0f})"
                                   for s, d in unserved[:4]))
            print(us_line)
            block.append(us_line)

        # Build summary
        summary_lines.append(f"\n  [{hour_range}]  {window_name}")
        summary_lines.append(f"  Network demand: {total_network:.0f}  |  "
                              f"Served: {total_served:.0f} ({coverage_pct:.0f}%)")
        summary_lines.extend(block)

    full_plan[label] = scenario_plan

# ─────────────────────────────────────────────────────────────────────────────
# 9.  SAVE OUTPUTS
# ─────────────────────────────────────────────────────────────────────────────

with open(OUT_PLAN, "w", encoding="utf-8") as f:
    json.dump(full_plan, f, indent=2)
print(f"\n\nRoute plan saved: {OUT_PLAN}")

with open(OUT_TXT, "w", encoding="utf-8") as f:
    f.write("\n".join(summary_lines))
print(f"Summary txt saved: {OUT_TXT}")

# ─────────────────────────────────────────────────────────────────────────────
# 10.  CROSS-SCENARIO COMPARISON TABLE
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("CROSS-SCENARIO: TOTAL DAILY DEMAND vs DEMAND SERVED")
print("=" * 70)
print(f"  {'Scenario':<46} {'Total':>7} {'Served':>7} {'Cover%':>7}")
print(f"  {'-'*46} {'-'*7} {'-'*7} {'-'*7}")
for scenario in SCENARIO_DAYS:
    label = scenario["label"]
    sp    = full_plan[label]
    total  = sum(v["demand_per_stop"][sid]
                 for v in sp.values() for sid in STOP_IDS)
    served = sum(r["total_demand"]
                 for v in sp.values() for r in v["routes"])
    cover  = 100 * served / max(total, 1)
    print(f"  {label:<46} {total:>7.0f} {served:>7.0f} {cover:>6.0f}%")

# ─────────────────────────────────────────────────────────────────────────────
# 11.  STOP-LEVEL DEMAND COMPARISON (AM Peak only)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("AM PEAK DEMAND PER STOP — ALL 4 SCENARIOS")
print("=" * 70)
col_w = 16
header_parts = ["Stop".ljust(22)] + [s["label"][:col_w].rjust(col_w+1)
                                      for s in SCENARIO_DAYS]
print("  " + "  ".join(header_parts))
print("  " + "-" * (22 + (col_w + 3) * len(SCENARIO_DAYS)))

for stop in STOPS:
    sid = stop["id"]
    vals = []
    for scenario in SCENARIO_DAYS:
        val = full_plan[scenario["label"]]["AM Peak"]["demand_per_stop"].get(sid, 0)
        vals.append(f"{val:>{col_w}.0f}")
    print(f"  {stop['name']:<22}  {'  '.join(vals)}")

# ─────────────────────────────────────────────────────────────────────────────
# 12.  ROUTE QUALITY — MEASURED OPTIMALITY GAP (greedy + 2-opt vs brute force)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("ROUTE QUALITY - 2-OPT vs OPTIMAL (brute force, per route)")
print("=" * 70)
if optimality_gaps:
    mean_gap  = sum(optimality_gaps) / len(optimality_gaps)
    worst_gap = max(optimality_gaps)
    pct_opt   = 100 * sum(g < 0.01 for g in optimality_gaps) / len(optimality_gaps)
    print(f"  Routes evaluated : {len(optimality_gaps)} (>= 3 stops)")
    print(f"  Mean gap         : {mean_gap:.2f}% above optimal")
    print(f"  Worst gap        : {worst_gap:.2f}% above optimal")
    print(f"  Solved optimally : {pct_opt:.0f}% of routes")
else:
    print("  (no multi-stop routes to evaluate)")

print("\nDone.")
