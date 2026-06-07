// Drives the live dashboard with Playwright and captures a sequence of
// screenshots into docs/figures/_dashboard_frames/, which assemble_gif.py
// then turns into docs/figures/dashboard_demo.gif.
//
// Prerequisite: the dashboard must be running locally —
//   uvicorn dashboard.api:app --reload   (terminal 1)
//   cd dashboard/web && npm run dev      (terminal 2)
//
// Run from dashboard/web/:  node ../../docs/diagrams/capture_dashboard_demo.mjs

import { chromium } from "playwright";
import { mkdirSync } from "fs";

const URL = process.env.DASHBOARD_URL || "http://localhost:5173";
const OUT_DIR = "../../docs/figures/_dashboard_frames";
const VIEWPORT = { width: 1280, height: 800 };

mkdirSync(OUT_DIR, { recursive: true });

let frame = 0;
async function shot(page, holdMs = 600, steps = 3) {
  for (let i = 0; i < steps; i++) {
    await page.screenshot({ path: `${OUT_DIR}/frame_${String(frame).padStart(3, "0")}.png` });
    frame++;
    await page.waitForTimeout(holdMs / steps);
  }
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: VIEWPORT });

await page.goto(URL, { waitUntil: "networkidle" });
await shot(page, 1200);                       // initial map load

// Click a stop marker to open the detail panel
const stop = page.locator("[data-testid='stop-marker'], .maplibregl-marker").first();
if (await stop.count()) {
  await stop.click({ force: true });
  await shot(page, 1400);
}

// Toggle the IMD equity overlay if a control exists
const overlayToggle = page.getByRole("button", { name: /equity|imd/i }).first();
if (await overlayToggle.count()) {
  await overlayToggle.click();
  await shot(page, 1400);
}

// Open scenario comparison if available
const compareToggle = page.getByRole("button", { name: /compare|scenario/i }).first();
if (await compareToggle.count()) {
  await compareToggle.click();
  await shot(page, 1400);
}

await browser.close();
console.log(`Captured ${frame} frames to ${OUT_DIR}`);
