# Dashboard

A FastAPI backend (`api.py`) and a React 19 + MapLibre GL frontend
(`web/`) that visualises the demand model and route optimiser live, on real
Ladywood geography. See the main [README's Dashboard
section](../README.md#the-dashboard) for screenshots and a feature tour — this
file covers how to run it.

## Backend (`api.py`)

A thin FastAPI layer over the project's existing model/optimiser artefacts —
it does not duplicate any logic, it serves what `prediction model/` already
produces:

| Endpoint | What it returns |
|---|---|
| `GET /api/stops` | The 15 real TfWM stops — id, name, coordinates, routes served, importance tier, plus static features (IMD, POI count, population, crime, elevation) |
| `GET /api/roads` | Real road-following polylines between every stop pair, keyed `"S01\|S07"` (sorted, reused for both directions) |
| `GET /api/demand` | Live call into `predict_window_demand()` — the only endpoint that runs the XGBoost model at request time, given `hour`, `day_type`, `weather`, `special_event`, `is_school_term`, `is_uni_term` |
| `GET /api/scenarios` | The list of pre-solved scenario names available in `route_plan.json` |
| `GET /api/routes/{scenario}/{window}` | The pre-solved route plan for a scenario/window, including bus routes (with real road geometry via `_route_geometry()`), per-stop demand, and any unserved stops |
| `GET /api/health` | Liveness check |

`_road_paths` and `_route_plan` are loaded once at startup from cached JSON —
the backend never recomputes road geometry or re-solves routes per request;
it only re-runs the demand model live (for the "what-if conditions" panel),
which is the one piece of the system designed to respond in real time.

Run it with:
```bash
uvicorn dashboard.api:app --reload
```

## Frontend (`web/`)

React 19 + TypeScript + Vite + Framer Motion + MapLibre GL, styled as a
minimalist dark "Apple Maps at night" experience.

| File | Role |
|---|---|
| `App.tsx` | Top-level state, layout, HUD panels, scenario/time-window controls |
| `MapView.tsx` | MapLibre basemap, stop markers, route animation |
| `BusLayer.tsx` | Animated bus markers following real road geometry |
| `StopPanel.tsx` | Click-a-stop detail panel |
| `ConditionsPanel.tsx` | Live "what-if" toggles (day type, weather, events, term) feeding `/api/demand` |
| `ComparePanel.tsx` | Side-by-side scenario comparison stats |
| `StoryOverlay.tsx` / `story.ts` | Guided narrative walkthrough mode |
| `api.ts` | Typed fetch wrappers for every backend endpoint |

Run it with:
```bash
cd dashboard/web
npm install
npm run dev      # http://localhost:5173, proxies /api to the FastAPI backend
npm run build    # production build
npm run lint     # ESLint
```

## Why this split?

The backend is deliberately thin — it exists to (a) expose the project's
existing offline-computed artefacts (`route_plan.json`, road geometry) over
HTTP, and (b) provide the *one* genuinely live piece, the demand-model
endpoint, so the "what-if conditions" panel can demonstrate the model
responding in real time rather than just replaying pre-computed scenarios.
Everything else is read-only and cached, which is what keeps the whole system
fast (sub-2-second route solves, instant scenario switching) and cheap to run
— see [Running Costs](../docs/design/RUNNING_COSTS.md) for the actual hosting
cost figures.
