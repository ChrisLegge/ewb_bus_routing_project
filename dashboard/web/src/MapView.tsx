import { useEffect, useRef, useState } from "react";
import maplibregl, { Map as MlMap, Marker, Popup } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { fetchStops, type Stop, type RouteInfo } from "./api";
import BusLayer from "./BusLayer";

// Minimalist dark basemap — Apple-Maps-at-night feel: muted greys, no clutter,
// just roads, water, and place labels turned down to a whisper.
const STYLE_URL = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const IMPORTANCE_COLOR: Record<string, string> = {
  major: "#0a84ff",
  medium: "#5ac8fa",
  minor: "#8e8e93",
};

// Tier becomes the *quiet* channel: a thin ring, not a loud fill. Demand owns
// the fill colour now — the thing the product predicts is the thing you see.
const TIER_RING: Record<string, number> = { major: 3, medium: 2, minor: 1.2 };

function radiusForDemand(boardings: number): number {
  // Smooth, perceptual scaling — sqrt so area (not radius) tracks demand.
  return 6 + Math.sqrt(Math.max(boardings, 0)) * 1.6;
}

// Demand "heat" for the breathing pulse — teal (quiet) → amber → red (busy).
function demandGlow(t: number): string {
  const c = Math.max(0, Math.min(1, t));
  const ramp: [number, number, number][] = [
    [46, 110, 140],   // calm steel-blue (quiet)
    [224, 160, 40],   // amber (mid)
    [220, 38, 38],    // red   (busy)
  ];
  const seg = c * (ramp.length - 1);
  const i = Math.min(Math.floor(seg), ramp.length - 2);
  const f = seg - i;
  const mix = (a: number, b: number) => Math.round(a + (b - a) * f);
  const [r, g, b] = [0, 1, 2].map((k) => mix(ramp[i][k], ramp[i + 1][k]));
  return `rgb(${r}, ${g}, ${b})`;
}

// The hero stop — the emotional centre of the whole narrative.
const HERO_ID = "S06";
const HERO_SUBLABEL = "City Hospital";

// Time-of-day atmosphere — the map's light breathes with the hour: warm dawn,
// bright noon, blue dusk, dark night. A colour wash (soft-light) tints, and a
// navy veil darkens the evening. Returns the nearest keyframe to `hour`.
function timeAtmosphere(hour: number): { wash: string; washOp: number; darken: number } {
  const table = [
    { h: 6,  c: [255, 150, 90],  o: 0.34, d: 0.10 }, // dawn — warm amber
    { h: 8,  c: [190, 205, 255], o: 0.16, d: 0.0 },  // morning — cool, clear
    { h: 10, c: [225, 228, 238], o: 0.08, d: 0.0 },  // mid — neutral
    { h: 12, c: [255, 250, 235], o: 0.05, d: 0.0 },  // noon — brightest
    { h: 14, c: [255, 222, 165], o: 0.16, d: 0.0 },  // afternoon — warm gold
    { h: 17, c: [255, 158, 88],  o: 0.30, d: 0.06 }, // pm — golden hour
    { h: 19, c: [90, 100, 190],  o: 0.36, d: 0.22 }, // evening — blue dusk
    { h: 22, c: [30, 40, 85],    o: 0.46, d: 0.38 }, // night — deep blue
  ];
  let best = table[0];
  for (const t of table)
    if (Math.abs(t.h - hour) < Math.abs(best.h - hour)) best = t;
  return { wash: `rgb(${best.c[0]}, ${best.c[1]}, ${best.c[2]})`, washOp: best.o, darken: best.d };
}

// Lift the city into 3D — extrude OSM building footprints (the CARTO basemap's
// `carto`/`building` source carries render_height). Subtle, dark, catches the
// dusk tint. Appears as you lean in past ~z13.5; the overview stays a clean map.
function add3DBuildings(map: MlMap) {
  if (map.getLayer("ladywood-3d-buildings")) return;
  const firstSymbol = map.getStyle().layers?.find((l) => l.type === "symbol")?.id;
  map.addLayer(
    {
      id: "ladywood-3d-buildings",
      type: "fill-extrusion",
      source: "carto",
      "source-layer": "building",
      minzoom: 13.5,
      paint: {
        "fill-extrusion-color": [
          "interpolate", ["linear"], ["coalesce", ["get", "render_height"], 6],
          0, "#1b1e26",
          40, "#2b3140",
          120, "#3a4252",
        ],
        "fill-extrusion-height": [
          "interpolate", ["linear"], ["zoom"],
          13.5, 0,
          14.5, ["coalesce", ["get", "render_height"], 6],
        ],
        "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
        "fill-extrusion-opacity": 0.85,
      },
    },
    firstSymbol,
  );
}

