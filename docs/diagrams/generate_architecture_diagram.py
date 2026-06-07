"""Generates docs/diagrams/architecture.png — a matplotlib system-architecture
diagram matching the layer breakdown in docs/ARCHITECTURE.md."""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.path import Path

BG = "#0d1117"
BOX_FACE = "#161b22"
BOX_EDGE = "#58a6ff"
LEGACY_EDGE = "#8b949e"
TEXT = "#e6edf3"
SUBTEXT = "#8b949e"
ARROW = "#58a6ff"

fig, ax = plt.subplots(figsize=(13, 7.5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, 13)
ax.set_ylim(0, 7.5)
ax.axis("off")


def box(x, y, w, h, title, lines, edge=BOX_EDGE, dashed=False):
    style = "round,pad=0.12,rounding_size=0.12"
    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle=style,
        linewidth=1.6, edgecolor=edge, facecolor=BOX_FACE,
        linestyle="--" if dashed else "-",
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h - 0.32, title, ha="center", va="top",
            color=TEXT, fontsize=11, fontweight="bold", family="monospace")
    for i, line in enumerate(lines):
        ax.text(x + w / 2, y + h - 0.62 - i * 0.28, line, ha="center", va="top",
                color=SUBTEXT, fontsize=8.5, family="monospace")
    return (x, y, w, h)


def arrow(b1, b2, label=None, style="-|>", color=ARROW):
    x1, y1, w1, h1 = b1
    x2, y2, w2, h2 = b2
    start = (x1 + w1, y1 + h1 / 2)
    end = (x2, y2 + h2 / 2)
    if x2 + w2 / 2 == x1 + w1 / 2:
        start = (x1 + w1 / 2, y1)
        end = (x2 + w2 / 2, y2 + h2)
    a = FancyArrowPatch(start, end, arrowstyle=style, color=color,
                        linewidth=1.4, mutation_scale=14, shrinkA=2, shrinkB=2)
    ax.add_patch(a)
    if label:
        mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
        ax.text(mx, my + 0.18, label, ha="center", color=SUBTEXT, fontsize=7.5,
                family="monospace")


# Layer 1 — ingestion
ingestion = box(0.4, 4.6, 2.6, 2.0, "DATA INGESTION",
                ["scripts/fetch_*.py", "scripts/parse_*.py",
                 "GTFS, weather, census,", "IMD, crime, ENCTS..."])

# Layer 2 — demand model
demand = box(3.6, 4.6, 3.0, 2.0, "DEMAND MODEL",
             ["generate_real_demand_", "dataset.py",
              "→ demand_model.pkl", "(XGBoost, R²=0.945)"])

# Layer 3 — optimiser
optimiser = box(7.2, 4.6, 3.0, 2.0, "ROUTE OPTIMISER",
                ["demand_route_optimizer.py", "greedy + 2-opt",
                 "→ route_plan.json", "(1.16% mean gap vs. optimal)"])

arrow(ingestion, demand)
arrow(demand, optimiser)

# Single shared artefact label
ax.text(8.7, 4.35, "single shared artefact", ha="center",
        color=SUBTEXT, fontsize=8, style="italic", family="monospace")

# Layer 4 — three presentation outputs
dash = box(2.6, 1.6, 2.6, 1.9, "dashboard/",
           ["api.py (FastAPI)", "↓", "web/ (React + MapLibre)"])
fpga = box(5.6, 1.6, 2.6, 1.9, "fpga/",
           ["bus_route.v", "gen_rom.py → ROM tables", "WS2812B LED strip"])
unity = box(8.6, 1.6, 2.6, 1.9, "legacy/simulation/",
            ["Unity (LEGACY)", "Jack Booth", "superseded — reference only"],
            edge=LEGACY_EDGE, dashed=True)

# fan-out from route_plan.json
src = (6.9, optimiser[1])
for tgt in (dash, fpga, unity):
    end = (tgt[0] + tgt[2] / 2, tgt[1] + tgt[3])
    edge_color = LEGACY_EDGE if tgt is unity else ARROW
    style = "--" if tgt is unity else "-"
    a = FancyArrowPatch(src, end, arrowstyle="-|>", color=edge_color,
                        linewidth=1.3, mutation_scale=13, linestyle=style,
                        connectionstyle="arc3,rad=0.0", shrinkA=2, shrinkB=2)
    ax.add_patch(a)

ax.text(6.5, 7.2, "System Architecture — data flow to user-facing outputs",
        ha="center", color=TEXT, fontsize=14, fontweight="bold", family="monospace")
ax.text(6.5, 6.85, "route_plan.json is the single source of truth shared by all three presentation layers",
        ha="center", color=SUBTEXT, fontsize=9, family="monospace")

plt.tight_layout()
plt.savefig("docs/diagrams/architecture.png", dpi=180, facecolor=BG, bbox_inches="tight")
print("Saved docs/diagrams/architecture.png")
