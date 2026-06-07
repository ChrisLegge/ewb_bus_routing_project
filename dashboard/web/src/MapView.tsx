import { useEffect, useRef, useState } from "react";
import maplibregl, { Map as MlMap, Marker, Popup } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { fetchStops, fetchDemand, type Stop } from "./api";

// Minimalist dark basemap — Apple-Maps-at-night feel: muted greys, no clutter,
// just roads, water, and place labels turned down to a whisper.
const STYLE_URL = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const IMPORTANCE_COLOR: Record<string, string> = {
  major: "#0a84ff",
  medium: "#5ac8fa",
  minor: "#8e8e93",
};

function radiusForDemand(boardings: number): number {
  // Smooth, perceptual scaling — sqrt so area (not radius) tracks demand.
  return 6 + Math.sqrt(Math.max(boardings, 0)) * 1.6;
}

export default function MapView({ hour }: { hour: number }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MlMap | null>(null);
  const markersRef = useRef<Record<string, { marker: Marker; el: HTMLDivElement }>>({});
  const [stops, setStops] = useState<Stop[]>([]);
  const [demand, setDemand] = useState<Record<string, number>>({});

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
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current = {};
    };
  }, []);

  // Load stops once
  useEffect(() => {
    fetchStops().then(setStops);
  }, []);

  // Reload demand whenever hour changes
  useEffect(() => {
    fetchDemand(hour).then((d) => setDemand(d.predictions));
  }, [hour]);

  // Create / update markers when stops or demand change
  useEffect(() => {
    const map = mapRef.current;
    if (!map || stops.length === 0) return;

    for (const stop of stops) {
      const boardings = demand[stop.stop_id] ?? 0;
      const r = radiusForDemand(boardings);
      let entry = markersRef.current[stop.stop_id];

      if (!entry) {
        const el = document.createElement("div");
        el.className = "stop-dot";
        const popup = new Popup({ offset: 14, closeButton: false }).setHTML(
          `<div class="stop-popup"><strong>${stop.name}</strong><span>${stop.stop_id} · ${stop.importance}</span></div>`
        );
        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([stop.lng, stop.lat])
          .setPopup(popup)
          .addTo(map);
        entry = { marker, el };
        markersRef.current[stop.stop_id] = entry;
      }

      entry.el.style.width = `${r * 2}px`;
      entry.el.style.height = `${r * 2}px`;
      entry.el.style.background = IMPORTANCE_COLOR[stop.importance] ?? "#8e8e93";
      entry.el.title = `${stop.name} — ${boardings.toFixed(0)} boardings`;
    }
  }, [stops, demand]);

  return <div ref={containerRef} className="map-canvas" />;
}
