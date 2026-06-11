# LED Map Comprehension Test — Protocol (Designed, Scheduled, Not Yet Run)

**Why this exists:** Reviewer 1, verbatim — *"I'd like to see how the community would
relate to such a display (i.e. would it improve/confuse their experience, etc)."* The
display is the project's most-praised novelty and its least-tested interface. We cannot
run a community study before Grand Finals, but we can show the question has been
engineered, not ignored: a written protocol with pass/fail thresholds is the difference
between "we hadn't thought about it" and "designed, scheduled, not yet run."

**Where this goes:** `docs/DISPLAY_COMPREHENSION_PROTOCOL.md`, linked from the README
and from `STAKEHOLDER_ENGAGEMENT.md` Phase 1 (it slots directly into the co-design
workshops already designed there).

---

## Study design

**Participants:** 8–12 Ladywood residents recruited through CIVIC SQUARE's existing
community network, deliberately stratified to include: at least 2 participants aged 65+,
at least 2 whose first language is not English, at least 1 with a visual impairment, and
at least 2 regular bus users without smartphones. (These are the exact groups
`DEMOGRAPHIC_DESIGN_MAP.md` claims the display serves — so they are the groups who must
be able to read it.)

**Setting:** the physical LED map (or the bench unit) at a community venue, then ideally
at a bus stop in situ. No instruction given beyond "this shows the buses in Ladywood."

**Tasks (think-aloud, max 60 seconds each):**
1. **Locate:** "Which area has buses right now?"
2. **Rank:** "Where is there the most bus service at the moment?"
3. **Decode:** "What do you think the red colour means?"
4. **Act:** "You want to get to City Hospital. What does the map tell you?"
5. **Trust:** "If the map went completely dark, what would you assume?"

**Measures:**
- Task success (correct/incorrect/partial) per task per participant
- Time-to-answer
- Confidence (self-reported, 1–5)
- Free comments, especially confusion points and colour-meaning misreads

**Pass thresholds (pre-registered so the test can fail honestly):**
- ≥ 80% task-1/2 success across all participants
- ≥ 70% correct colour decoding **without** any legend
- No systematic failure concentrated in one demographic group — if e.g. the 65+
  participants fail task 3 while others pass, that is a *design defect*, not a user defect

**Design responses already anticipated:**
- If colour decoding fails → add a minimal 3-symbol legend plate (sun/cloud-style icons,
  not words — consistent with the colour-not-words principle for non-English-first users)
- If ranking fails → increase brightness contrast ratio between demand tiers
- If trust task reveals "dark = broken = ignore forever" → the "no live data" fallback
  pattern must be visually distinct from "off" (see FPGA hardening §1)

**Ethics note:** no personal data is collected; responses are anonymous task outcomes and
comments; participation is voluntary with a plain-language information sheet. (This is a
usability test of a public display, not human-subjects data processing — but we treat
consent and clarity as first-class anyway, consistent with the project's data ethics.)

---

## The spoken answer (when a judge raises Reviewer 1's question)

> "We agree — and we've designed the test. Twelve residents recruited through CIVIC
> SQUARE, stratified to include the exact groups the display claims to serve: elderly,
> non-English-first, no-smartphone. Five think-aloud tasks with pre-registered pass
> thresholds — including that no failure may concentrate in one demographic group, because
> that would be our design defect, not theirs. It's scheduled into the Phase-1 co-design
> workshops. We didn't want to run a token test before finals; we want to run the real one."
