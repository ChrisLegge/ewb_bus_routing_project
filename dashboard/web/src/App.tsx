import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import MapView from "./MapView";
import StopPanel from "./StopPanel";
import ConditionsPanel, { type Conditions } from "./ConditionsPanel";
import ComparePanel from "./ComparePanel";
import StoryOverlay from "./StoryOverlay";
import { STORY } from "./story";
import { fetchScenarios, fetchRoutes, fetchDemand, type RouteInfo, type RoutesResponse, type Stop } from "./api";
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

function HeadlineStat({ value, label }: { value: string; label: string }) {
  return (
    <div className="headline-stat">
      <span className="headline-value">{value}</span>
      <span className="headline-label">{label}</span>
    </div>
  );
}

function App() {
  const [scenarios, setScenarios] = useState<string[]>([]);
  const [scenario, setScenario] = useState<string>("");
  const [windowIdx, setWindowIdx] = useState(1); // AM Peak default
  const [routes, setRoutes] = useState<RouteInfo[]>([]);
  const [currentPlan, setCurrentPlan] = useState<RoutesResponse | null>(null);
  const [comparing, setComparing] = useState(false);
  const [compareScenario, setCompareScenario] = useState<string>("");
  const [comparePlan, setComparePlan] = useState<RoutesResponse | null>(null);
  const [selectedStop, setSelectedStop] = useState<Stop | null>(null);
  const [demand, setDemand] = useState<Record<string, number>>({});
  const [imdOverlay, setImdOverlay] = useState(false);
  const [loading, setLoading] = useState(true);
  const [conditions, setConditions] = useState<Conditions>({
    dayType: "weekday",
    weather: "sunny",
    specialEvent: "none",
    isSchoolTerm: true,
    isUniTerm: true,
  });
  const [storyActive, setStoryActive] = useState(false);
  const [storyStep, setStoryStep] = useState(0);

  // Apply the current story step's settings to the live dashboard state
  useEffect(() => {
    if (!storyActive) return;
    const s = STORY[storyStep];
    setScenario(s.scenario);
    setWindowIdx(s.windowIdx);
    if (s.imdOverlay !== undefined) setImdOverlay(s.imdOverlay);
    if (s.comparing !== undefined) setComparing(s.comparing);
    if (s.compareScenario !== undefined) setCompareScenario(s.compareScenario);
    setSelectedStop(null);
  }, [storyActive, storyStep]);

  const startStory = () => { setStoryStep(0); setStoryActive(true); };
  const exitStory = () => setStoryActive(false);

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
      .then((r) => { setRoutes(r.routes ?? []); setCurrentPlan(r); })
      .finally(() => setLoading(false));
  }, [scenario, win.label]);

  useEffect(() => {
    if (!comparing || !compareScenario) { setComparePlan(null); return; }
    fetchRoutes(compareScenario, win.label).then(setComparePlan);
  }, [comparing, compareScenario, win.label]);

  // Default the compare scenario to the first different one available
  useEffect(() => {
    if (comparing && !compareScenario) {
      const other = scenarios.find((s) => s !== scenario);
      if (other) setCompareScenario(other);
    }
  }, [comparing, compareScenario, scenarios, scenario]);

  useEffect(() => {
    fetchDemand(win.hour, {
      day_type: conditions.dayType,
      weather: conditions.weather,
      special_event: conditions.specialEvent,
      is_school_term: conditions.isSchoolTerm ? 1 : 0,
      is_uni_term: conditions.isUniTerm ? 1 : 0,
    }).then((d) => setDemand(d.predictions));
  }, [win.hour, conditions]);

  return (
    <div className="app-shell">
      <MapView routes={routes} demand={demand} onSelectStop={setSelectedStop} imdOverlay={imdOverlay} />

      {!storyActive && <ConditionsPanel conditions={conditions} onChange={setConditions} />}

      <StoryOverlay
        active={storyActive}
        step={storyStep}
        onNext={() => setStoryStep((i) => Math.min(i + 1, STORY.length - 1))}
        onPrev={() => setStoryStep((i) => Math.max(i - 1, 0))}
        onExit={exitStory}
      />

      <ComparePanel
        active={comparing}
        scenarios={scenarios}
        scenario={scenario}
        compareScenario={compareScenario}
        onCompareChange={setCompareScenario}
        current={currentPlan}
        compare={comparePlan}
      />

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
        <div className="headline-stats">
          <HeadlineStat value="57.9%" label="households with no car" />
          <HeadlineStat value="0.945" label="demand model R² (unseen 2024 data)" />
          <HeadlineStat value="263k" label="rows anchored to real ridership + weather" />
          <HeadlineStat value="1.16%" label="optimiser gap vs. brute-force optimal" />
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
        {currentPlan?.unserved_stops && currentPlan.unserved_stops.length > 0 && (
          <div className="unserved-row">
            <span className="unserved-icon">⚠</span>
            <span className="unserved-text">
              {currentPlan.unserved_stops.length} area{currentPlan.unserved_stops.length > 1 ? "s" : ""} left underserved this window —{" "}
              {currentPlan.unserved_stops
                .slice(0, 3)
                .map((u) => `${u.stop} (${u.demand.toFixed(0)})`)
                .join(", ")}
              {currentPlan.unserved_stops.length > 3 ? ", …" : ""}
            </span>
          </div>
        )}

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
          <button className="overlay-toggle story-launch" onClick={startStory}>
            ▶ Play the story
          </button>
          <button
            className={`overlay-toggle${comparing ? " active" : ""}`}
            onClick={() => setComparing((v) => !v)}
          >
            {comparing ? "Comparing scenarios" : "Compare scenarios"}
          </button>
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
