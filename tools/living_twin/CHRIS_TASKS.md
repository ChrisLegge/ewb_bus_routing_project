# Chris — Task List (Hardware / FPGA / Verilog)

**Calendar:** today is Sat 13 Jun · team meeting Sun 14 · deck freeze Wed 17 · Grand Finals Fri 19.

Ordered so nothing blocks the team and the live demo never risks the freeze.
Tick them off in order — the first two are small and high-value, the third is the
big build (with a built-in safety net).

---

## 1. Your reflection — DUE at Sunday's meeting (blocks the team) ⏳

**File:** `docs/REFLECTIONS.md` → your section.

This is the single cheapest rubric gain in the competition (criterion 3a), and the
file is **live on the public repo right now still carrying its "DRAFT — judges can
smell ghost-written reflection" banner** until all three of us replace our sections.

Write ~300 words, first person, your voice. The factual anchors are already in the file:
- The WS2812B bit-bang driver and the Quartus STA timing-closure issue — what it taught
  you about the difference between *"it compiles"* and *"it's proven."*
- The decision to bake `route_plan.json` into ROM — accepting an honestly-static
  snapshot rather than faking liveness.
- Designing for a viewer with **no phone, no app, no English** — colour not words.
- The Repair Club model — repairable, commodity parts, no vendor lock-in.
- What you'd do differently — e.g. starting the LoRa link-budget survey earlier.

**When done:** delete the `*(DRAFT — personalise)*` tag from your heading.

---

## 2. The LoRa security paragraph — ~30 min, highest value-per-effort 🔴

**File:** write a new "§6 Security" section into `docs/radio_signalling_report.md`
(full guidance in `docs/FPGA_HARDENING.md` §1).

This closes the **last unanswered Tier-1 Q&A attack** — *"your 433 MHz broadcast is
unauthenticated, so anyone with a £15 transmitter can paint false demand onto every
LED map in Ladywood."*

Three sentences, three defences:
- **AES-128-CMAC** on every packet — the stop unit rejects any packet whose MAC doesn't
  verify against the pre-shared key.
- **Monotonic frame counter** — the receiver drops any packet with a counter ≤ the last
  seen, so a captured packet can't be replayed.
- **Fail-safe default** — on an invalid MAC, a stale counter, or no packet for N minutes,
  the display shows an explicit "no live data" pattern, never stale/attacker data.
  *A blank display is honest; a lying one isn't — and the people who depend on it most are
  the least able to catch a lie.*

---

## 3. The Living Twin — the showstopper build (Fri/Sat/Sun) ⭐

**File:** `tools/living_twin/BUILD_SPEC.md` is your full build doc — read it top to bottom
once before touching hardware.

In one line: the existing DE1-SoC LED map, but with **SW9** flipping it between the ROM
snapshot you submitted and a **live UART feed** of the real buses on lines 8A/8C/80/126,
fed from a Raspberry Pi polling the Bus Open Data Service. Same board, same Verilog, one
switch — and that light is the number 80 on Dudley Road, *right now*.

Three new modules (all testbench-able, none touch the WS2812B driver):
1. **`uart_rx.sv`** — standard 8-N-1 receiver at 9600 baud off the 50 MHz clock.
2. **`frame_rx.sv`** — byte FSM: wait `0xAA` sync → shift 15 payload bytes → verify XOR
   checksum → latch all 15 atomically (double-buffer; never display a half-frame).
3. **Mux into the existing data path** — `SW9 ? live_regs : rom_row`, replacing the
   ROM-row selection. Live colour: low nibble = demand tier (dimmed), high nibble ≠ 0 =
   bright "bus here" on that stop's LED.
4. **Staleness watchdog** — no valid frame for 60 s in live mode → slow amber "no live
   data" pulse. This is the fail-safe from FPGA_HARDENING §1, made physical and
   demonstrable on stage.

**The safety net:** SW9 down is always the ROM snapshot you already trust. If live mode
isn't solid by Sunday night, the demo ships as the ROM snapshot + the testbench evidence,
and nothing is lost. So this build can't put the deadline at risk — start it now and let
it breathe.

Pin note: Pi GPIO14 TX (3.3 V) → DE1-SoC GPIO RX + common ground, no level shifter
(both 3.3 V). Treat RX as asynchronous — 2-FF synchroniser before the UART FSM.

---

## 4. The HDL testbench — closes two gaps at once

**File:** `fpga/tb_bus_route.v` (or at minimum a one-paragraph "how we verified" note in
the FPGA README).

The software side has 16 passing tests; the FPGA side currently shows **no testbench**,
which a judge with any digital-design background will ask about. A self-checking
testbench that (a) drives `uart_rx` with a recorded byte stream and asserts the register
bank matches, and (b) checks the WS2812B T0H/T1H/T0L/T1L pulse timings against the
datasheet — **also produces exactly the HDL-verification evidence the hardening punch-list
asks for.** Two birds, one testbench. If you verified on-hardware by inspection instead,
that's a legitimate answer for a student project — but *state it* rather than leave it as
an implied gap.

---

## 5. WS2812B outdoors + a maintenance cost line

**Files:** a paragraph into the FPGA README (guidance in `docs/FPGA_HARDENING.md` §2),
plus one line into `docs/design/RUNNING_COSTS.md`.

The isometric render now advertises the physical stop unit, so the hardware-reality
question is invited: weatherproofing (IP65 enclosure, conformal-coated PCB), daylight
readability (high-brightness modules with ambient dimming, or an e-paper + LED hybrid),
vandalism (polycarbonate, internal fixings, solar so there's no mains to cut), and a
per-unit annual maintenance figure. Keep it honest and bounded.

---

## 6. Monday — wire the Pi to your board

Per the BUILD_SPEC bench-acceptance test: Pi (`hub.py`, reusing the
`tools/bods_avl/collect_avl.py` poll logic) → UART → your FPGA. Watch a real 80 move
S06 → S07 on the physical map within ~60 s of it happening on Dudley Road (cross-check
the dashboard or the BODS map). Then pull the UART wire → amber pulse → flip SW9 down →
ROM snapshot returns. All three behaviours working = ship.

**Register your own free BODS key** (2 min — signup link in
`tools/bods_avl/BODS_AVL_PIPELINE.md`). Don't share keys; the key file is gitignored.

---

## The 10-second version
Sunday: write your reflection. Before then if you can: the LoRa security paragraph
(30 min). Main build: the Living Twin HDL (`uart_rx` + `frame_rx` + SW9 mux per
`tools/living_twin/BUILD_SPEC.md`) — SW9 keeps the ROM demo as a safe fallback, so the
deadline is never at risk. The testbench doubles as your verification evidence. Monday we
wire the Pi.
