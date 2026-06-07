import { useState } from "react";
import { motion } from "framer-motion";
import MapView from "./MapView";
import "./app.css";

const HOUR_LABELS: Record<number, string> = {
  5: "Early Morning", 7: "AM Peak", 9: "Mid Morning", 11: "Lunch",
  13: "Afternoon", 16: "PM Peak", 18: "Evening", 21: "Night",
};

function App() {
  const [hour, setHour] = useState(8);

  return (
    <div className="app-shell">
      <MapView hour={hour} />

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
        <div className="time-row">
          <span className="time-label">{String(hour).padStart(2, "0")}:00</span>
          <span className="time-window">{HOUR_LABELS[hour] ?? "—"}</span>
        </div>
        <input
          type="range"
          min={0}
          max={23}
          step={1}
          value={hour}
          onChange={(e) => setHour(Number(e.target.value))}
          className="time-slider"
        />
        <div className="legend">
          <span className="legend-dot major" /> Major
          <span className="legend-dot medium" /> Medium
          <span className="legend-dot minor" /> Minor
          <span className="legend-spacer" />
          <span className="legend-hint">Dot size = predicted boardings</span>
        </div>
      </motion.div>
    </div>
  );
}

export default App;
