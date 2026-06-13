import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Stop } from "./api";

const METRIC_DEFS: { label: string; def: string }[] = [
  { label: "Predicted boardings", def: "The demand model's estimate of how many passengers board here during the selected 2-hour window, under the chosen day / weather / event. This is the one live, model-driven number — it changes as you scrub the time of day (roughly 0 overnight up to ~200 at a busy stop in peak). The five below are fixed stop attributes." },
  { label: "IMD score", def: "Index of Multiple Deprivation (2019) for the stop's Lower Super Output Area — England's official measure of relative deprivation (income, employment, health, education, crime, housing, environment). The score runs ~0 (least deprived) to ~90 (most); higher = more deprived. Ladywood's stops sit between 27 and 68 — most in England's more-deprived half." },
  { label: "Points of interest", def: "Count of amenities (shops, services, civic buildings) within 400 m, from OpenStreetMap — a proxy for footfall and local activity. Across these stops it ranges from ~10 (quiet residential) to ~190 (a busy interchange). A dash (—) means OpenStreetMap returned no data for that stop, not zero amenities." },
  { label: "Population", def: "Resident population of the stop's surrounding Census area (an LSOA, designed to hold ~1,500–3,000 people). Here it ranges ~1,450–2,500 — the size of the immediate community the stop serves." },
  { label: "Crime (2024)", def: "Recorded crime incidents for 2024 (police.uk) across the stop's wider policing neighbourhood — which is why the figures run into the tens of thousands and are shared between nearby stops, rather than a single street's count. Used cautiously (see the crime-feature ablation): higher may indicate need for safer, more frequent evening service." },
  { label: "Elevation", def: "Height above sea level in metres (here 123–149 m — a modest spread). Included because hills affect walking distance to stops and journey times." },
];

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

const fmt = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined ? "—" : v.toFixed(digits);

// POI counts use -1 per category as an "OSM returned no data" sentinel, which
// can sum to a negative total — show those as unavailable, not a real count.
const fmtCount = (v: number | null | undefined) =>
  v === null || v === undefined || v < 0 ? "—" : v.toFixed(0);

export default function StopPanel({
  stop,
  boardings,
  onClose,
}: {
  stop: Stop | null;
  boardings: number;
  onClose: () => void;
}) {
  const [showGlossary, setShowGlossary] = useState(false);

  return (
    <AnimatePresence>
      {stop && (
        <motion.aside
          key={stop.stop_id}
          className="hud stop-panel"
          initial={{ opacity: 0, x: 32 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 32 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        >
          <button className="panel-close" onClick={onClose} aria-label="Close">
            ×
          </button>
          <span className="hud-eyebrow">{stop.stop_id} · {stop.importance}</span>
          <h2>{stop.name}</h2>
          <p className="panel-note">{stop.note}</p>

          <div className="stat-grid">
            <Stat label="Predicted boardings" value={fmt(boardings)} />
            <Stat label="IMD score" value={fmt(stop.imd_score, 1)} />
            <Stat label="Points of interest" value={fmtCount(stop.poi_total)} />
            <Stat label="Population" value={fmt(stop.population)} />
            <Stat label="Crime (2024)" value={fmt(stop.crime_total_2024)} />
            <Stat label="Elevation" value={stop.elevation_m == null ? "—" : `${fmt(stop.elevation_m)} m`} />
          </div>

          <button className="glossary-toggle" onClick={() => setShowGlossary((v) => !v)}>
            {showGlossary ? "Hide metric definitions ▴" : "What do these metrics mean? ▾"}
          </button>
          <AnimatePresence>
            {showGlossary && (
              <motion.dl
                className="glossary"
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
              >
                {METRIC_DEFS.map((m) => (
                  <div key={m.label} className="glossary-entry">
                    <dt>{m.label}</dt>
                    <dd>{m.def}</dd>
                  </div>
                ))}
              </motion.dl>
            )}
          </AnimatePresence>

          <div className="panel-routes">
            <span className="hud-eyebrow">Served by</span>
            <div className="route-chips">
              {stop.routes.map((r) => (
                <span key={r} className="route-chip">Route {r}</span>
              ))}
            </div>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
