"""
demand.py
=========
Loads the trained XGBoost demand model and reproduces the prediction
feature-row assembly from `prediction model/demand_route_optimizer.py`,
without re-running that script's training pipeline on import (it trains
and plots on import, which is far too slow for an API process).

Exposes `predict_stop_demand(...)` for the FastAPI layer.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd
from sklearn.preprocessing import LabelEncoder

_REPO_ROOT = Path(__file__).parent.parent
_MODEL_DIR = _REPO_ROOT / "prediction model"
_MODEL_PKL = _MODEL_DIR / "demand_model.pkl"
_DATASET_CSV = _MODEL_DIR / "map_demand_dataset.csv"

# Synthetic plan-space coordinates for the 15 model stops — these are the
# `stop_x` / `stop_y` features the model was trained on (distinct from the
# real lat/lng in ladywood_display.STOPS_DISPLAY, which are for the map).
_STOP_XY = {
    "S01": (5.8, 0.5),  "S03": (3.5, 3.8),  "S07": (3.5, 4.9),  "S09": (7.7, 5.8),
    "S04": (5.0, 2.7),  "S08": (4.5, 5.8),  "S11": (2.5, 7.5),  "S12": (5.7, 7.7),
    "S02": (1.4, 1.5),  "S05": (8.8, 2.8),  "S06": (0.4, 4.9),  "S10": (0.4, 6.6),
    "S13": (1.4, 10.3), "S14": (0.4, 11.5), "S15": (5.8, 11.5),
}
_STOP_IMPORTANCE = {
    "S01": "major", "S03": "major", "S07": "major", "S09": "major",
    "S04": "medium", "S08": "medium", "S11": "medium", "S12": "medium",
    "S02": "minor", "S05": "minor", "S06": "minor", "S10": "minor",
    "S13": "minor", "S14": "minor", "S15": "minor",
}

_STATIC_COLS = ["imd_score", "poi_total", "population", "crime_total_2024", "elevation_m"]


def _load_bundle():
    if not _MODEL_PKL.exists():
        raise FileNotFoundError(
            f"Model not found at {_MODEL_PKL}. "
            "Run python \"prediction model/demand_route_optimizer.py\" first."
        )
    with open(_MODEL_PKL, "rb") as f:
        bundle = pickle.load(f)
    return bundle["model"], bundle["encoders"]


def _load_static_lookup() -> dict[str, dict]:
    if not _DATASET_CSV.exists():
        return {}
    df = pd.read_csv(_DATASET_CSV, usecols=lambda c: c == "stop_id" or c in _STATIC_COLS)
    cols = [c for c in _STATIC_COLS if c in df.columns]
    if not cols:
        return {}
    raw = df.drop_duplicates("stop_id").set_index("stop_id")[cols].to_dict("index")
    return {sid: {k: (None if pd.isna(v) else v) for k, v in row.items()}
            for sid, row in raw.items()}


_model, _encoders = _load_bundle()
_static_lookup = _load_static_lookup()
_static_cols = [c for c in _STATIC_COLS if c in next(iter(_static_lookup.values()), {})]


def _safe_encode(enc: LabelEncoder, value: str) -> int:
    if value in enc.classes_:
        return int(enc.transform([value])[0])
    fallback = "none" if "none" in enc.classes_ else enc.classes_[0]
    return int(enc.transform([fallback])[0])


def predict_stop_demand(
    stop_id: str, hour: int, day_type: str, month: int,
    weather: str, climate_event: str, special_event: str,
    temperature_c: float, wind_kmh: float, precipitation_mm: float,
    is_school_term: int, is_uni_term: int,
) -> float:
    """Predicted boardings for one stop at one hour, given conditions."""
    x, y = _STOP_XY[stop_id]
    row = [
        _safe_encode(_encoders["stop_id"], stop_id),
        _safe_encode(_encoders["stop_importance"], _STOP_IMPORTANCE[stop_id]),
        _safe_encode(_encoders["day_type"], day_type),
        _safe_encode(_encoders["weather_type"], weather),
        _safe_encode(_encoders["climate_event"], climate_event),
        _safe_encode(_encoders["special_event"], special_event),
        hour, month,
        temperature_c, wind_kmh, precipitation_mm,
        is_school_term, is_uni_term,
        x, y,
    ]
    if _static_cols:
        static = _static_lookup.get(stop_id, {})
        row += [static.get(c) for c in _static_cols]
    return max(0.0, float(_model.predict([row])[0]))


def predict_all_stops(hour: int, **conditions) -> dict[str, float]:
    """Predicted boardings for every stop at one hour, given conditions."""
    return {sid: round(predict_stop_demand(sid, hour, **conditions), 1) for sid in _STOP_XY}