export default function MapView({
  routes,
  demand,
  onSelectStop,
  imdOverlay,
  hour,
}: {
  routes: RouteInfo[];
  demand: Record<string, number>;
  onSelectStop: (stop: Stop) => void;
  imdOverlay: boolean;
  hour: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MlMap | null>(null);
  const markersRef = useRef<Record<string, { marker: Marker; el: HTMLDivElement }>>({});
  const [stops, setStops] = useState<Stop[]>([]);
  const [mapInstance, setMapInstance] = useState<MlMap | null>(null);

  // Init map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      center: [-1.918, 52.481],
      zoom: 12.4,
      pitch: 30,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => add3DBuildings(map));
    mapRef.current = map;
    setMapInstance(map);
    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current = {};
      setMapInstance(null);
    };
  }, []);

  // Load stops once
  useEffect(() => {
    fetchStops().then(setStops);
  }, []);

  // Create / update markers when stops or demand change
  useEffect(() => {
    const map = mapRef.current;
    if (!map || stops.length === 0) return;

    // Normalise demand across the current window so the heat is relative.
    const maxDemand = Math.max(1, ...stops.map((s) => demand[s.stop_id] ?? 0));
    // Which stops the current plan actually serves. A stop the plan leaves out
    // (while others are served) is "underserved" — it gets the amber alarm.
    const served = new Set<string>();
    for (const r of routes) for (const s of r.route_stops ?? []) served.add(s);
    const planLoaded = served.size > 0;

    for (const stop of stops) {
      const boardings = demand[stop.stop_id] ?? 0;
      const r = radiusForDemand(boardings);
      const isHero = stop.stop_id === HERO_ID;
      let entry = markersRef.current[stop.stop_id];

      if (!entry) {
        // Anchor a ZERO-SIZE point exactly on the coordinate; the visible dot,
        // pulse and label hang off it via CSS centring — so demand-scaled size
        // and the label can never shift the geographic anchor on zoom.
        const wrap = document.createElement("div");
        wrap.className = "stop-anchor";
        const el = document.createElement("div");
        el.className = `stop-dot tier-${stop.importance}${isHero ? " hero" : ""}`;
        el.innerHTML =
          `<span class="pulse-ring"></span>` +
          `<span class="stop-label">${stop.name}` +
          (isHero ? `<em>${HERO_SUBLABEL}</em>` : ``) +
          `</span>`;
        wrap.appendChild(el);
        const popup = new Popup({ offset: 14, closeButton: false }).setHTML(
          `<div class="stop-popup"><strong>${stop.name}</strong><span>${stop.stop_id} · ${stop.importance}</span></div>`
        );
        const marker = new maplibregl.Marker({ element: wrap, anchor: "center" })
          .setLngLat([stop.lng, stop.lat])
          .setPopup(popup)
          .addTo(map);
        el.addEventListener("click", (e) => {
          e.stopPropagation();
          onSelectStop(stop);
        });
        entry = { marker, el };
        markersRef.current[stop.stop_id] = entry;
      }

      entry.el.style.width = `${r * 2}px`;
      entry.el.style.height = `${r * 2}px`;
      entry.el.title = `${stop.name} — ${boardings.toFixed(0)} boardings`;

      // Demand heat drives the fill, the pulse, everything. t = 0 cool/quiet,
      // t = 1 red/busy.
      const t = boardings / maxDemand;
      const heat = demandGlow(t);
      const isServed = !planLoaded || served.has(stop.stop_id);
      // Underserved = the plan is loaded but doesn't serve this stop.
      const isUnderserved = planLoaded && !served.has(stop.stop_id);
      const ring = TIER_RING[stop.importance] ?? 1.5;
      const tierRing = (IMPORTANCE_COLOR[stop.importance] ?? "#8e8e93") + "66";

      // Underserved stops are alarmed (amber ring, CSS-animated); everything
      // else sits at full strength — the cool demand colour de-emphasises quiet
      // stops without needing to dim them.
      entry.el.classList.toggle("underserved", isUnderserved);
      entry.el.style.opacity = "1";

      // Demand pulse only in the default (non-equity) view, for served stops.
      const pulseOp = !imdOverlay && isServed && !isUnderserved ? 0.15 + t * 0.6 : 0;
      entry.el.style.setProperty("--glow", heat);
      entry.el.style.setProperty("--glow-op", pulseOp.toFixed(3));
      entry.el.style.setProperty("--glow-scale", (0.4 + t * 1.8).toFixed(3));

      if (imdOverlay && stop.imd_score != null) {
        // Equity view: fill = deprivation, plus a soft red FIELD whose radius
        // scales with deprivation — overlapping fields read as a heat map.
        const d = Math.max(0, Math.min(1, stop.imd_score / 60));
        const r0 = 90, g0 = 100, b0 = 110;  // muted slate baseline
        const r1 = 255, g1 = 55, b1 = 95;    // alert red (#ff375f)
        const mix = (a: number, b: number) => Math.round(a + (b - a) * d);
        entry.el.style.background = `rgb(${mix(r0, r1)}, ${mix(g0, g1)}, ${mix(b0, b1)})`;
        if (!isUnderserved)
          entry.el.style.boxShadow =
            `0 0 0 ${ring}px ${tierRing}, 0 0 ${18 + d * 46}px ${6 + d * 18}px rgba(255,55,95,${(0.22 + d * 0.5).toFixed(2)})`;
      } else {
        // Default view: FILL = demand heat (loud), RING = tier (quiet).
        entry.el.style.background = heat;
        if (!isUnderserved)
          entry.el.style.boxShadow = `0 0 0 ${ring}px ${tierRing}, 0 0 16px 3px ${heat}55`;
      }
      // Underserved alert ring is owned by CSS animation — clear any inline shadow.
      if (isUnderserved) entry.el.style.boxShadow = "";
    }
  }, [stops, demand, routes, imdOverlay, onSelectStop]);

  const atm = timeAtmosphere(hour);
  return (
    <>
      <div ref={containerRef} className="map-canvas" />
      <div className="time-tint" style={{ background: atm.wash, opacity: atm.washOp }} />
      <div className="time-darken" style={{ opacity: atm.darken }} />
      <BusLayer map={mapInstance} routes={routes} />
    </>
  );
}
