# What 0.385 → 0.374 Actually Means — the Human-Units Translation

**The attack:** "Your equity dissimilarity index improved by 0.011. That's under 3%.
Your metrics are precise — but is the effect *meaningful*?" If you can't convert the
index into buses and people, the judge concludes the rigour is decorating a negligible
effect. This doc gives the conversion method, the worked sentence, and the honest
framing for why a small-looking number is the right-sized claim.

**Where this goes:** a short subsection in the equity analysis docs (next to wherever
0.385/0.374 is reported), plus a rehearsed spoken answer.

---

## The conversion (method, so the team can compute the exact figure)

The dissimilarity index D = ½ Σᵢ |sᵢ − dᵢ|, where sᵢ = stop i's share of *service*
(scheduled visits) and dᵢ = its share of *demand*. **D is directly interpretable: it is
the fraction of all service that would have to move to perfectly match demand.**

Therefore ΔD = 0.385 − 0.374 = **0.011 ≈ 1.1% of all daily stop-visits reallocated
from over-served toward under-served stops** — and in this network the under-served,
high-deprivation stops are S06 Dudley Rd (the City Hospital corridor, deprivation 0.88),
S10 Ladywood Fire Station (0.86; 57.9% of the ward has no car), and S12 Summerfield
Park (0.82).

To get the exact human number, compute once from the route plan:

```python
# visits_per_day = total scheduled stop-visits across the network per weekday
# (sum over routes of: departures/day × stops on route) — from route_plan.json
moved_visits_per_day = 0.011 * visits_per_day
```

Then the sentence becomes concrete, e.g. *"about N additional bus arrivals every day at
the hospital corridor and the no-car estates"* — fill N from the computation above and
quote it everywhere instead of the raw index.

## The honest framing (this is the part that wins the exchange)

1. **The gain is permanent and daily, not one-off.** N extra arrivals at the highest-
   deprivation stops *every single day*, structurally, by design — not a pilot bump.
2. **It's the conservative bound, and that's deliberate.** The reallocation was achieved
   under a hard constraint: no stop loses service below the floor, total fleet unchanged,
   zero new vehicles. The small delta is what equity improvement looks like when you
   refuse to rob Peter to pay Paul. An unconstrained optimiser could post a bigger ΔD —
   by stripping quiet stops. We consider that a worse design with a better number.
3. **The index can't saturate to 0 anyway**: perfect service-demand matching is
   infeasible under fixed fleet + service floor, so judging ΔD against 0.385→0 is the
   wrong yardstick; the right yardstick is the feasible frontier under the constraints.
4. **And we quoted it anyway.** "We could have quoted a bigger number. We quoted the
   true one." — the deck line applies here verbatim.

## The spoken answer (20 seconds)

> "0.011 is the fraction of daily service that moves toward under-served stops — about
> [N] extra bus arrivals a day, every day, at the hospital corridor and the estates where
> a majority of households have no car. It looks small because it's constrained to be
> honest: no stop drops below the service floor, no new buses, no robbing quiet stops to
> flatter the metric. That's the equity gain you can actually deploy — and we'd rather
> defend a real 1.1% than an imaginary 10."

## Action

- [ ] Compute `visits_per_day` from `route_plan.json` (one-liner above), fill N in.
- [ ] Add the subsection next to the reported index; quote N (not the raw index) in the deck's speaker notes.
