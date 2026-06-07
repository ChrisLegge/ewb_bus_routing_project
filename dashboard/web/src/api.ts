const BASE = "/api";

export interface Stop {
  stop_id: string;
  name: string;
  lat: number;
  lng: number;
  routes: string[];
  importance: "major" | "medium" | "minor";
  note: string;
}

export interface DemandResponse {
  hour: number;
  conditions: Record<string, unknown>;
  predictions: Record<string, number>;
}

export async function fetchStops(): Promise<Stop[]> {
  const res = await fetch(`${BASE}/stops`);
  return res.json();
}

export async function fetchRoads(): Promise<Record<string, [number, number][]>> {
  const res = await fetch(`${BASE}/roads`);
  return res.json();
}

export async function fetchDemand(hour: number, params: Record<string, string | number> = {}): Promise<DemandResponse> {
  const qs = new URLSearchParams({ hour: String(hour), ...Object.fromEntries(
    Object.entries(params).map(([k, v]) => [k, String(v)])
  ) });
  const res = await fetch(`${BASE}/demand?${qs}`);
  return res.json();
}

export async function fetchScenarios(): Promise<string[]> {
  const res = await fetch(`${BASE}/scenarios`);
  return res.json();
}

export interface RouteInfo {
  bus: number;
  route_stops: string[];
  route_names: string[];
  geometry: [number, number][];
  [key: string]: unknown;
}

export interface RoutesResponse {
  scenario: string;
  window: string;
  hours: string;
  demand_per_stop: Record<string, number>;
  routes: RouteInfo[];
}

export async function fetchRoutes(scenario: string, window: string): Promise<RoutesResponse> {
  const res = await fetch(`${BASE}/routes/${encodeURIComponent(scenario)}/${encodeURIComponent(window)}`);
  return res.json();
}
