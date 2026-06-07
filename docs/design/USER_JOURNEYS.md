# User Journeys

How real people would actually interact with this system — including people
who do **not** use a smartphone, and the bus drivers who'd have to operate it.
Three personas grounded in Ladywood's real demographics: **57.9% of households
have no car** (ONS Census 2021), it's among the more deprived wards in
England, and it has large shift-working and elderly cohorts.

---

## 1. Amara — early-shift cleaner, no car, basic phone

**Context.** 05:40, needs to reach a city-centre office to start at 06:30. No
smartphone data; relies entirely on the bus and the physical stop.

**Today.** The fixed early-morning service runs too late or too infrequently
at that hour; she risks being late, or pays for a taxi she can't afford.

**With the system.** The demand model — anchored to real UCL/GEoDS smartcard
journey data (see [Model Card](../MODEL_CARD.md)) — predicts the recurring
early-shift demand spike at her stop, and the optimiser keeps an early vehicle
allocated there rather than treating "Early Morning" as a uniformly
low-priority window. The **FPGA LED map at the stop** glows brighter at her
stop and animates the approaching bus moving along the line — *no app, no
data plan, no account needed*.

**Why the LED map matters**: it's the inclusive interface. Amara reads
real-time-style status the same way a smartphone user reads an app, without a
device, account, or data — see [`fpga/README.md`](../../fpga/README.md) for
how the display itself works (and its current honest limitation: it's a
snapshot display today, with [a proposed LoRa-based path to making it
live](../radio_signalling_report.md)).

---

## 2. Ron — 74, reduced mobility, anxious about missing the bus

**Context.** Travels mid-morning to the Ladywood Health Centre. Worried about
standing too long in the cold, or missing a connection he can't easily recover
from.

**Today.** Timetables are static and frequently wrong after years of service
cuts; the resulting uncertainty keeps him at home — a known social-isolation
risk for elderly residents in deprived wards.

**With the system.** Mid-morning demand at his stop is modest but
*consistently predicted* — and because the optimiser is capacity-aware
(`BUS_CAPACITY = 40`, `MIN_DEMAND_VISIT = 2.0` in
[`demand_route_optimizer.py`](../../prediction%20model/demand_route_optimizer.py)),
a vehicle is reliably routed past it rather than skipped in favour of only the
highest-demand hub. The LED map's dwell/approach animation gives him a clear,
glanceable "your bus is two stops away" cue — exactly the kind of confidence
that turns "maybe I shouldn't risk going out" into "I know when to leave."

**Design response to a real risk**: equity isn't incidental here — it's
encoded directly in the optimiser's constraints, and measured afterwards by
the allocation-mismatch index in [`analysis/equity.py`](../../analysis/equity.py)
(see the README's [Equity](../../README.md#equity) section for the actual
measured numbers).

---

## 3. Dan — bus driver receiving a live-updated route

**Context.** Starts a shift; under a fully-deployed dynamic system, his
vehicle could be re-allocated between time windows based on predicted demand.

**Today.** Drivers follow a fixed, published route. "Dynamic routing" is
meaningless — and potentially alarming — to a driver without a clear, safe,
predictable way to receive and act on changes.

**With the system (a designed, not-yet-built operational layer).**
- Route changes are issued **between** time windows, never mid-trip, and only
  from a small, fixed set of pre-approved route variants per service — a
  driver never improvises, and passengers can still be reliably told which
  buses serve which stops.
- An in-cab display shows the next window's stop list; changes require
  explicit driver acknowledgement — the same kind of ACK pattern already used
  on the project's Arduino serial bridge (`legacy/simulation/`).
- Union and operational buy-in is a precondition, not an afterthought — see
  [Stakeholder Engagement](STAKEHOLDER_ENGAGEMENT.md), where drivers are
  listed as a stakeholder group with real veto power over change cadence.

**Honest limitation**: this operational layer is *designed, not built*. The
current prototype demonstrates the *allocation* (the optimiser, the dashboard,
the FPGA display); a safe, driver-facing rollout — with the radio-link
architecture sketched in [`docs/radio_signalling_report.md`](../radio_signalling_report.md)
as one candidate path — is the clearly-scoped next engineering step, and we'd
rather say that plainly than imply it already exists.

---

## How people are classified "beyond numbers"

The model doesn't see individuals; it sees **stop-hours under conditions**
(see [Model Card](../MODEL_CARD.md) for exactly what features it uses). The
equity work is in *how the optimiser spends capacity* once it has a
prediction:

- It will not strand medium/low-demand residential stops to chase a single
  high-demand hub — the capacity cap forces spread across the network.
- Stop "importance" tiers (major/medium/minor, set in `STOPS` in
  `demand_route_optimizer.py`) keep residential and interchange stops in the
  served set, not just commercial centres.
- The deliberately **non-smartphone** interface (the FPGA LED map) is a
  considered choice for a low-income, mixed-digital-literacy ward — a
  meaningful share of West Midlands residents lack reliable home internet
  access, and Amara's journey above shows exactly why that choice matters in
  practice rather than as an abstract inclusivity checkbox.
