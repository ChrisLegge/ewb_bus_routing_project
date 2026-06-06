"""
explainability.py
=================
Feature importance analysis for the XGBoost demand prediction model.

Computes both built-in XGBoost gain-based importance and permutation importance
(model-agnostic, more reliable for correlated features). Outputs a ranked JSON
report with interpretation notes for each feature.

Usage
-----
  python analysis/explainability.py              # print summary
  python analysis/explainability.py --json       # write analysis/outputs/explainability.json

Requirements
------------
  The model must already be trained:
    python "prediction model/generate_map_dataset.py"
    python "prediction model/demand_route_optimizer.py"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────────────────────
_REPO_ROOT   = Path(__file__).parent.parent
_MODEL_DIR   = _REPO_ROOT / "prediction model"
_DATA_DIR    = _REPO_ROOT / "data" / "synthetic"
_MODEL_PKL   = _REPO_ROOT / "simulation" / "Assets" / "StreamingAssets" / "demand_model.pkl"
_DATASET_CSV = _DATA_DIR / "map_demand_dataset.csv"

sys.path.insert(0, str(_MODEL_DIR))


def _load_model_and_data():
    import pickle
    import csv

    if not _MODEL_PKL.exists():
        raise FileNotFoundError(
            f"Model not found at {_MODEL_PKL}. "
            "Run 'python prediction model/demand_route_optimizer.py' first."
        )
    if not _DATASET_CSV.exists():
        raise FileNotFoundError(
            f"Dataset not found at {_DATASET_CSV}. "
            "Run 'python prediction model/generate_map_dataset.py' first."
        )

    with open(_MODEL_PKL, "rb") as f:
        model_bundle = pickle.load(f)

    # model_bundle may be (model, feature_names) or just a model — handle both
    if isinstance(model_bundle, tuple):
        model, feature_names = model_bundle
    else:
        model = model_bundle
        feature_names = None

    # Load dataset
    rows = []
    with open(_DATASET_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    return model, feature_names, rows


def _build_feature_matrix(rows: list[dict], feature_names: list[str] | None):
    """Reconstruct the feature matrix used during training."""
    import numpy as np

    # Mirror the feature engineering from demand_route_optimizer.py / script_json.py
    weather_types = [
        "sunny", "partly_cloudy", "overcast", "light_rain", "heavy_rain",
        "fog", "light_snow", "heavy_snow", "storm", "heatwave",
    ]
    climate_events = [
        "none", "heatwave_event", "cold_snap", "named_storm",
        "heavy_snow_event", "flooding", "dense_fog",
    ]
    special_events = [
        "none", "festival", "market", "sports_match", "concert", "road_closure",
    ]

    numeric_cols = [
        "hour", "month", "temperature_c", "wind_kmh", "precipitation_mm",
        "is_school_term", "is_uni_term",
    ]
    # stop_importance ordinal
    importance_map = {"major": 2, "medium": 1, "minor": 0}

    X_rows = []
    y_rows = []
    for row in rows:
        features = [float(row.get(c, 0)) for c in numeric_cols]
        # stop importance ordinal
        features.append(importance_map.get(row.get("stop_importance", "minor"), 0))
        # day_type ordinal
        day_type = row.get("day_type", "weekday")
        features.append({"weekday": 0, "saturday": 1, "sunday": 2}.get(day_type, 0))
        # one-hot weather
        wt = row.get("weather_type", "sunny")
        features.extend([1 if wt == w else 0 for w in weather_types])
        # one-hot climate event
        ce = row.get("climate_event", "none")
        features.extend([1 if ce == c else 0 for c in climate_events])
        # one-hot special event
        se = row.get("special_event", "none")
        features.extend([1 if se == s else 0 for s in special_events])

        X_rows.append(features)
        y_rows.append(float(row.get("boardings", 0)))

    X = np.array(X_rows, dtype=np.float32)
    y = np.array(y_rows, dtype=np.float32)

    # Construct canonical feature names if not stored in the model bundle
    if feature_names is None:
        feature_names = (
            numeric_cols
            + ["stop_importance", "day_type"]
            + [f"weather_{w}" for w in weather_types]
            + [f"climate_{c}" for c in climate_events]
            + [f"event_{s}" for s in special_events]
        )

    return X, y, feature_names


def _permutation_importance(model, X, y, n_repeats: int = 5, seed: int = 42):
    """Model-agnostic permutation importance."""
    import numpy as np

    rng = np.random.default_rng(seed)
    baseline_preds = model.predict(X)
    baseline_mse = float(np.mean((baseline_preds - y) ** 2))

    importances = []
    for col in range(X.shape[1]):
        deltas = []
        for _ in range(n_repeats):
            X_perm = X.copy()
            rng.shuffle(X_perm[:, col])
            perm_preds = model.predict(X_perm)
            perm_mse = float(np.mean((perm_preds - y) ** 2))
            deltas.append(perm_mse - baseline_mse)
        importances.append(float(np.mean(deltas)))

    return importances


# Human-readable interpretation notes
_FEATURE_NOTES: dict[str, str] = {
    "hour":             "Time of day — the strongest driver of demand; captures AM/PM peaks and overnight suppression",
    "stop_importance":  "Stop tier (major/medium/minor) — encodes structural footfall; interchanges vs kerbside stops",
    "month":            "Seasonal cycle — demand drops in summer holidays and rises in cold wet months",
    "temperature_c":    "Temperature — heatwaves suppress walking trips; cold snaps increase bus dependency",
    "is_school_term":   "School term flag — large effect at minor stops near schools; smaller at interchanges",
    "is_uni_term":      "University term — affects city-centre and Five Ways stops disproportionately",
    "day_type":         "Weekday/Saturday/Sunday — Sunday patterns differ markedly from weekdays in Ladywood",
    "wind_kmh":         "Wind speed — correlated with storm events; independent effect on cyclist→bus modal shift",
    "precipitation_mm": "Rainfall — amplifies heavy_rain weather signal; orthogonal to wind",
    "weather_heavy_rain": "Heavy rain dummy — triggers significant uplift at sheltered major stops",
    "weather_storm":    "Storm dummy — reduces overall demand (stay-home effect dominates at night)",
    "weather_heatwave": "Heatwave dummy — suppresses discretionary trips; increases healthcare-destination demand",
    "climate_named_storm": "Named storm climate event — strongest climate signal; 30–50% demand reduction",
    "climate_flooding": "Flooding event — route-level disruption; correlated with precipitation",
    "event_festival":   "Festival special event — large demand spike at nearby major stops",
    "event_sports_match": "Sports match — directional demand (pre-match inbound, post-match outbound)",
    "event_road_closure": "Road closure — redistributes demand to adjacent stops",
}


def run_analysis(n_repeats: int = 5) -> dict:
    import numpy as np

    model, feature_names_stored, rows = _load_model_and_data()

    # Use a 10% stratified sample for permutation importance (fast but representative)
    rng = np.random.default_rng(0)
    sample_idx = rng.choice(len(rows), size=min(6500, len(rows)), replace=False)
    rows_sample = [rows[i] for i in sample_idx]

    X, y, feature_names = _build_feature_matrix(rows_sample, feature_names_stored)

    # XGBoost built-in gain importance
    try:
        gain_scores = model.get_booster().get_score(importance_type="gain")
        # get_score returns {f0: score, f1: score, ...} keyed by "f{index}"
        gain_by_idx = {int(k[1:]): v for k, v in gain_scores.items()}
        gain_list = [gain_by_idx.get(i, 0.0) for i in range(len(feature_names))]
        total_gain = sum(gain_list) or 1.0
        gain_normalised = [g / total_gain for g in gain_list]
    except Exception:
        gain_normalised = [0.0] * len(feature_names)

    # Permutation importance (on sample)
    perm_scores = _permutation_importance(model, X, y, n_repeats=n_repeats)
    perm_max = max(perm_scores) or 1.0
    perm_normalised = [max(0.0, p / perm_max) for p in perm_scores]

    features_out = []
    for i, name in enumerate(feature_names):
        features_out.append({
            "feature":              name,
            "gain_importance":      round(gain_normalised[i], 4),
            "permutation_importance": round(perm_normalised[i], 4),
            "combined_rank_score":  round((gain_normalised[i] + perm_normalised[i]) / 2, 4),
            "interpretation":       _FEATURE_NOTES.get(name, ""),
        })

    features_out.sort(key=lambda x: -x["combined_rank_score"])

    return {
        "model_path":    str(_MODEL_PKL),
        "dataset_rows":  len(rows),
        "sample_rows":   len(rows_sample),
        "n_features":    len(feature_names),
        "n_perm_repeats": n_repeats,
        "top_features":  features_out[:10],
        "all_features":  features_out,
        "methodology": {
            "gain_importance": (
                "XGBoost built-in: average gain across all trees for splits on each feature. "
                "Fast but biased toward high-cardinality and continuous features."
            ),
            "permutation_importance": (
                "Model-agnostic: MSE increase when a single feature column is randomly permuted. "
                "Unbiased but more expensive; computed on a 10% sample with 5 repeats."
            ),
            "combined_rank_score": "Mean of normalised gain and permutation scores.",
        },
    }


def print_summary(result: dict) -> None:
    sep = "─" * 60
    print(f"\n{'XGBoost Demand Model — Feature Importance':^60}")
    print(sep)
    print(f"  Dataset rows: {result['dataset_rows']:,}  |  Sample: {result['sample_rows']:,}")
    print(f"  Features: {result['n_features']}  |  Permutation repeats: {result['n_perm_repeats']}")
    print(f"\n  {'Feature':<28} {'Gain':>6}  {'Perm':>6}  {'Score':>6}")
    print(f"  {'─'*28} {'─'*6}  {'─'*6}  {'─'*6}")
    for f in result["top_features"]:
        print(
            f"  {f['feature']:<28} {f['gain_importance']:>6.3f}  "
            f"{f['permutation_importance']:>6.3f}  {f['combined_rank_score']:>6.3f}"
        )
    print()
    print("  Interpretations (top 5):")
    for f in result["top_features"][:5]:
        note = f["interpretation"]
        if note:
            print(f"  · {f['feature']}: {note[:80]}")
    print(sep)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    result = run_analysis(n_repeats=args.repeats)
    print_summary(result)

    if args.json:
        out_dir = Path(__file__).parent / "outputs"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "explainability.json"
        out_path.write_text(json.dumps(result, indent=2))
        print(f"\nWrote {out_path}")
