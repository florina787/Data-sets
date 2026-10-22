import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, streamChat } from "@/services/api";
import type { ChatResponse, NodeStatus, StreamEvent } from "@/types/api";

export interface NodeProgress { status: NodeStatus; label?: string; duration_ms?: number; summary?: Record<string, any>; error?: string | null }

export interface Turn {
  id: string;
  question: string;
  status: "streaming" | "done" | "error" | "cancelled";
  requestId?: string;
  nodes: Record<string, NodeProgress>;
  order: string[];
  response?: ChatResponse;
  error?: string;
  retryable?: boolean;
  startedAt: number;
}

interface ModelStatus { available?: boolean; mode?: string; model?: string; provider?: string; reason?: string | null; circuit?: string }

interface AppState {
  sessionId: string | null;
  datasetMode: "original" | "synthetic" | "combined";
  setDatasetMode: (m: "original" | "synthetic" | "combined") => void;
  selectedConversation: string | null;
  setSelectedConversation: (id: string | null) => void;
  turns: Turn[];
  ask: (question: string) => void;
  cancel: () => void;
  retry: (turnId: string) => void;
  newSession: () => void;
  loadSession: (id: string) => Promise<void>;
  busy: boolean;
  model: ModelStatus | null;
  refreshModel: () => void;
  health: any;
}

const Ctx = createContext<AppState | null>(null);
const SESSION_KEY = "cic.session";

function safeGet(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function safeSet(key: string, v: string | null) {
  try { v === null ? localStorage.removeItem(key) : localStorage.setItem(key, v); } catch { /* storage unavailable */ }
}

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(() => safeGet(SESSION_KEY));
  const [datasetMode, setDatasetMode] = useState<"original" | "synthetic" | "combined">("original");
  const [selectedConversation, setSelectedConversation] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [model, setModel] = useState<ModelStatus | null>(null);
  const [health, setHealth] = useState<any>(null);
  const abortRef = useRef<(() => void) | null>(null);

  const refreshModel = useCallback(() => {
    api.get<ModelStatus>("/api/model/status").then(setModel).catch(() => setModel({ available: false, reason: "Backend unreachable" }));
    api.get<any>("/health").then(setHealth).catch(() => setHealth({ status: "error", checks: [] }));
  }, []);
  useEffect(() => { refreshModel(); }, [refreshModel]);

  useEffect(() => {
    if (!sessionId || turns.length) return;
    api.get<ChatResponse[]>(`/api/sessions/${sessionId}/responses`)
      .then((rs) => setTurns(rs.map((r) => ({ id: r.request_id, question: r.question, status: "done", requestId: r.request_id, nodes: {}, order: [], response: r, startedAt: 0 }))))
      .catch(() => { setSessionId(null); safeSet(SESSION_KEY, null); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const update = (id: string, fn: (t: Turn) => Turn) => setTurns((ts) => ts.map((t) => (t.id === id ? fn(t) : t)));

  const run = useCallback((turnId: string, question: string) => {
    const onEvent = (e: StreamEvent) => {
      if (e.type === "accepted") {
        if (e.session_id) { setSessionId(e.session_id); safeSet(SESSION_KEY, e.session_id); }
        update(turnId, (t) => ({ ...t, requestId: e.request_id }));
      } else if (e.type === "node_start" && e.node) {
        update(turnId, (t) => ({ ...t, order: t.order.includes(e.node!) ? t.order : [...t.order, e.node!],
          nodes: { ...t.nodes, [e.node!]: { status: "running", label: e.label } } }));
      } else if (e.type === "node_end" && e.node) {
        update(turnId, (t) => ({ ...t, nodes: { ...t.nodes, [e.node!]: { status: e.status ?? "completed", label: e.label, duration_ms: e.duration_ms,
          summary: e.output_summary, error: e.error } } }));
      } else if (e.type === "final" && e.response) {
        update(turnId, (t) => ({ ...t, status: "done", response: e.response }));
        abortRef.current = null;
        refreshModel();
      } else if (e.type === "error") {
        update(turnId, (t) => ({ ...t, status: "error", error: e.message, retryable: e.retryable }));
        abortRef.current = null;
      }
    };
    abortRef.current = streamChat(
      { question, session_id: safeGet(SESSION_KEY), dataset_mode: datasetMode, selected_conversation_id: selectedConversation },
      onEvent,
      (err) => { update(turnId, (t) => ({ ...t, status: "error", error: err.message, retryable: true })); abortRef.current = null; },
    );
  }, [datasetMode, selectedConversation, refreshModel]);

  const ask = useCallback((question: string) => {
    const q = question.trim();
    if (!q || abortRef.current) return;
    const id = `t-${Date.now()}`;
    setTurns((ts) => [...ts, { id, question: q, status: "streaming", nodes: {}, order: [], startedAt: Date.now() }]);
    run(id, q);
  }, [run]);

  const cancel = useCallback(() => {
    abortRef.current?.();
    abortRef.current = null;
    setTurns((ts) => ts.map((t) => (t.status === "streaming" ? { ...t, status: "cancelled", retryable: true } : t)));
  }, []);

  const retry = useCallback((turnId: string) => {
    const t = turns.find((x) => x.id === turnId);
    if (!t || abortRef.current) return;
    update(turnId, (x) => ({ ...x, status: "streaming", error: undefined, nodes: {}, order: [], startedAt: Date.now() }));
    run(turnId, t.question);
  }, [turns, run]);

  const newSession = useCallback(() => {
    abortRef.current?.();
    abortRef.current = null;
    setSessionId(null);
    safeSet(SESSION_KEY, null);
    setTurns([]);
  }, []);

  const loadSession = useCallback(async (id: string) => {
    const rs = await api.get<ChatResponse[]>(`/api/sessions/${id}/responses`);
    setSessionId(id);
    safeSet(SESSION_KEY, id);
    setTurns(rs.map((r) => ({ id: r.request_id, question: r.question, status: "done", requestId: r.request_id, nodes: {}, order: [], response: r, startedAt: 0 })));
  }, []);

  const busy = turns.some((t) => t.status === "streaming");
  const value = useMemo<AppState>(() => ({ sessionId, datasetMode, setDatasetMode, selectedConversation, setSelectedConversation, turns, ask, cancel,
    retry, newSession, loadSession, busy, model, refreshModel, health }),
  [sessionId, datasetMode, selectedConversation, turns, ask, cancel, retry, newSession, loadSession, busy, model, refreshModel, health]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp must be used inside AppStateProvider");
  return v;
}
