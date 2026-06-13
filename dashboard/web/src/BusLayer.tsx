import { useEffect, useRef } from "react";
import maplibregl, { Map as MlMap, Marker } from "maplibre-gl";
import type { RouteInfo } from "./api";

const BUS_COLORS = ["#0a84ff", "#ff9f0a", "#30d158", "#ff375f", "#bf5af2"];

/** Total length of a [lng,lat] polyline in plain degrees-space (good enough
 * for short city-scale routes — avoids pulling in a geo library). */
function pathLength(coords: [number, number][]): number {
  let total = 0;
  for (let i = 1; i < coords.length; i++) {
    const [x1, y1] = coords[i - 1];
    const [x2, y2] = coords[i];
    total += Math.hypot(x2 - x1, y2 - y1);
  }
  return total;
}

/** Position + bearing at fractional distance `t` (0..1) along the polyline. */
function pointAt(coords: [number, number][], t: number): { lngLat: [number, number]; bearing: number } {
  if (coords.length < 2) return { lngLat: coords[0] ?? [0, 0], bearing: 0 };
  const total = pathLength(coords);
  let target = total * Math.max(0, Math.min(1, t));
  for (let i = 1; i < coords.length; i++) {
    const [x1, y1] = coords[i - 1];
    const [x2, y2] = coords[i];
    const segLen = Math.hypot(x2 - x1, y2 - y1);
    if (target <= segLen || i === coords.length - 1) {
      const f = segLen === 0 ? 0 : target / segLen;
      const lng = x1 + (x2 - x1) * f;
      const lat = y1 + (y2 - y1) * f;
      const bearing = (Math.atan2(x2 - x1, y2 - y1) * 180) / Math.PI;
      return { lngLat: [lng, lat], bearing };
    }
    target -= segLen;
  }
  return { lngLat: coords[coords.length - 1], bearing: 0 };
}

const ROUTE_SOURCE_PREFIX = "route-line-";

export default function BusLayer({ map, routes }: { map: MlMap | null; routes: RouteInfo[] }) {
  const markersRef = useRef<Marker[]>([]);
  const rafRef = useRef<number>(0);
  const startRef = useRef<number>(0);

  // Draw route lines + spawn bus markers whenever the route set changes
  useEffect(() => {
    if (!map) return;

    const cleanupLines = () => {
      for (const r of routes) {
        const id = `${ROUTE_SOURCE_PREFIX}${r.bus}`;
        if (map.getLayer(`${id}-case`)) map.removeLayer(`${id}-case`);
        if (map.getLayer(id)) map.removeLayer(id);
        if (map.getSource(id)) map.removeSource(id);
      }
    };

    const draw = () => {
      cleanupLines();
      routes.forEach((r, i) => {
        if (r.geometry.length < 2) return;
        const id = `${ROUTE_SOURCE_PREFIX}${r.bus}`;
        const color = BUS_COLORS[i % BUS_COLORS.length];
        map.addSource(id, {
          type: "geojson",
          data: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: r.geometry } },
        });
        // Dark casing underneath keeps the route legible where it crosses
        // light roads or the basemap's grey arterials.
        map.addLayer({
          id: `${id}-case`, type: "line", source: id,
          layout: { "line-join": "round", "line-cap": "round" },
          paint: { "line-color": "#0b0c10", "line-width": 7, "line-opacity": 0.7 },
        });
        map.addLayer({
          id, type: "line", source: id,
          layout: { "line-join": "round", "line-cap": "round" },
          paint: { "line-color": color, "line-width": 3.6, "line-opacity": 0.92 },
        });
      });
    };

    if (map.isStyleLoaded()) draw();
    else map.once("idle", draw);

    // Spawn one marker per route, staggered along its path
    for (const m of markersRef.current) m.remove();
    markersRef.current = routes
      .filter((r) => r.geometry.length >= 2)
      .map((r, i) => {
        const color = BUS_COLORS[i % BUS_COLORS.length];
        const el = document.createElement("div");
        el.className = "bus-marker";
        el.title = `Bus ${r.bus}: ${r.route_names.join(" → ")}`;
        el.innerHTML = `
          <svg viewBox="0 0 16 32" width="20" height="40">
            <!-- birds-eye bus: long rounded body, roofline, window strip, wheels -->
            <rect x="1" y="0.5" width="14" height="31" rx="4" fill="${color}" stroke="rgba(255,255,255,0.9)" stroke-width="1" />
            <rect x="2.4" y="2.3" width="11.2" height="6" rx="2" fill="rgba(255,255,255,0.22)" />
            <rect x="3" y="9.5" width="10" height="16" rx="1.6" fill="rgba(20,20,22,0.55)" />
            ${[0, 1, 2, 3, 4].map((i) => `<rect x="3.9" y="${10.7 + i * 3.05}" width="8.2" height="1.7" rx="0.5" fill="rgba(255,255,255,0.55)" />`).join("")}
            <rect x="-0.4" y="5" width="2" height="4.5" rx="0.8" fill="#1c1c1e" stroke="rgba(255,255,255,0.5)" stroke-width="0.6" />
            <rect x="14.4" y="5" width="2" height="4.5" rx="0.8" fill="#1c1c1e" stroke="rgba(255,255,255,0.5)" stroke-width="0.6" />
            <rect x="-0.4" y="22" width="2" height="4.5" rx="0.8" fill="#1c1c1e" stroke="rgba(255,255,255,0.5)" stroke-width="0.6" />
            <rect x="14.4" y="22" width="2" height="4.5" rx="0.8" fill="#1c1c1e" stroke="rgba(255,255,255,0.5)" stroke-width="0.6" />
          </svg>`;
        return new maplibregl.Marker({ element: el, rotationAlignment: "map" }).setLngLat(r.geometry[0]).addTo(map);
      });

    startRef.current = performance.now();

    return () => {
      cleanupLines();
      for (const m of markersRef.current) m.remove();
      markersRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, routes]);

  // Animation loop — each bus loops its route every ~22s, offset by index
  useEffect(() => {
    if (!map || markersRef.current.length === 0) return;
    const LOOP_MS = 29000; // ~25% slower than the original 22s loop

    const tick = (now: number) => {
      const elapsed = now - startRef.current;
      routes.forEach((r, i) => {
        const marker = markersRef.current[i];
        if (!marker || r.geometry.length < 2) return;
        const offset = (i / Math.max(routes.length, 1)) * LOOP_MS;
        const t = ((elapsed + offset) % LOOP_MS) / LOOP_MS;
        const { lngLat, bearing } = pointAt(r.geometry, t);
        marker.setLngLat(lngLat);
        marker.setRotation(bearing);
      });
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [map, routes]);

  return null;
}
