import { useCallback, useEffect, useRef, useState } from "react";
import { api, tokenStore } from "@/lib/api";
import { parseSSE } from "./sse";
import type { Intent, MessageContext, MessageResponse, Stage, StoredMessage } from "./types";

export type AgentEvent = { agent: string; status: "succeeded" | "failed"; tools?: string[]; failure_class?: string };
export type Turn = {
  key: string; // client_message_id (idempotency key)
  question: string;
  context?: MessageContext;
  state: "streaming" | "done" | "error";
  stages: Stage[];
  agents: AgentEvent[];
  plan?: { supervisor: string; agents: string[]; skipped: string[] };
  intent?: Intent;
  requestId?: string;
  response?: MessageResponse;
  error?: string;
};

const newKey = () => `cm_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;

export function useConversation(persona: string, language: string) {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [selected, setSelected] = useState(-1);
  const abort = useRef<AbortController | null>(null);
  const cidRef = useRef<string | null>(null);
  cidRef.current = conversationId;
  const turnsRef = useRef<Turn[]>([]);
  turnsRef.current = turns;

  const patch = useCallback((key: string, f: (t: Turn) => Partial<Turn>) => {
    setTurns((ts) => ts.map((t) => (t.key === key ? { ...t, ...f(t) } : t)));
  }, []);

  const ensureConversation = useCallback(async () => {
    if (cidRef.current) return cidRef.current;
    const c = await api<{ id: string }>("/api/conversations", { method: "POST", json: { persona } });
    setConversationId(c.id);
    cidRef.current = c.id;
    return c.id;
  }, [persona]);

  const finish = useCallback((key: string, r: MessageResponse) => {
    patch(key, () => ({ state: "done", response: r, requestId: r.request_id, stages: r.workflow.stages?.length ? r.workflow.stages : undefined } as Partial<Turn>));
  }, [patch]);

  // Non-streaming request with the same idempotency key: used as fallback and for reconnection (server returns the stored
  // or in-flight result instead of running the workflow twice).
  const postPlain = useCallback(async (cid: string, key: string, body: object) => {
    const r = await api<MessageResponse>(`/api/conversations/${cid}/messages`, { method: "POST", json: body });
    finish(key, r);
  }, [finish]);

  const send = useCallback(async (question: string, context: MessageContext = {}) => {
    const q = question.trim();
    if (!q) return;
    const key = newKey();
    setSelected(turnsRef.current.length);
    setTurns((ts) => [...ts, { key, question: q, context, state: "streaming", stages: [], agents: [] }]);
    let cid: string;
    try {
      cid = await ensureConversation();
    } catch (e: any) {
      patch(key, () => ({ state: "error", error: e?.message ?? "Could not start a conversation" }));
      return;
    }
    const body = { text: q, persona, client_message_id: key, language, context };
    const ctrl = new AbortController();
    abort.current = ctrl;
    let gotResult = false;
    try {
      const res = await fetch(`/api/conversations/${cid}/messages/stream`, {
        method: "POST", signal: ctrl.signal,
        headers: { "Content-Type": "application/json", Accept: "text/event-stream", Authorization: `Bearer ${tokenStore.get()}` },
        body: JSON.stringify(body),
      });
      if (res.status === 401) window.dispatchEvent(new Event("flo:logout"));
      if (!res.ok || !res.body) throw new Error(`stream unavailable (${res.status})`);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const { events, rest } = parseSSE(buf);
        buf = rest;
        for (const ev of events) {
          const d: any = ev.data;
          if (ev.event === "started") patch(key, () => ({ requestId: d.request_id }));
          else if (ev.event === "stage") patch(key, (t) => ({ stages: [...t.stages.filter((s) => !(s.id === d.id && s.status === "active" && d.status === "done")), d] }));
          else if (ev.event === "intent") patch(key, () => ({ intent: d }));
          else if (ev.event === "plan") patch(key, () => ({ plan: d }));
          else if (ev.event === "agent") patch(key, (t) => ({ agents: [...t.agents, d] }));
          else if (ev.event === "result") { gotResult = true; finish(key, d as MessageResponse); }
          else if (ev.event === "error") patch(key, () => ({ state: "error", error: d.message ?? d.code }));
        }
      }
      if (!gotResult) throw new Error("stream ended before a result");
    } catch (e: any) {
      if (ctrl.signal.aborted) return;
      // reconnect: same idempotency key, so the server never runs the workflow twice
      try {
        await postPlain(cid, key, body);
      } catch (e2: any) {
        patch(key, () => ({ state: "error", error: e2?.message ?? e?.message ?? "Request failed" }));
      }
    } finally {
      if (abort.current === ctrl) abort.current = null;
    }
  }, [ensureConversation, finish, language, patch, persona, postPlain]);

  const cancel = useCallback(async () => {
    const t = [...turns].reverse().find((x) => x.state === "streaming");
    abort.current?.abort();
    if (t?.requestId) await api(`/api/conversations/requests/${t.requestId}/cancel`, { method: "POST" }).catch(() => undefined);
    if (t) {
      const cid = cidRef.current;
      // the server records the cancelled run under the same key; fetch it so the transcript stays truthful
      if (cid) {
        try {
          await postPlain(cid, t.key, { text: t.question, persona, client_message_id: t.key, language, context: t.context ?? {} });
          return;
        } catch { /* fall through */ }
      }
      patch(t.key, () => ({ state: "error", error: "Cancelled" }));
    }
  }, [language, patch, persona, postPlain, turns]);

  const load = useCallback(async (cid: string) => {
    const c = await api<{ id: string; persona: string; messages: StoredMessage[] }>(`/api/conversations/${cid}`);
    const out: Turn[] = [];
    for (const m of c.messages) {
      if (m.role === "user") out.push({ key: m.id, question: m.content, state: "done", stages: [], agents: [] });
      else if (out.length) {
        const last = out[out.length - 1];
        if (m.response) Object.assign(last, { response: m.response, requestId: m.request_id ?? undefined, stages: m.response.workflow.stages ?? [] });
        else Object.assign(last, { state: "error", error: m.content });
      }
    }
    setConversationId(c.id);
    setTurns(out);
    setSelected(out.length - 1);
    return c.persona;
  }, []);

  const reset = useCallback(() => {
    abort.current?.abort();
    setConversationId(null);
    setTurns([]);
    setSelected(-1);
  }, []);

  useEffect(() => () => abort.current?.abort(), []);

  const busy = turns.some((t) => t.state === "streaming");
  return { conversationId, turns, selected, setSelected, send, cancel, load, reset, busy };
}
