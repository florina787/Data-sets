import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { api, sessionHeaders, streamSSE, type Dataset, type Filters, type FloEvent } from "./api";

export type Mode = "demo" | "connected";

export type ToolActivity = { step: string; tool: string; purpose: string; status: string; summary?: string; filters?: string | null; evidence_ids?: string[]; args?: Record<string, unknown> };
export type NodeState = Record<string, "running" | "completed" | "failed" | "awaiting_approval">;

export type FloTurn = {
  id: string;
  question: string;
  page: string;
  filters: Filters;
  mode: Mode;
  datasetId: string;
  requestId?: string;
  status: "streaming" | "completed" | "awaiting_approval" | "failed" | "cancelled" | "error";
  streamedText: string;
  tools: ToolActivity[];
  nodes: NodeState;
  nodeOrder: string[];
  response?: any;
  approval?: any;
  error?: string;
  validation?: any;
  method?: string;
};

type Status = { model: any; langsmith: any; retrieval: any; limits: any; auth: string } | null;

type Ctx = {
  datasets: Dataset[];
  refreshDatasets: () => Promise<void>;
  mode: Mode;
  setMode: (m: Mode) => void;
  dataset: Dataset | null;
  setDatasetId: (id: string) => void;
  filters: Filters;
  setFilters: (f: Filters) => void;
  page: string;
  status: Status;
  refreshStatus: () => void;
  floOpen: boolean;
  setFloOpen: (o: boolean) => void;
  turns: FloTurn[];
  ask: (question: string, filters?: Filters) => void;
  cancel: () => void;
  decide: (turnId: string, decision: "approve" | "save_as_proposed" | "reject", edits: Record<string, unknown>, reviewer: string) => Promise<void>;
  busy: boolean;
  liveNodes: NodeState;
  clearTurns: () => void;
  loadError: string | null;
};

const AppCtx = createContext<Ctx | null>(null);

const PAGE_NAMES: Record<string, string> = {
  "/": "Executive overview", "/ask": "Ask Flo", "/explorer": "Conversation explorer", "/maps": "Insight maps",
  "/opportunities": "Opportunity portfolio", "/decisions": "Decisions and actions", "/impact": "Impact review",
  "/quality": "Data quality", "/observability": "Observability and evaluation", "/languages": "Language intelligence", "/review": "Human review",
};

