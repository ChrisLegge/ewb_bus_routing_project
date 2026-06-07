"""
api.py
======
FastAPI backend for the Predictive Bus Routing dashboard.

Serves the static network (stops + real road geometry) and, in later
features, live demand predictions and route plans from the trained
XGBoost model.

Run:
    uvicorn dashboard.api:app --port 8000
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dashboard.ladywood_display import STOPS_DISPLAY
from dashboard.demand import predict_all_stops, _static_lookup

_REPO_ROOT = Path(__file__).parent.parent
_ROAD_PATHS = _REPO_ROOT / "data" / "gtfs" / "road_paths.json"
_ROUTE_PLAN = _REPO_ROOT / "prediction model" / "route_plan.json"

app = FastAPI(title="Predictive Bus Routing API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

with open(_ROAD_PATHS, encoding="utf-8") as f:
    _road_paths: dict[str, list[list[float]]] = json.load(f)

_route_plan: dict = {}
if _ROUTE_PLAN.exists():
    with open(_ROUTE_PLAN, encoding="utf-8") as f:
        _route_plan = json.load(f)


def _segment_path(a: str, b: str) -> list[list[float]]:
    """Real road polyline between two stops, in travel direction a -> b."""
    key = "|".join(sorted([a, b]))
    path = _road_paths.get(key, [])
    if path and sorted([a, b])[0] != a:
        path = list(reversed(path))
    return path


def _route_geometry(route_stops: list[str]) -> list[list[float]]:
    """Concatenated real road polyline following a route's full stop sequence."""
    geometry: list[list[float]] = []
    for a, b in zip(route_stops, route_stops[1:]):
        seg = _segment_path(a, b)
        geometry.extend(seg[1:] if geometry else seg)
    return geometry


@app.get("/api/stops")
def get_stops():
    """The 15 model stops — id, name, coordinates, routes, importance tier."""
    return [
        {"stop_id": sid, **info, **_static_lookup.get(sid, {})}
        for sid, info in STOPS_DISPLAY.items()
    ]


@app.get("/api/roads")
def get_roads():
    """Real road-following polylines between every pair of stops.

    Keys are "S01|S07" (sorted stop-id pair); each value is a list of
    [lng, lat] points. The reverse direction reuses the same polyline.
    """
    return _road_paths


@app.get("/api/demand")
def get_demand(
    hour: int = 8,
    day_type: str = "weekday",
    month: int = 9,
    weather: str = "sunny",
    climate_event: str = "none",
    special_event: str = "none",
    temperature_c: float = 16.0,
    wind_kmh: float = 12.0,
    precipitation_mm: float = 0.0,
    is_school_term: int = 1,
    is_uni_term: int = 1,
):
    """Live per-stop boarding predictions from the trained XGBoost model
    for one hour, given a set of conditions (weather, calendar, events)."""
    predictions = predict_all_stops(
        hour=hour, day_type=day_type, month=month,
        weather=weather, climate_event=climate_event, special_event=special_event,
        temperature_c=temperature_c, wind_kmh=wind_kmh, precipitation_mm=precipitation_mm,
        is_school_term=is_school_term, is_uni_term=is_uni_term,
    )
    return {
        "hour": hour,
        "conditions": {
            "day_type": day_type, "month": month, "weather": weather,
            "climate_event": climate_event, "special_event": special_event,
            "temperature_c": temperature_c, "wind_kmh": wind_kmh,
            "precipitation_mm": precipitation_mm,
            "is_school_term": is_school_term, "is_uni_term": is_uni_term,
        },
        "predictions": predictions,
    }


@app.get("/api/scenarios")
def get_scenarios():
    """Available pre-computed scenario names (e.g. 'Weekday (Sunny, Sep)')."""
    return list(_route_plan.keys())


@app.get("/api/routes/{scenario}/{window}")
def get_routes(scenario: str, window: str):
    """Optimised routes for one scenario + time window, with real road
    geometry attached to each route so the frontend can animate buses
    along actual streets rather than straight lines between stops.

    Example: /api/routes/Weekday (Sunny, Sep)/AM Peak
    """
    scenario_plan = _route_plan.get(scenario)
    if scenario_plan is None:
        return {"error": "unknown scenario", "available": list(_route_plan.keys())}
    window_plan = scenario_plan.get(window)
    if window_plan is None:
        return {"error": "unknown window", "available": list(scenario_plan.keys())}

    routes = []
    for route in window_plan.get("routes", []):
        stops = route["route_stops"]
        routes.append({
            **route,
            "geometry": _route_geometry(stops),
        })

    return {
        "scenario": scenario,
        "window": window,
        "hours": window_plan.get("hours"),
        "demand_per_stop": window_plan.get("demand_per_stop"),
        "routes": routes,
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "stops": len(STOPS_DISPLAY), "road_segments": len(_road_paths)}
