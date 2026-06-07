import { motion, AnimatePresence } from "framer-motion";
import type { Stop } from "./api";

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

export default function StopPanel({
  stop,
  boardings,
  onClose,
}: {
  stop: Stop | null;
  boardings: number;
  onClose: () => void;
}) {
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
            <Stat label="Points of interest" value={fmt(stop.poi_total)} />
            <Stat label="Population" value={fmt(stop.population)} />
            <Stat label="Crime (2024)" value={fmt(stop.crime_total_2024)} />
            <Stat label="Elevation" value={stop.elevation_m == null ? "—" : `${fmt(stop.elevation_m)} m`} />
          </div>

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
