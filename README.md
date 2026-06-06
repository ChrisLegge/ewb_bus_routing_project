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
| **Demand model** | XGBoost trained on 65k synthetic rows; predicts boardings per stop per hour across weather, season, and event conditions |
| **Route optimiser** | Capacitated VRP — greedy construction + 2-opt local search; 0.4% mean gap above brute-force optimal; < 2s solve time |
| **Web dashboard** | FastAPI + React 19 + MapLibre GL; real TfWM stop coordinates; buses animate along real Ladywood road geometry |
| **Unity simulation** | Multi-agent bus system driven by the live ML output; same routing logic as the dashboard |
| **FPGA LED map** | Terasic DE1-SoC driving 156 WS2812B LEDs; a physical, screen-free network display for the community |

---

## Key Results

| Metric | Value |
|---|---|
| Demand model R² | 0.940 (RMSE 4.3 boardings) |
| Routing optimality gap | 0.4% mean above optimal |
| Routes solved optimally | 99% |
| Solve time | < 2 s |
| Real stops modelled | 15 (TfWM routes 8A/8C, 80, 126) |
| Operating cost saving | ~£10k/yr (DfT BUS0404 methodology) |
| Break-even | ~5.5 months |
| Social value (DfT TAG) | ~£194k/yr passenger time savings |
| Deprivation coverage uplift | +19.5% (IMD 2019 weighted) |

All figures are reproducible — see [Getting Started](#getting-started).

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

# 1. Generate synthetic dataset + train demand model
python "prediction model/generate_map_dataset.py"
python "prediction model/demand_route_optimizer.py"

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
| IMD 2019 | MHCLG | Stop-level deprivation scoring |
| DfT BUS0404 | Department for Transport | Vehicle operating costs |
| DfT TAG A1.3 | Department for Transport | Passenger time value |
| ONS ASHE 2023 | Office for National Statistics | Ladywood median wage |
| Census 2021 | ONS | Car-free household rate |

---

## Caveats

The demand model is trained on **synthetic data**, not observed ridership. R² = 0.94 measures self-consistency with the generator, not real-world accuracy. GTFS validation shows mean Pearson r = 0.32 against real service frequency — temporal patterns diverge (synthetic peaks AM/PM; real network peaks afternoon). Both are documented honestly in [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md) and [`analysis/outputs/gtfs_validation.json`](analysis/outputs/gtfs_validation.json).

The path to real accuracy: replace synthetic `boardings` with TfWM APC or ticketing data, retrain with a time-based train/test split.

---

## Team

| Name | Role |
|---|---|
| Arya Arun | Machine learning, demand model, analysis |
| Stefan Cius | ML validation, data pipeline |
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
