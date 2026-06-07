"""Assembles docs/figures/_dashboard_frames/*.png (captured by
capture_dashboard_demo.mjs) into docs/figures/dashboard_demo.gif."""

import glob
from PIL import Image

FRAMES_DIR = "docs/figures/_dashboard_frames"
OUT_PATH = "docs/figures/dashboard_demo.gif"
TARGET_WIDTH = 720
FRAME_DURATION_MS = 180

paths = sorted(glob.glob(f"{FRAMES_DIR}/*.png"))
if not paths:
    raise SystemExit(f"No frames found in {FRAMES_DIR} — run capture_dashboard_demo.mjs first")

frames = []
for p in paths:
    im = Image.open(p).convert("RGB")
    ratio = TARGET_WIDTH / im.width
    im = im.resize((TARGET_WIDTH, int(im.height * ratio)))
    frames.append(im)

frames[0].save(
    OUT_PATH, save_all=True, append_images=frames[1:],
    duration=FRAME_DURATION_MS, loop=0, optimize=True,
)
print(f"Saved {OUT_PATH} ({len(frames)} frames)")
