# FPGA LED map — `bus_route.v`

DE1-SoC (Cyclone V 5CSEMA5F31C6) design that drives a 156-LED WS2812B strip,
animating three buses over the Ladywood stop topology and colour-coding stops
by the predicted demand from `route_plan.json`. ROM tables are auto-generated
by `gen_rom.py` from the same prediction-model output the dashboard consumes.

This is the cleaned working copy. The original source and Quartus compile/
timing-analysis bundle (which **fails timing closure** — see below) live in
[`legacy/fpga/`](../legacy/fpga/) for reference.

## Changes vs. the legacy source

Two mechanical, behaviour-preserving fixes applied (no logic/timing-relationship
changes, just removing things that were actively hurting STA results):

1. **Removed a stray backtick** after `endcase` in the WS2812B driver block —
   not valid Verilog (backticks are preprocessor-directive syntax only);
   Quartus silently tolerated it but it could break other toolchains.
2. **Converted 6 always-blocks from async to synchronous reset**
   (`posedge CLOCK_50 or negedge rst_n` → `posedge CLOCK_50`, keeping the
   `if (!rst_n) ... else ...` body unchanged). `rst_n` is already debounced
   through a 2-FF synchroniser (`rst_sync`), so using it asynchronously with
   this much fan-out was reintroducing exactly the recovery/removal-timing
   problem the synchroniser exists to avoid.

## Known remaining issue — setup timing is NOT yet closed

The legacy `.sta.summary` shows **Setup slack of −11.24 ns (TNS −1847 ns)**
across all 4 PVT corners — the combinational chain feeding `cur_color`
(an ~18-way priority encoder fed by chained ROM lookups: `route_stop_led →
get_path_id → get_path_len/path_rom`, `demand_rom → stop_color`) is too deep
to settle within one 20 ns CLOCK_50 period. The two fixes above should clear
the Recovery/Removal/Min-Pulse-Width failures, but **setup closure requires
retiming** (e.g. latching `cur_color` once per LED rather than recomputing it
every clock — there's ~1,500 cycles of slack per LED to exploit). That's a
real cycle-accuracy change to the bit-bang FSM and needs simulation/hardware
verification before it goes in — not something to do blind. Re-run Quartus +
TimeQuest on this cleaned copy first to confirm the corner-by-corner deltas,
then tackle setup as a follow-up.
