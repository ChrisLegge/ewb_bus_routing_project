import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import MapView from "./MapView";
import StopPanel from "./StopPanel";
import { fetchScenarios, fetchRoutes, fetchDemand, type RouteInfo, type Stop } from "./api";
import "./app.css";

const WINDOWS = [
  { label: "Early Morning", hour: 6, hours: "05:00-07:00" },
  { label: "AM Peak", hour: 8, hours: "07:00-09:00" },
  { label: "Mid Morning", hour: 10, hours: "09:00-11:00" },
  { label: "Lunch", hour: 12, hours: "11:00-13:00" },
  { label: "Afternoon", hour: 14, hours: "13:00-16:00" },
  { label: "PM Peak", hour: 17, hours: "16:00-18:00" },
  { label: "Evening", hour: 19, hours: "18:00-21:00" },
  { label: "Night", hour: 22, hours: "21:00-24:00" },
];

function App() {
  const [scenarios, setScenarios] = useState<string[]>([]);
  const [scenario, setScenario] = useState<string>("");
  const [windowIdx, setWindowIdx] = useState(1); // AM Peak default
  const [routes, setRoutes] = useState<RouteInfo[]>([]);
  const [selectedStop, setSelectedStop] = useState<Stop | null>(null);
  const [demand, setDemand] = useState<Record<string, number>>({});
  const [imdOverlay, setImdOverlay] = useState(false);
  const [loading, setLoading] = useState(true);

  const win = WINDOWS[windowIdx];

  useEffect(() => {
    fetchScenarios().then((s) => {
      setScenarios(s);
      if (s.length) setScenario(s[0]);
    });
  }, []);

  useEffect(() => {
    if (!scenario) return;
    setLoading(true);
    fetchRoutes(scenario, win.label)
      .then((r) => setRoutes(r.routes ?? []))
      .finally(() => setLoading(false));
  }, [scenario, win.label]);

  useEffect(() => {
    fetchDemand(win.hour).then((d) => setDemand(d.predictions));
  }, [win.hour]);

  return (
    <div className="app-shell">
      <MapView hour={win.hour} routes={routes} onSelectStop={setSelectedStop} imdOverlay={imdOverlay} />

      <AnimatePresence>
        {loading && (
          <motion.div
            className="loading-veil"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <span className="loading-pulse" />
          </motion.div>
        )}
      </AnimatePresence>

      <StopPanel
        stop={selectedStop}
        boardings={selectedStop ? demand[selectedStop.stop_id] ?? 0 : 0}
        onClose={() => setSelectedStop(null)}
      />

      <motion.header
        className="hud hud-top"
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="hud-title">
          <span className="hud-eyebrow">Ladywood · Birmingham</span>
          <h1>Predictive Bus Routing</h1>
        </div>
      </motion.header>

      <motion.div
        className="hud hud-bottom"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="scenario-row">
          <select
            className="scenario-select"
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
          >
            {scenarios.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={win.label}
            className="time-row"
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.25 }}
          >
            <span className="time-label">{win.hours}</span>
            <span className="time-window">{win.label} · {routes.length} buses live</span>
          </motion.div>
        </AnimatePresence>

        <input
          type="range"
          min={0}
          max={WINDOWS.length - 1}
          step={1}
          value={windowIdx}
          onChange={(e) => setWindowIdx(Number(e.target.value))}
          className="time-slider"
        />
        <div className="legend">
          {imdOverlay ? (
            <>
              <span className="legend-dot imd-low" /> Less deprived
              <span className="legend-dot imd-high" /> More deprived
            </>
          ) : (
            <>
              <span className="legend-dot major" /> Major
              <span className="legend-dot medium" /> Medium
              <span className="legend-dot minor" /> Minor
            </>
          )}
          <span className="legend-spacer" />
          <button
            className={`overlay-toggle${imdOverlay ? " active" : ""}`}
            onClick={() => setImdOverlay((v) => !v)}
          >
            {imdOverlay ? "Showing IMD equity overlay" : "Show IMD equity overlay"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

export default App;
