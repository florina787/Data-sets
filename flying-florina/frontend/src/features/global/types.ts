export type Shortage = { category_id: string; p10: number; p50: number; p90: number; stockout_prob: number };
export type Facility = {
  id: string; name: string; kind: string; city: string; country: string; region: string; lat: number; lon: number;
  health_mean?: number; units_tracked?: number; units_due?: number; high_risk_units?: number;
  demand_p10?: number; demand_p50?: number; demand_p90?: number; workload_utilisation?: number; workload_hours_p50?: number;
  capacity_cut?: number; cost_p50_usd?: number; shortages?: Shortage[]; shortage_count?: number; max_stockout_prob?: number; disruptions: string[];
};
export type Supplier = {
  id: string; name: string; city: string; country: string; region: string; lat: number; lon: number; late_probability: number;
  baseline_late_probability: number; disruption_days_added: number; open_orders: number; categories: string[];
};
export type Link = { supplier_id: string; facility_id: string; category_id: string; share: number; from: [number, number]; to: [number, number] };
export type Disruption = {
  id: string; title: string; kind: string; lat: number; lon: number; region: string; facility_id: string | null; supplier_id: string | null;
  start_day: number; duration_days: number; end_day: number; severity: string; capacity_cut: number; lead_time_add_days: number;
  recovery_progress: number; days_to_restore: number; phase: string; source: string; verified: number;
};
export type Region = { region: string; facilities: number; demand_p50: number; shortages: number; health_mean: number | null; cost_p50_usd: number; disruptions: number };
export type Freshness = { data_as_of: string; forecast_origin: string; models_built_at: string; model_version: string; dataset: string; synthetic: boolean; build_ms: number };
export type MapState = {
  horizon_days: number; facilities: Facility[]; suppliers: Supplier[]; links: Link[]; disruptions: Disruption[]; regions: Region[];
  categories: { id: string; name: string; family: string }[]; freshness: Freshness; assumptions: string[];
};
export const HORIZONS = [0, 7, 14, 30, 60, 90] as const;
export const LAYERS = [
  { id: "facilities", label: "Facility overview" },
  { id: "health", label: "Component health" },
  { id: "supply", label: "Supply chain" },
  { id: "inventory", label: "Inventory forecast" },
  { id: "disruptions", label: "Operational disruptions" },
  { id: "recovery", label: "Recovery intelligence" },
] as const;
export type LayerId = (typeof LAYERS)[number]["id"];
