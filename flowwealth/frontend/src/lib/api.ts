export type DataStatus = "LIVE" | "DELAYED" | "CACHED" | "HISTORICAL" | "SYNTHETIC" | "HYPOTHETICAL";

export interface Tile { name: string; value: number; change_1d: number; spark: number[]; as_of: string }
export interface Mover { ticker: string; sector: string; close: number; change: number }
export interface Overview {
  data_status: DataStatus; as_of: string; composite: Tile; sectors: Tile[]; countries: Tile[];
  gainers: Mover[]; losers: Mover[]; breadth_up: number;
}
export interface Series {
  ticker: string; exchange: string; sector: string; data_status: DataStatus; delisted: string | null;
  points: { t: string; c: number; flag: string }[];
}
export interface AlarmEval {
  definition: string; alarm_level: string; days: number; event_days: number; alarm_days: number;
  precision: number | null; recall: number | null; false_alarm_days: number; missed_event_days: number;
}
export interface CrashRisk {
  as_of: string; data_status: DataStatus; current: { score: number; level: string; regime: string };
  inputs: Record<string, number | null>; history: { date: string; level: string; score: number }[];
  evaluation: AlarmEval[]; index: { date: string; value: number }[];
}
export interface RankItem {
  ticker: string; exchange: string; sector: string; country: string; adj_close: number; ts: string;
  pred: number; vol_20: number; ret_20: number; dd_60: number;
}
export interface Rankings {
  horizon: string; as_of: string; data_status: DataStatus; model_version: string; target: string;
  methodology: string; feature_correlation_with_score: Record<string, number>; items: RankItem[]; disclaimer: string;
}
export interface MemoryRow {
  prediction_id: string; created_at: string; ticker: string; horizon: string; target_time: string;
  actual_return: number | null; benchmark_return: number | null; direction_correct: number | null;
  forecast_return: number | null; regime: string; strategy_id: string; data_status: DataStatus;
}
export interface MemoryResp {
  chain_verified: boolean; first_bad_seq: number | null; recent: MemoryRow[];
  summary: {
    model_version: string; dataset_version: string; data_status: DataStatus; predictions: number; replay_steps: number;
    evaluation: Record<string, unknown> & { n_resolved: number; n_pending: number; directional_accuracy?: number;
      rank_ic_vs_excess?: number; directional_accuracy_vs_excess?: number; mae?: number;
      by_regime?: { regime: string; mean: number; count: number }[] };
    feature_drift_psi_dev_vs_holdout: Record<string, number>;
  };
}
export interface PerfStats { sharpe?: number; cagr?: number; max_drawdown?: number; total_return?: number; win_rate?: number; n_periods: number }
export interface Experiment {
  experiment: string; dataset_version: string; data_status: DataStatus[]; rows_modelled: number; horizon_bars: number;
  split: Record<string, { rows: number; start: string; end: string }>;
  walk_forward_summary: { model: string; ic_mean: number | null; ic_min: number | null; folds_positive: number }[];
  holdout: Record<string, { ic: { ic_mean: number | null; ic_t: number | null; n_dates: number };
    backtest_long_short: null | { gross: PerfStats; net: PerfStats; avg_turnover: number; cost_drag_total: number } }>;
  caveat: string;
}
export interface Status {
  dataset: { version: string; rows: number; tickers: number; start: string; end: string; content_sha256: string;
    quality: Record<string, number> };
  data_status: DataStatus; live_feeds: string[]; brokerage: string;
  horizon_readiness: Record<string, { ready: boolean; status: string[]; max_age_s: number; needs: string[] }>;
  disclaimer: string;
}
export interface SearchHit { ticker: string; exchange: string; country: string; sector: string; delisted: string | null }
export interface RiskCheckResult { verdict: "APPROVE" | "REDUCE" | "REJECT"; approved_qty: number; reasons: string[];
  checks: Record<string, unknown>; effective_limits: Record<string, number> }

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/api${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail ?? msg; } catch { /* body not JSON */ }
    throw new ApiError(r.status, typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return r.json() as Promise<T>;
}

export const api = {
  status: () => req<Status>("/status"),
  overview: () => req<Overview>("/market/overview"),
  series: (ticker: string, range: string) => req<Series>(`/market/series?ticker=${encodeURIComponent(ticker)}&range=${range}`),
  search: (q: string) => req<{ results: SearchHit[] }>(`/search?q=${encodeURIComponent(q)}`),
  rankings: () => req<Rankings>("/rankings"),
  crash: () => req<CrashRisk>("/risk/crash"),
  memory: (limit = 50) => req<MemoryResp>(`/memory?limit=${limit}`),
  experiments: () => req<{ experiments: Experiment[] }>("/experiments"),
  limits: () => req<{ hard_limits: Record<string, number>; appetite_defaults: Record<string, Record<string, number>> }>("/profiles/limits"),
  riskCheck: (body: unknown) => req<RiskCheckResult>("/risk/check", { method: "POST", body: JSON.stringify(body) }),
};