function store<T>(key: string, value?: T): T | null {
  try {
    if (value === undefined) {
      const v = localStorage.getItem(key);
      return v ? (JSON.parse(v) as T) : null;
    }
    localStorage.setItem(key, JSON.stringify(value));
  } catch { /* storage unavailable: preference not remembered */ }
  return null;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [mode, setModeState] = useState<Mode>(() => store<Mode>("convolens.mode") ?? "demo");
  const [datasetId, setDatasetIdState] = useState<string | null>(() => store<string>("convolens.dataset"));
  const [filters, setFilters] = useState<Filters>({});
  const [status, setStatus] = useState<Status>(null);
  const [floOpen, setFloOpen] = useState<boolean>(() => store<boolean>("convolens.floOpen") ?? true);
  const [turns, setTurns] = useState<FloTurn[]>([]);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const page = PAGE_NAMES[location.pathname] ?? location.pathname;

  const refreshDatasets = useCallback(async () => {
    try {
      const r = await api<{ datasets: Dataset[] }>("/api/datasets");
      setDatasets(r.datasets);
      setLoadError(null);
    } catch (e: any) {
      setLoadError(e.message);
    }
  }, []);
  const refreshStatus = useCallback(() => { api<Status>("/api/status").then(setStatus).catch(() => setStatus(null)); }, []);
  useEffect(() => { refreshDatasets(); refreshStatus(); }, [refreshDatasets, refreshStatus]);

  const eligible = useMemo(() => datasets.filter((d) => d.status === "ready" && (mode === "demo" ? d.synthetic : !d.synthetic)), [datasets, mode]);
  const dataset = useMemo(() => eligible.find((d) => d.id === datasetId) ?? eligible[0] ?? null, [eligible, datasetId]);

  const setMode = (m: Mode) => { setModeState(m); store("convolens.mode", m); setFilters({}); };
  const setDatasetId = (id: string) => { setDatasetIdState(id); store("convolens.dataset", id); setFilters({}); };
  useEffect(() => { store("convolens.floOpen", floOpen); }, [floOpen]);

  const patchTurn = (id: string, fn: (t: FloTurn) => FloTurn) => setTurns((ts) => ts.map((t) => (t.id === id ? fn(t) : t)));

  const handleEvent = (id: string) => (e: FloEvent) => {
    patchTurn(id, (t) => {
      switch (e.type) {
        case "run_started":
          return { ...t, requestId: e.request_id, method: e.method };
        case "run_resumed":
          return { ...t, status: "streaming" };
        case "node": {
          const nodes = { ...t.nodes, [e.node]: e.status };
          const nodeOrder = t.nodeOrder.includes(e.node) ? t.nodeOrder : [...t.nodeOrder, e.node];
          return { ...t, nodes, nodeOrder };
        }
        case "tool": {
          const tools = [...t.tools];
          const i = tools.findIndex((x) => x.step === e.step);
          const entry = { step: e.step, tool: e.tool, purpose: e.purpose, status: e.status, summary: e.summary, filters: e.filters, evidence_ids: e.evidence_ids, ...(e.args ? { args: e.args } : {}) };
          if (i >= 0) tools[i] = { ...tools[i], ...entry }; else tools.push(entry);
          return { ...t, tools };
        }
        case "token":
          return { ...t, streamedText: (e.attempt ? "" : t.streamedText) + e.text };
        case "validation":
          return { ...t, validation: e };
        case "approval_required":
          return { ...t, approval: e };
        case "action_saved":
          return t;
        case "answer":
          return { ...t, response: e.response, status: e.status === "awaiting_approval" ? "awaiting_approval" : e.status === "failed" ? "failed" : e.status === "cancelled" ? "cancelled" : "completed" };
        case "error":
          return { ...t, status: "error", error: e.message };
        default:
          return t;
      }
    });
  };

  const ask = useCallback((question: string, f?: Filters) => {
    if (!dataset || busy) return;
    const scope = f ?? filters;
    if (f) setFilters(f);
    const id = `t${Date.now()}`;
    const turn: FloTurn = { id, question, page, filters: scope, mode, datasetId: dataset.id, status: "streaming", streamedText: "", tools: [], nodes: {}, nodeOrder: [] };
    setTurns((ts) => [...ts, turn]);
    setFloOpen(true);
    setBusy(true);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    streamSSE("/api/flo/chat", { question, dataset_id: dataset.id, mode, page, filters: scope }, handleEvent(id), ctrl.signal)
      .catch((err) => {
        if (ctrl.signal.aborted) patchTurn(id, (t) => ({ ...t, status: t.status === "streaming" ? "cancelled" : t.status }));
        else patchTurn(id, (t) => ({ ...t, status: "error", error: err.message }));
      })
      .finally(() => { setBusy(false); abortRef.current = null; });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset, busy, filters, page, mode]);

  const cancel = useCallback(() => {
    const t = turns[turns.length - 1];
    if (t?.requestId) {
      sessionHeaders().then((h) => fetch(`/api/flo/runs/${t.requestId}/cancel`, { method: "POST", headers: h })).catch(() => undefined);
    }
    // Server-side cancellation stops the graph; the stream then delivers the cancelled response.
    setTimeout(() => abortRef.current?.abort(), 4000);
  }, [turns]);

  const decide = useCallback(async (turnId: string, decision: "approve" | "save_as_proposed" | "reject", edits: Record<string, unknown>, reviewer: string) => {
    const t = turns.find((x) => x.id === turnId);
    if (!t?.requestId) return;
    setBusy(true);
    patchTurn(turnId, (x) => ({ ...x, status: "streaming", approval: { ...x.approval, submitted: decision } }));
    const ctrl = new AbortController();
    try {
      await streamSSE(`/api/flo/runs/${t.requestId}/approval`, { decision, edits, reviewer }, handleEvent(turnId), ctrl.signal);
    } catch (err: any) {
      patchTurn(turnId, (x) => ({ ...x, status: "error", error: err.message }));
    } finally {
      setBusy(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turns]);

  const liveNodes = turns.length ? turns[turns.length - 1].nodes : {};

  const value: Ctx = {
    datasets, refreshDatasets, mode, setMode, dataset, setDatasetId, filters, setFilters, page, status, refreshStatus,
    floOpen, setFloOpen, turns, ask, cancel, decide, busy, liveNodes, clearTurns: () => setTurns([]), loadError,
  };
  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp() {
  const c = useContext(AppCtx);
  if (!c) throw new Error("useApp outside provider");
  return c;
}

/** Load data for the current dataset + filters, re-fetching when they change. */
export function useData<T>(loader: (datasetId: string, filters: Filters) => Promise<T>, deps: unknown[] = []) {
  const { dataset, filters } = useApp();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [nonce, setNonce] = useState(0);
  useEffect(() => {
    if (!dataset) return;
    let alive = true;
    setLoading(true);
    loader(dataset.id, filters)
      .then((d) => { if (alive) { setData(d); setError(null); } })
      .catch((e) => { if (alive) setError(e.message); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset?.id, JSON.stringify(filters), nonce, ...deps]);
  return { data, error, loading, reload: () => setNonce((n) => n + 1) };
}
