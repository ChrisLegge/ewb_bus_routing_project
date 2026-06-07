# Scalability to Data-Sparse Contexts

How could this framework adapt to places where live bus data, Automatic
Passenger Counting (APC) infrastructure, or even a formalised transit system
are absent — rural contexts, informal paratransit networks, places where power
itself is a constraint on what's technically possible?

The system was built for Ladywood, but the **hardest version of this problem
is a context with no timetable, no APC, and limited power** — exactly that
kind of setting. The design is built to degrade gracefully toward it rather
than assume infrastructure that may not exist.

## The capability ladder

The framework needs only what a context can provide, and gets better as more
becomes available — it is never *blocked* on infrastructure it doesn't have:

| Tier | Data available | What the system uses | Output |
|---|---|---|---|
| **0 — Informal / paratransit** (matatu, jeepney, rural minibus) | Just stop locations + local knowledge | Hand-elicited demand profiles from co-design workshops, OSM/OSRM road geometry | Static, demand-aware *suggested* allocation; LED or even printed map |
| **1 — Ladywood today** | Real GTFS geography + a real-data-anchored demand model (see [Model Card](../MODEL_CARD.md)) | XGBoost trained on real weather/calendar/anchor data, modelled temporal shape | Per-window allocation + measured comparison to a fixed baseline (see [Key Results](../../README.md#key-results)) |
| **2 — Instrumented** | GTFS-RT + APC/ticketing data | Same model architecture, retrained on directly-observed counts | Validated, genuinely live re-allocation — closing exactly the gap the [Model Card](../MODEL_CARD.md#known-limitations--the-honest-gap) identifies as Ladywood's current honest residual |

The **same optimiser and the same screen-free interface** run at every tier;
only the *demand source* changes. A context with no formal timetable starts at
Tier 0 and climbs as data becomes available.

## Mapping the "nebulous route" problem

Where routes aren't fixed — informal transit being the clearest case — the
road graph still exists. Because this project's routing is built on real
**OSM/TfWM road geometry** loaded into a NetworkX graph (`G` in
`demand_route_optimizer.py`, with `nx.all_pairs_dijkstra_path_length` for
travel-time estimation) rather than a fixed GTFS shape file, the optimiser can
propose paths along real roads between demand points even where no official
route exists. This directly addresses the "routes might be even more
nebulous" concern — the underlying machinery doesn't actually require a
pre-defined route to function, only a road network and a set of stop-like
points.

## Power constraints

Power is a real, correctly-identified limiter for low-resource deployments —
and the architecture happens to already be frugal by design, not as a
retrofit:

- **Inference is tiny.** One XGBoost model, under 2 seconds per
  re-optimisation across all 32 scenario/window combinations — comfortably
  runs on a Raspberry Pi (~3–5 W), not a server rack.
- **Display is low-power.** The WS2812B LED map (`fpga/bus_route.v`) draws
  roughly 15 W on average, and is a natural fit for a small solar + battery
  setup; brightness can be scaled down further to cut draw — see the solar
  bus-shelter precedent pictured in
  [`docs/radio_signalling_report.md`](../radio_signalling_report.md#4-power-and-practicality).
- **No always-on connectivity required.** Route plans are precomputed and
  cached as a single static artefact (`route_plan.json` — see
  [Architecture](../ARCHITECTURE.md)); the model and optimiser run locally;
  only periodic data refresh needs any network connection at all, and even
  that could run over the same low-power LoRa link proposed for the live
  display path.
- **Screen-free by design.** No backlit screens, no per-rider devices — the
  most power- and cost-efficient public interface available, and (per
  [User Journeys → Amara](USER_JOURNEYS.md#1--amara--early-shift-cleaner-no-car-basic-phone))
  also the most inclusive one.

## What does *not* transfer unchanged

Honesty matters here as much as anywhere else in this project:

- **Demand profiles are culturally and locally specific.** Ladywood's
  commuter-peak curve is not a rural market-day curve, and is not a
  paratransit boarding pattern in another country. A Tier-0 deployment
  *requires* local co-design to elicit realistic profiles — you cannot copy
  the model's learned weights into a different context and expect them to
  mean anything. (This is the same honesty principle behind the [Model
  Card](../MODEL_CARD.md)'s insistence that Ladywood's own R²=0.945 measures
  self-consistency with a realistically-anchored generator, not validated
  real-world accuracy — the same caution applies, more strongly, to any
  cross-context transfer.)
- **"Stops" may be fuzzy in informal systems.** The discretisation into
  stop-hours that this whole pipeline depends on needs a local definition
  before any of the rest of the machinery can run.
- **Governance and trust must be rebuilt locally.** The CIVIC SQUARE
  stewardship model described in [Stakeholder
  Engagement](STAKEHOLDER_ENGAGEMENT.md) is a *template* for how a community
  can hold and govern a system like this — not something that can be
  transplanted wholesale into a different community's existing power
  structures and expectations.

## One-line summary

*The algorithm and the screen-free interface are portable and frugal — they
scale down to data-sparse, low-power contexts precisely because they can start
from human knowledge and a cached road map and only improve as real data
arrives. The demand model is the one part that is emphatically **not**
portable: it has to be re-anchored, re-validated, and re-owned locally every
time.*
