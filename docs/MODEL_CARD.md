# Model Card — Ladywood Demand Predictor

Following the spirit of [Mitchell et al., "Model Cards for Model Reporting"
(2019)](https://arxiv.org/abs/1810.03993): what this model is, what it was
trained on, how it performs, and — most importantly — exactly where its
limits are.

## Model details

- **Type**: XGBoost gradient-boosted regression tree ensemble
- **Task**: predict `boardings` (passenger count) for a given Ladywood bus
  stop, hour of day, and set of conditions (day type, weather, special event,
  school/university term)
- **Training script**: `prediction model/generate_real_demand_dataset.py`
- **Artefact**: `prediction model/demand_model.pkl`
- **Runtime entry point**: `predict_window_demand()` — called live by the
  dashboard's `/api/demand` endpoint and offline by the route optimiser

## Intended use

Generating *relative* demand signals — which stops, at which times, under
which conditions, are likely to see more or fewer boarders than others — to
drive a capacitated VRP route optimiser and a public-facing demand
visualisation. **It is not** intended as a source of absolute, audited
ridership counts, nor as a substitute for a direct Automatic Passenger
Counting (APC) data feed (see [Caveats](#known-limitations--the-honest-gap)).

## Training data — what's real and what isn't

| Component | Status | Source |
|---|---|---|
| Stop coordinates, road geometry | **Real** | TfWM GTFS (open licence) |
| Weather (2023–24, hourly) | **Real** | Open-Meteo historical archive |
| School/university term dates | **Real** | Birmingham LA term + bank-holiday calendars |
| Per-stop demand anchor | **Real** | UCL/GEoDS ENCTS concessionary smartcard journey volumes, TfWM-linked, 2010–2016 |
| Per-stop static features (`imd_score`, `poi_total`, `population`, `crime_total_2024`, `elevation_m`) | **Real** | IMD 2019, OSM, ONS Census 2021, police.uk, elevation API |
| **Hour-of-day demand shape** (commuter-peak curves) | **Synthetic** | Modelled — no public per-hour boarding curves exist for these stops |
| **Special events** (festivals, road closures) | **Synthetic** | Modelled — no public event/disruption logs exist for these stops |

263,160 rows (every real day in the 2023–24 weather archive × 15 stops × 24
hours), built by `generate_real_demand_dataset.py`. This supersedes an earlier,
fully-synthetic 65k-row baseline (`generate_map_dataset.py`) which is retained
in the repo for the before/after comparison documented in the
[README](../README.md#from-synthetic-to-real-how-the-demand-model-evolved).

## Headline performance

| Metric | Value | Split |
|---|---|---|
| **R² (primary, reported)** | **0.945** (RMSE 4.57 boardings) | Temporal — train 2023, test unseen 2024 |
| R² (random split) | 0.949 (RMSE 4.45) | Random 80/20 |

The temporal split is reported as primary because it cannot be inflated by
within-period row leakage — it's the honest measure of "how well does this
generalise to a year it has never seen."

## Robustness — six independent checks (full data: [`robustness.json`](../analysis/outputs/robustness.json))

| Check | Result | What it rules out |
|---|---|---|
| Random vs. temporal split | R² 0.949 vs. 0.945 (gap = 0.004) | Row-level autocorrelation inflating the headline score |
| Anchor sensitivity (±20% perturbation of the smartcard demand anchor) | R² spread = 0.0004 (0.9439 / 0.9439 / 0.9443) | The result being an artefact of the *exact magnitude* of one decade-old, concessionary-only data source — the model is learning demand *shape*, not memorising one source's scale |
| Year shift (train 2023→test 2024 and reverse) | avg R² = 0.9449 | The model memorising one year's idiosyncrasies rather than stable structure |
| Season shift (train winter→test summer and reverse) | avg R² = 0.9339 | — and quantifies the honest bound: a ~0.011 drop is the expected, informative cost of extrapolating across a seasonal regime change |

**Interpretation**: the 0.945 headline is stable under every stress test we
could construct from available data. The one consistent, expected weak point
is cross-season transfer (0.934 vs. 0.945 in-distribution) — exactly what
you'd expect from a model that has correctly learned "winter and summer demand
patterns differ" rather than memorised a single regime.

## Known limitations — the honest gap

This is the single most important section of this card, and the project's
central honesty disclosure (also covered in the README's
[Caveats](../README.md#caveats)):

> **The *absolute scale* and *hour-of-day shape* of demand at these specific
> stops have never been directly observed.** No public per-hour boarding
> curves or event/disruption logs exist for Ladywood stops. The 0.945 R² should
> therefore be read as *"this model is highly self-consistent with a
> realistically-anchored generative process,"* **not** *"this model has been
> validated against ground-truth ridership."* The per-stop demand *anchor* is
> real (UCL/GEoDS smartcard data); the *temporal curve* layered on top of that
> anchor is the project's own, carefully-reasoned, but ultimately synthetic
> construction.

A second, related check — `analysis/gtfs_validate.py`, comparing the model's
predicted hour-of-day demand *shape* per stop against real TfWM GTFS service
frequency as a proxy for ridership pattern — returns a **median Pearson
correlation of 0.06** across the 45 stop/day-type combinations evaluated (full
data: [`gtfs_validation.json`](../analysis/outputs/gtfs_validation.json)). We
report this number plainly rather than omit it: it confirms that *service
frequency* is a weak proxy for *ridership shape* at this resolution (operators
set timetables on more than just measured demand — political, contractual, and
historical constraints all play in), and it underlines why the anchor-based,
not shape-validated, framing above is the correct one to present. **The path
to closing this gap is a direct TfWM Automatic Passenger Counting (APC) data
request or a manual stop-level traffic survey** — see
[Caveats](../README.md#caveats) for the full discussion of next steps.

## Ethical considerations

- The demand anchor (UCL/GEoDS smartcard data) is **concessionary-only**
  (predominantly older and disabled passengers) and **decade-old**
  (2010–2016). Both the anchor-sensitivity check above and the explicit
  framing in this card exist specifically to bound and disclose that
  limitation rather than let it pass silently.
- Predicted demand directly drives which stops get more service under the
  optimiser — an under- or over-estimate at a given stop has a real equity
  consequence. This is why [`analysis/equity.py`](../analysis/equity.py)
  exists as a standing check on the optimiser's output, not just the model's
  accuracy (see the README's [Equity](../README.md#equity) section).
