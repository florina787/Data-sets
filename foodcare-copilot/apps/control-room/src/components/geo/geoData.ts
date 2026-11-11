import { useEffect, useState } from "react";
import { api } from "../../api";
import { useApp } from "../../context";

export type Tier = "farm" | "supplier" | "factory" | "distribution_centre" | "market";
export type Provenance = "verified" | "operational_record" | "modeled" | "synthetic";
export type GeoNode = {
  id: string; tier: Tier; name: string; country: string; country_name: string; lat: number; lon: number;
  revenue_dependent: number; provenance: Provenance; location_note: string;
  performance: { on_time_pct: number; quality_pass_pct: number };
};
export type GeoEdge = { id: string; from: string; to: string; km: number; mode: string; lead_time_days: number; provenance: Provenance };
export type GeoIncident = {
  id: string; node_id: string; country: string; lat: number; lon: number; date: string; kind: string;
  severity: "low" | "medium" | "high"; batch: string; provenance: Provenance; title?: string;
};
export type GeoCountry = { id: string; name: string; lat: number; lon: number; revenue: number; revenue_share_pct: number; sites: number; incidents_365d: number; provenance: Provenance };
export type Network = {
  scenario: { name: string; disclaimer: string; countries: number; annual_revenue: number; currency: string; seed: number; path: string };
  countries: GeoCountry[]; nodes: GeoNode[]; edges: GeoEdge[]; incidents: GeoIncident[];
  tracking: { events: number; note: string };
  provenance: Record<Provenance, { label: string; count: number }>;
  as_of: string;
  attribution: { attributed_to_market_sites: number; total: number; note: string };
};
export type Risk = {
  scope: { country: string | null; node: string | null; sites: number }; currency: string; draws: number; method: string;
  horizons: { days: number; incidents: { p10: number; p50: number; p90: number }; exposure: { p10: number; p50: number; p90: number } }[];
};

export const TIERS: Tier[] = ["farm", "supplier", "factory", "distribution_centre", "market"];
export const TIER_LABEL: Record<Tier, string> = {
  farm: "Farm", supplier: "Supplier", factory: "Factory", distribution_centre: "Distribution centre", market: "Market",
};
// Premium navy palette: cyan, gold, lime, white; red is reserved for quality risk.
export const TIER_COLOR: Record<Tier, string> = {
  farm: "#a3e635", supplier: "#38bdf8", factory: "#e9b95b", distribution_centre: "#c7d2fe", market: "#f3d18a",
};
export const RISK_RED = "#f43f5e";
export const PROVENANCE_STYLE: Record<Provenance, string> = {
  verified: "border-leaf-500 text-leaf-700",
  operational_record: "border-ice-400 text-ice-300",
  modeled: "border-royal-400 text-royal-400",
  synthetic: "border-gold-500 text-gold-300",
};

export function money(v: number, cur = "USD"): string {
  if (v >= 1e9) return `${cur} ${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `${cur} ${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${cur} ${(v / 1e3).toFixed(0)}k`;
  return `${cur} ${Math.round(v)}`;
}

const cache = new Map<string, Promise<Network>>();

/** The network, fetched once per signed-in user (operational incidents are per user). */
export function useNetwork(): { data: Network | null; error: string | null } {
  const { user } = useApp();
  const key = user?.username ?? "-";
  const [state, setState] = useState<{ data: Network | null; error: string | null }>({ data: null, error: null });
  useEffect(() => {
    let live = true;
    if (!cache.has(key)) cache.set(key, api<Network>("/api/geo/network"));
    cache.get(key)!.then((data) => live && setState({ data, error: null }))
      .catch((e) => { cache.delete(key); if (live) setState({ data: null, error: (e as Error).message }); });
    return () => { live = false; };
  }, [key]);
  return state;
}

export function useRisk(country?: string, node?: string): Risk | null {
  const [risk, setRisk] = useState<Risk | null>(null);
  useEffect(() => {
    let live = true;
    const qs = new URLSearchParams({ ...(country && { country }), ...(node && { node }) });
    api<Risk>(`/api/geo/risk?${qs}`).then((r) => live && setRisk(r)).catch(() => live && setRisk(null));
    return () => { live = false; };
  }, [country, node]);
  return risk;
}

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

export function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

/** Scope of the current selection: nodes, edges and incidents to emphasise. */
export function scopeOf(net: Network, sel: { country?: string; node?: string; incident?: string }) {
  const byId = new Map(net.nodes.map((n) => [n.id, n]));
  const incident = sel.incident ? net.incidents.find((i) => i.id === sel.incident) : undefined;
  const nodeId = sel.node ?? incident?.node_id;
  const node = nodeId ? byId.get(nodeId) : undefined;
  let nodeIds: Set<string>;
  if (node) {
    // the site, everything upstream and everything downstream
    nodeIds = new Set([node.id]);
    for (const dir of ["up", "down"] as const) {
      const stack = [node.id];
      while (stack.length) {
        const cur = stack.pop()!;
        for (const e of net.edges) {
          const next = dir === "up" && e.to === cur ? e.from : dir === "down" && e.from === cur ? e.to : null;
          if (next && !nodeIds.has(next)) { nodeIds.add(next); stack.push(next); }
        }
      }
    }
  } else if (sel.country) {
    nodeIds = new Set(net.nodes.filter((n) => n.country === sel.country).map((n) => n.id));
    for (const e of net.edges) if (nodeIds.has(e.from) || nodeIds.has(e.to)) { nodeIds.add(e.from); nodeIds.add(e.to); }
  } else {
    nodeIds = new Set(net.nodes.map((n) => n.id));
  }
  const edges = net.edges.filter((e) => nodeIds.has(e.from) && nodeIds.has(e.to));
  const incidents = node ? net.incidents.filter((i) => i.node_id === node.id)
    : sel.country ? net.incidents.filter((i) => i.country === sel.country) : net.incidents;
  const country = sel.country ? net.countries.find((c) => c.id === sel.country) : node ? net.countries.find((c) => c.id === node.country) : undefined;
  return { node, incident, country, nodeIds, edges, incidents, all: !node && !sel.country };
}
