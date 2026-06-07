# Predictive Bus Routing — Ladywood, Birmingham

[![CI](https://github.com/ChrisLegge/ewb_bus_routing_project/actions/workflows/ci.yml/badge.svg)](https://github.com/ChrisLegge/ewb_bus_routing_project/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![React](https://img.shields.io/badge/React-19-61dafb)
![Model](https://img.shields.io/badge/Model-XGBoost-green)
![FPGA](https://img.shields.io/badge/FPGA-DE1--SoC-orange)
![Status](https://img.shields.io/badge/Status-Prototype-yellow)

> Engineering Without Borders Design Challenge 2025–26 · UK2026-82 · Ladywood Ward, Birmingham

---

<p align="center">
  <img src="docs/figures/demo.gif" width="45%" />
  <img src="docs/figures/FPGA.gif" width="45%" />
</p>
<p align="center">
  <em>Left: live web dashboard — ML-driven routing on real Ladywood roads &nbsp;|&nbsp; Right: FPGA LED network map</em>
</p>

---

## The Problem

Ladywood is one of the most deprived wards in England. **57.9% of households have no car** (Census 2021). For these residents — shift workers, carers, patients, students — the bus is not a convenience. It is the only option.

Fixed-schedule routing cannot respond to demand. A bus runs at 08:00 whether twenty people are waiting or two. When demand spikes — weather, events, school term start — the network has no mechanism to adapt. Overcrowding, missed connections, and long waits follow.

This project builds a system that adapts routing in real time to predicted demand, and makes that routing visible — both digitally and physically — to everyone in the community.

---

## What We Built

A five-layer system, end to end:

| Layer | What it does |
|---|---|
| **Demand model** | XGBoost trained on 263k rows built from real Birmingham 2023–2024 weather and school-term data, with each stop's demand anchored to real TfWM concessionary smartcard journey volumes (UCL/GEoDS); predicts boardings per stop per hour |
| **Route optimiser** | Capacitated VRP — greedy construction + 2-opt local search; 0.4% mean gap above brute-force optimal; < 2s solve time |
| **Web dashboard** | FastAPI + React 19 + MapLibre GL; real TfWM stop coordinates; buses animate along real Ladywood road geometry |
| **Unity simulation** | Multi-agent bus system driven by the live ML output; same routing logic as the dashboard |
| **FPGA LED map** | Terasic DE1-SoC driving 156 WS2812B LEDs; a physical, screen-free network display for the community |

---

## Key Results

| Metric | Value |
|---|---|
| Demand model R² | 0.945 (RMSE 4.57 boardings) — temporal split, train 2023 / test 2024 |
| Routing optimality gap | 2.4% mean above optimal |
| Routes solved optimally | 89% |
| Solve time | < 2 s |
| Real stops modelled | 15 (TfWM routes 8A/8C, 80, 126) |
| Operating cost saving | ~£10k/yr (DfT BUS0404 methodology) |
| Break-even | ~5.5 months |
| Social value (DfT TAG) | ~£194k/yr passenger time savings |
| Deprivation coverage uplift | +19.5% (IMD 2019 weighted) |

All figures are reproducible — see [Getting Started](#getting-started).

---

## From Synthetic to Real: How the Demand Model Evolved

The project started — deliberately — with a fully **synthetic** dataset (`generate_map_dataset.py`, 65k rows): hand-picked per-stop `base` demand values, sampled weather distributions, and a fixed monthly school-term flag. It was a good starting point — it let the routing optimiser, dashboard, and FPGA layers be built and tested before any real demand data existed, and it's still in the repo for comparison.

We then mined as much **real, openly-licensed data** as exists for Ladywood (see [Data Sources](#data-sources) — IMD, OSM POIs, crime, elevation, Census, DfT bus stats, BODS live feeds, and critically the UCL/GEoDS concessionary smartcard journey volumes), and built `generate_real_demand_dataset.py` to retrain on it:

| | Synthetic baseline | Real-data-anchored (current) |
|---|---|---|
| Rows | 65k, fully sampled | 263k, spans real Birmingham 2023–2024 (every real day in the weather archive) |
| Weather | Sampled from a hand-built monthly probability table | Real Open-Meteo hourly archive — actual recorded conditions per hour |
| School terms | Fixed flag per calendar month | Real Birmingham term + bank-holiday calendar, per real date |
| Per-stop demand level | Hand-picked `base` value per importance tier | Anchored to real ENCTS concessionary smartcard journey volumes (UCL/GEoDS, TfWM-linked) |
| Static features | `stop_x`, `stop_y`, `stop_importance` only | + `imd_score`, `poi_total`, `population`, `crime_total_2024`, `elevation_m` — all real, all per-stop |
| Demand model R² | 0.940 (RMSE 4.3), random 80/20 split | 0.945 (RMSE 4.57), **temporal split** — train on 2023, test on unseen 2024 |
| What still isn't real | Everything (no observed boardings exist for these stops) | Hour-of-day demand *shape* and one-off special events — no public per-hour boarding curves or event logs exist; this is the honest residual gap (see [Caveats](#caveats)) |

The R² didn't jump dramatically — it was never the point. What changed is *what the model learned from*: real weather, a real calendar, and a real (if dated and concessionary-only) ridership signal, instead of distributions we invented. That's the difference between "self-consistent with our assumptions" and "anchored to the world as it actually is."

---

## Model Validation & Robustness

A single random-split R² is not enough to trust a demand model — it can hide row-level autocorrelation, sensitivity to a single noisy data source, or a model that has just memorised one slice of time. `analysis/robustness_analysis.py` runs three checks aimed squarely at that concern (full output: [`analysis/outputs/robustness.json`](analysis/outputs/robustness.json)):

| Check | Result | What it tells us |
|---|---|---|
| **i.i.d. / independence** — random split vs. temporal split (train 2023 → test 2024) | R² 0.949 (random) vs. 0.945 (temporal); gap = 0.004 | The model isn't leaning on row-level leakage between train and test — it generalises to a genuinely unseen year almost as well as to shuffled rows from the same period |
| **Sensitivity** — perturb the smartcard demand anchor by ±20% and retrain | R² spread = 0.0004 across baseline / −20% / +20% | The headline accuracy isn't an artefact of the exact (decade-old, concessionary-only) magnitude fixed by the smartcard anchor — the model is learning the *shape* of demand (by stop, time, weather), not the absolute scale of one source |
| **Domain shift** — train on one year/season, test on the other | Year shift avg R² = 0.945; season shift avg R² = 0.934 | Cross-year and cross-season transfer retain most of the in-distribution score — the model is mostly capturing stable structure (which stops are busy, when, in what weather), not memorising one year's quirks. The modest season-shift drop (0.945 → 0.934) is the honest bound on how far this model should be trusted to extrapolate without retraining |

This is also why the **headline R² changed from 0.949 (random 80/20 split) to 0.945 (temporal split, train-2023/test-2024)** between the table above and this one — the temporal figure is the one we now report as primary, because it's the one that can't be inflated by within-period leakage.

---

## Equity

The system is designed explicitly around the people most dependent on it. Every stop is mapped to its IMD 2019 Lower Super Output Area deprivation score. The dashboard exposes a deprivation overlay — colour-coded by IMD band — and reports a Gini coefficient of service coverage.

The highest-deprivation stops served:

| Stop | IMD Rank | Score |
|---|---|---|
| Dudley Rd (S06) | 312 / 32,844 | 0.88 |
| Ladywood Fire Station (S10) | 418 | 0.86 |
| Summerfield Park (S12) | 520 | 0.82 |

Dynamic routing serves all 15 stops on demand. The fixed timetable leaves several high-deprivation stops unserved outside peak hours.

---

## Repository Structure

```
prediction model/   XGBoost demand model + CVRP route optimiser
dashboard/          FastAPI backend + React/MapLibre frontend
simulation/         Unity multi-agent simulation + Arduino serial bridge
hardware/           Arduino FPGA LED controller
data/gtfs/          Real TfWM GTFS stop data, road geometry, service profiles
scripts/            GTFS mining, stop extraction, road geometry builder
analysis/           Economic model, equity analysis, feature explainability, GTFS validation
docs/               Architecture, model card, design decisions, references
tests/              pytest suite — routing invariants + API contract
```

---

## Getting Started

```bash
git clone https://github.com/ChrisLegge/ewb_bus_routing_project
cd ewb_bus_routing_project
pip install -r requirements.txt

# 1. Generate the real-data-anchored dataset + train demand model
python "prediction model/generate_real_demand_dataset.py"
python "prediction model/demand_route_optimizer.py"

# (the original synthetic generator is still available for comparison)
# python "prediction model/generate_map_dataset.py"

# 2. Build the React frontend
cd dashboard/web && npm install && npm run build && cd ../..

# 3. Serve the dashboard
uvicorn dashboard.api:app --port 8000
# Open http://localhost:8000
```

> The trained model (`demand_model.pkl`) and generated dataset are git-ignored — they are fully reproducible from the two steps above.

### Run the analysis scripts

```bash
python analysis/cost_model.py          # economic model (DfT sources)
python analysis/equity.py              # IMD 2019 deprivation analysis
python analysis/gtfs_validate.py       # synthetic vs real GTFS validation
python analysis/explainability.py      # XGBoost feature importance
python analysis/robustness_analysis.py --json   # i.i.d., sensitivity, domain-shift checks
```

### Run tests

```bash
pytest
```

---

## Data Sources

| Dataset | Source | Used for |
|---|---|---|
| TfWM GTFS feed | Transport for West Midlands (open licence) | Real stop coordinates, road geometry, service frequency validation |
| **West Midlands Accessibility & Travel Passes** | **UCL/GEoDS — ENCTS concessionary smartcard data, anonymised, linked to vehicle GPS (TfWM, 2010–2016)** | **Per-stop demand anchor — replaces the synthetic `base` boarding values with real observed concessionary journey volumes** |
| **Open-Meteo historical archive** | **Open-Meteo (ERA5/ECMWF reanalysis)** | **Real hourly Birmingham weather (2023–2024) — weather type, temperature, wind, precipitation, storm flags driving every training row** |
| **Birmingham school term & bank holiday calendar** | **Birmingham City Council term dates + GOV.UK bank holidays API** | **Real `is_school_term` flag for every training row (was a fixed monthly synthetic flag)** |
| IMD 2019 | MHCLG | Stop-level deprivation scoring + ML feature (`imd_score`) |
| OSM Overpass API | OpenStreetMap | POI density per stop (hospitals, schools, workplaces, shops) — ML feature (`poi_total`) |
| data.police.uk | UK Police open data | Street crime counts per stop, 2024 — ML feature (`crime_total_2024`) |
| Open-Meteo Elevation API | Open-Meteo (SRTM 90m) | Stop elevation — ML feature (`elevation_m`) |
| Census 2021 (TS007/TS045/TS058/TS061/TS062) | ONS | Age structure, car-free household rate, working-age population, commuting patterns |
| DfT BUS0101/BUS0102/BUS09 | Department for Transport | Regional bus statistics — punctuality, patronage trends, vehicle-km |
| BODS SIRI-VM live feed | DfT Bus Open Data Service | Live vehicle positions, delays, operator/line coverage near Ladywood |
| DfT BUS0404 | Department for Transport | Vehicle operating costs |
| DfT TAG A1.3 | Department for Transport | Passenger time value |
| ONS ASHE 2023 | Office for National Statistics | Ladywood median wage |

---

## Caveats

True commercial stop-route boarding counts are **not publicly released** by TfWM (we asked the question directly — see [Data Sources](#data-sources)). `generate_real_demand_dataset.py` therefore builds the training set from real, openly-licensed inputs wherever they exist:

- **Real exogenous variables** — every row uses observed Birmingham weather (Open-Meteo hourly archive, 2023–2024), the real school-term/bank-holiday calendar, and storm flags derived from observed conditions, in place of the original sampled distributions.
- **Real demand anchor** — each stop's relative demand level is now set from its real ENCTS concessionary smartcard journey volume (UCL/GEoDS, TfWM-linked, 2010–2016) rather than a hand-picked synthetic `base` value, with IMD/POI/crime/elevation added as genuine per-stop ML features.
- **Still synthetic** — the *hour-of-day demand shape* (commuter-peak curves) and one-off *special events* (festivals, road closures) remain modelled, since no public per-hour boarding curves or event logs exist for these stops. This is the honest residual gap, and the reason R² = 0.949 should still be read as *self-consistency with a realistically-anchored generator*, not validated real-world accuracy.

GTFS validation (`analysis/gtfs_validate.py`) compares the model's temporal pattern against real service frequency — see [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md) and [`analysis/outputs/gtfs_validation.json`](analysis/outputs/gtfs_validation.json) for the full discussion.

The remaining path to fully-observed accuracy: a direct TfWM Automatic Passenger Counting (APC) data request, or a manual stop-level traffic survey, to replace the smartcard-anchored + shape-modelled `boardings` with directly observed counts and a time-based train/test split.

---

## Team

| Name | Role |
|---|---|
| Arya Arun | Machine learning, demand model, analysis |
| Chris Legge | Hardware, FPGA, Arduino |
| Jack Booth | Unity simulation |

---

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Model Card](docs/MODEL_CARD.md)
- [Economic model methodology](docs/design/RUNNING_COSTS.md)
- [Stakeholder engagement design](docs/design/STAKEHOLDER_ENGAGEMENT.md)
- [User journeys](docs/design/USER_JOURNEYS.md)
- [Scalability](docs/design/SCALABILITY.md)
- [Dashboard README](dashboard/README.md)
